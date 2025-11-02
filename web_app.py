"""
YouTube视频转文本并总结 - Web应用
整合下载、转录和总结功能
"""
import os
import sys
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_file, Response, stream_with_context
import threading
import json
import time
import queue

# 加载.env文件
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ 已加载.env文件")
except ImportError:
    print("⚠ python-dotenv未安装，无法自动加载.env文件")
    print("  建议运行: uv add python-dotenv")
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

# 添加src目录到路径
src_path = str(Path(__file__).parent / 'src')
sys.path.insert(0, src_path)

# 导入模块（处理相对导入问题）
import importlib.util

# 导入download_youtube_audio
spec1 = importlib.util.spec_from_file_location("download_youtube_audio", Path(__file__).parent / "src" / "download_youtube_audio.py")
download_module = importlib.util.module_from_spec(spec1)
spec1.loader.exec_module(download_module)
download_youtube_audio = download_module.download_youtube_audio

# 导入download_podcast
spec_podcast = importlib.util.spec_from_file_location("download_podcast", Path(__file__).parent / "src" / "download_podcast.py")
podcast_module = importlib.util.module_from_spec(spec_podcast)
spec_podcast.loader.exec_module(podcast_module)
download_podcast_from_rss = podcast_module.download_podcast_from_rss
download_podcast_simple = podcast_module.download_podcast_simple
parse_rss_feed = podcast_module.parse_rss_feed

# 导入transcribe_audio
spec2 = importlib.util.spec_from_file_location("transcribe_audio", Path(__file__).parent / "src" / "transcribe_audio.py")
transcribe_module = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(transcribe_module)
transcribe_audio = transcribe_module.transcribe_audio
save_transcription_result = transcribe_module.save_transcription_result

# 导入summarize_text
spec3 = importlib.util.spec_from_file_location("summarize_text", Path(__file__).parent / "src" / "summarize_text.py")
summarize_module = importlib.util.module_from_spec(spec3)
spec3.loader.exec_module(summarize_module)
summarize_text = summarize_module.summarize_text

# 导入translate_text
spec4 = importlib.util.spec_from_file_location("translate_text", Path(__file__).parent / "src" / "translate_text.py")
translate_module = importlib.util.module_from_spec(spec4)
spec4.loader.exec_module(translate_module)
translate_list_parallel = translate_module.translate_list_parallel

app = Flask(__name__)

# 存储任务状态和进度队列
tasks = {}
progress_queues = {}  # task_id -> queue.Queue


def register_apple_fonts():
    """注册Apple系统字体"""
    # macOS系统的Apple字体路径
    apple_font_paths = [
        # PingFang SC (简体中文) - 优先使用
        '/System/Library/Fonts/PingFang.ttc',
        '/Library/Fonts/PingFang.ttc',
        # STHeiti (黑体)
        '/System/Library/Fonts/STHeiti Light.ttc',
        '/System/Library/Fonts/Supplemental/STHeiti Medium.ttc',
        # 其他中文字体
        '/System/Library/Fonts/STSong.ttc',
        '/System/Library/Fonts/STKaiti.ttc',
        # 英文系统字体（作为fallback）
        '/System/Library/Fonts/Helvetica.ttc',
        '/System/Library/Fonts/SFNS.ttf',
    ]
    
    # 尝试注册简体中文字体
    for font_path in apple_font_paths:
        if os.path.exists(font_path):
            try:
                # TTC文件可能需要特殊处理，但对于reportlab，直接使用TTFont应该可以
                pdfmetrics.registerFont(TTFont('AppleChinese', font_path))
                print(f"✓ 成功注册Apple字体: {font_path}")
                return 'AppleChinese'
            except Exception as e:
                print(f"⚠ 注册字体失败 {font_path}: {e}")
                continue
    
    # 如果所有字体都注册失败，使用Helvetica（reportlab内置字体）
    print("⚠ 未找到Apple字体，使用默认Helvetica字体（可能无法正确显示中文）")
    return 'Helvetica'


def generate_transcript_pdf(segments, output_path, has_speakers=False, title="转录文本"):
    """生成转录文本的PDF文件"""
    doc = SimpleDocTemplate(output_path, pagesize=A4, 
                          leftMargin=2*cm, rightMargin=2*cm,
                          topMargin=2*cm, bottomMargin=2*cm)
    story = []
    
    # 注册Apple字体
    font_name = register_apple_fonts()
    
    # 创建样式
    title_style = ParagraphStyle(
        'TitleStyle',
        fontSize=20,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=20,
        spaceBefore=0,
        fontName=font_name,
        leading=26
    )
    
    speaker_style = ParagraphStyle(
        'SpeakerStyle',
        fontSize=11,
        textColor=colors.HexColor('#3498db'),
        spaceAfter=5,
        fontName=font_name,
        leading=14
    )
    
    time_style = ParagraphStyle(
        'TimeStyle',
        fontSize=10,
        textColor=colors.HexColor('#7f8c8d'),
        spaceAfter=5,
        fontName=font_name,
        leading=12
    )
    
    text_style = ParagraphStyle(
        'TextStyle',
        fontSize=12,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=15,
        alignment=TA_JUSTIFY,
        fontName=font_name,
        leading=18
    )
    
    # 添加标题
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # 添加段落
    for idx, segment in enumerate(segments, 1):
        text = segment.get('text', '').strip()
        if not text:
            continue
        
        # 时间戳
        start_time = segment.get('start', 0)
        end_time = segment.get('end', 0)
        hours = int(start_time // 3600)
        minutes = int((start_time % 3600) // 60)
        secs = int(start_time % 60)
        if hours > 0:
            start_str = f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            start_str = f"{minutes}:{secs:02d}"
        
        end_hours = int(end_time // 3600)
        end_minutes = int((end_time % 3600) // 60)
        end_secs = int(end_time % 60)
        if end_hours > 0:
            end_str = f"{end_hours}:{end_minutes:02d}:{end_secs:02d}"
        else:
            end_str = f"{end_minutes}:{end_secs:02d}"
        
        time_str = f"{start_str} - {end_str}"
        
        story.append(Paragraph(f"<b>{time_str}</b>", time_style))
        
        # 说话人标签（如果有）
        if has_speakers and segment.get('speaker'):
            speaker = segment.get('speaker', '')
            story.append(Paragraph(f"<b>[{speaker}]</b>", speaker_style))
        
        # 文本内容
        # 转义XML特殊字符
        text_escaped = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        story.append(Paragraph(text_escaped, text_style))
        
        story.append(Spacer(1, 0.3*cm))
    
    # 生成PDF
    doc.build(story)
    print(f"✓ PDF已生成: {output_path}")


def generate_transcript_pdf_with_translation(segments, translations, output_path, has_speakers=False, title="转录文本（含翻译）"):
    """生成包含原文和翻译的PDF文件"""
    doc = SimpleDocTemplate(output_path, pagesize=A4, 
                          leftMargin=2*cm, rightMargin=2*cm,
                          topMargin=2*cm, bottomMargin=2*cm)
    story = []
    
    # 注册Apple字体
    font_name = register_apple_fonts()
    
    # 创建样式
    title_style = ParagraphStyle(
        'TitleStyle',
        fontSize=20,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=20,
        spaceBefore=0,
        fontName=font_name,
        leading=26
    )
    
    speaker_style = ParagraphStyle(
        'SpeakerStyle',
        fontSize=11,
        textColor=colors.HexColor('#3498db'),
        spaceAfter=5,
        fontName=font_name,
        leading=14
    )
    
    time_style = ParagraphStyle(
        'TimeStyle',
        fontSize=10,
        textColor=colors.HexColor('#7f8c8d'),
        spaceAfter=5,
        fontName=font_name,
        leading=12
    )
    
    original_style = ParagraphStyle(
        'OriginalStyle',
        fontSize=12,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=8,
        alignment=TA_JUSTIFY,
        fontName=font_name,
        leading=18
    )
    
    translation_style = ParagraphStyle(
        'TranslationStyle',
        fontSize=12,
        textColor=colors.HexColor('#e74c3c'),  # 红色
        spaceAfter=15,
        alignment=TA_JUSTIFY,
        fontName=font_name,
        leading=18,
        leftIndent=0.5*cm
    )
    
    # 添加标题
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # 添加段落（一段原文一段翻译）
    for idx, (segment, translation) in enumerate(zip(segments, translations), 1):
        text = segment.get('text', '').strip()
        translated_text = translation.strip() if translation else ''
        
        if not text:
            continue
        
        # 时间戳
        start_time = segment.get('start', 0)
        end_time = segment.get('end', 0)
        hours = int(start_time // 3600)
        minutes = int((start_time % 3600) // 60)
        secs = int(start_time % 60)
        if hours > 0:
            start_str = f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            start_str = f"{minutes}:{secs:02d}"
        
        end_hours = int(end_time // 3600)
        end_minutes = int((end_time % 3600) // 60)
        end_secs = int(end_time % 60)
        if end_hours > 0:
            end_str = f"{end_hours}:{end_minutes:02d}:{end_secs:02d}"
        else:
            end_str = f"{end_minutes}:{end_secs:02d}"
        
        time_str = f"{start_str} - {end_str}"
        
        story.append(Paragraph(f"<b>{time_str}</b>", time_style))
        
        # 说话人标签（如果有）
        if has_speakers and segment.get('speaker'):
            speaker = segment.get('speaker', '')
            story.append(Paragraph(f"<b>[{speaker}]</b>", speaker_style))
        
        # 原文
        text_escaped = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        story.append(Paragraph(f"<b>原文:</b><br/>{text_escaped}", original_style))
        
        # 翻译
        if translated_text:
            translation_escaped = translated_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(f"<b>翻译:</b><br/>{translation_escaped}", translation_style))
        
        story.append(Spacer(1, 0.4*cm))
    
    # 生成PDF
    doc.build(story)
    print(f"✓ 双语PDF已生成: {output_path}")


def get_html_template():
    """返回HTML模板"""
    return '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube视频总结工具</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #f0f0f0;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: #ffffff;
            border: 1px solid #e0e0e0;
            overflow: hidden;
        }
        
        .header {
            background: #3498db;
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2em;
            margin-bottom: 10px;
            font-weight: 500;
        }
        
        .header p {
            opacity: 0.95;
            font-weight: 300;
        }
        
        .content {
            padding: 30px;
        }
        
        .input-group {
            margin-bottom: 25px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #2c3e50;
            font-size: 14px;
        }
        
        input[type="text"], select {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #bdc3c7;
            border-radius: 0;
            font-size: 16px;
            transition: border-color 0.2s;
            background: #ffffff;
        }
        
        input[type="text"]:focus, select:focus {
            outline: none;
            border-color: #3498db;
        }
        
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        
        button {
            width: 100%;
            padding: 15px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 0;
            font-size: 18px;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        button:hover:not(:disabled) {
            background: #2980b9;
        }
        
        button:disabled {
            background: #95a5a6;
            cursor: not-allowed;
        }
        
        .status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 0;
            display: none;
            border-left: 4px solid;
        }
        
        .status.info {
            background: #ebf5fb;
            color: #2980b9;
            border-left-color: #3498db;
        }
        
        .status.success {
            background: #eafaf1;
            color: #27ae60;
            border-left-color: #2ecc71;
        }
        
        .status.error {
            background: #fdeaea;
            color: #c0392b;
            border-left-color: #e74c3c;
        }
        
        .progress {
            margin-top: 20px;
            display: none;
        }
        
        .progress-bar {
            width: 100%;
            height: 30px;
            background: #ecf0f1;
            border: 1px solid #bdc3c7;
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: #3498db;
            width: 0%;
            transition: width 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 500;
            font-size: 13px;
        }
        
        .results {
            margin-top: 30px;
            display: none;
        }
        
        .result-section {
            margin-bottom: 25px;
            padding: 20px;
            background: #f8f9fa;
            border: 1px solid #e0e0e0;
        }
        
        .result-section h3 {
            margin-bottom: 15px;
            color: #2c3e50;
            font-weight: 500;
            font-size: 18px;
        }
        
        .result-content {
            background: white;
            padding: 15px;
            border: 1px solid #e0e0e0;
            max-height: 400px;
            overflow-y: auto;
            white-space: pre-wrap;
            line-height: 1.6;
            color: #34495e;
        }
        
        .segment-item {
            margin-bottom: 12px;
            padding: 10px;
            border-left: 3px solid #3498db;
            background: #f8f9fa;
        }
        
        .segment-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 5px;
            font-size: 12px;
            color: #7f8c8d;
        }
        
        .segment-time {
            font-weight: 500;
        }
        
        .segment-speaker {
            background: #3498db;
            color: white;
            padding: 2px 8px;
            border-radius: 3px;
            font-weight: 500;
            font-size: 11px;
        }
        
        .segment-text {
            color: #2c3e50;
            line-height: 1.5;
        }
        
        .download-btn {
            display: inline-block;
            margin-top: 10px;
            padding: 10px 20px;
            background: #2ecc71;
            color: white;
            text-decoration: none;
            border-radius: 0;
            transition: background 0.2s;
            border: none;
            font-weight: 500;
        }
        
        .download-btn:hover {
            background: #27ae60;
        }
        
        .steps {
            margin-top: 20px;
            display: none;
        }
        
        .step {
            padding: 15px;
            margin-bottom: 10px;
            background: #ffffff;
            border: 1px solid #e0e0e0;
            border-left: 4px solid #bdc3c7;
            font-weight: 400;
        }
        
        .step.active {
            background: #ebf5fb;
            border-left-color: #3498db;
            color: #2980b9;
        }
        
        .step.completed {
            background: #eafaf1;
            border-left-color: #2ecc71;
            color: #27ae60;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎥 音频视频总结工具</h1>
            <p>支持YouTube视频和播客RSS，自动下载、转录并生成总结</p>
        </div>
        
        <div class="content">
            <form id="videoForm">
                <div class="input-group">
                    <label for="input_type">输入类型：</label>
                    <select id="input_type" name="input_type">
                        <option value="youtube" selected>YouTube视频</option>
                        <option value="rss">播客RSS</option>
                    </select>
                </div>
                
                <div class="input-group">
                    <label for="youtube_url" id="url_label">YouTube视频链接：</label>
                    <input type="text" id="youtube_url" name="youtube_url" 
                           placeholder="https://www.youtube.com/watch?v=..." required>
                </div>
                
                <div class="form-row">
                    <div class="input-group">
                        <label for="model_name">转录模型：</label>
                        <select id="model_name" name="model_name">
                            <option value="tiny">Tiny (最快)</option>
                            <option value="base" selected>Base (平衡)</option>
                            <option value="small">Small (更准确)</option>
                            <option value="medium">Medium (高准确度)</option>
                        </select>
                    </div>
                    
                    <div class="input-group">
                        <label for="language">语言：</label>
                        <select id="language" name="language">
                            <option value="">自动检测</option>
                            <option value="en" selected>英语</option>
                            <option value="zh">中文</option>
                            <option value="ja">日语</option>
                            <option value="es">西班牙语</option>
                        </select>
                    </div>
                </div>
                
                <div class="input-group">
                    <label style="display: flex; align-items: center; cursor: pointer;">
                        <input type="checkbox" id="enable_diarize" name="enable_diarize" style="width: auto; margin-right: 8px;">
                        <span>启用说话人检测（需要 HF_TOKEN 环境变量）</span>
                    </label>
                </div>
                
                <div class="input-group">
                    <label style="display: flex; align-items: center; cursor: pointer;">
                        <input type="checkbox" id="enable_translate" name="enable_translate" style="width: auto; margin-right: 8px;">
                        <span>启用翻译</span>
                    </label>
                </div>
                
                <div class="input-group" id="translate_lang_group" style="display: none;">
                    <label for="translate_lang">翻译目标语言：</label>
                    <select id="translate_lang" name="translate_lang">
                        <option value="zh-cn" selected>简体中文</option>
                        <option value="zh-tw">繁体中文</option>
                        <option value="en">英语</option>
                        <option value="ja">日语</option>
                        <option value="ko">韩语</option>
                        <option value="es">西班牙语</option>
                        <option value="fr">法语</option>
                        <option value="de">德语</option>
                    </select>
                </div>
                
                <button type="submit" id="submitBtn">开始处理</button>
            </form>
            
            <div class="steps" id="steps">
                <div class="step" id="step1">
                    <strong>步骤 1:</strong> 下载音频...
                </div>
                <div class="step" id="step2">
                    <strong>步骤 2:</strong> 转录音频为文本...
                </div>
                <div class="step" id="step3">
                    <strong>步骤 3:</strong> 生成文本总结...
                </div>
            </div>
            
            <div class="progress" id="progress">
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill">0%</div>
                </div>
            </div>
            
            <div class="status" id="status"></div>
            
            <div class="estimated-time" id="estimatedTime" style="display: none; margin-top: 15px; padding: 10px; background: #f8f9fa; border-left: 4px solid #3498db; color: #2c3e50; font-size: 14px;">
                <strong>预计转录时长：</strong><span id="estimatedTimeValue">计算中...</span>
            </div>
            
            <div class="results" id="results">
                <div class="result-section">
                    <h3>📝 转录文本</h3>
                    <div class="result-content" id="transcript"></div>
                    <div style="margin-top: 10px;">
                        <a href="#" class="download-btn" id="downloadTranscript">下载文本 (TXT)</a>
                        <a href="#" class="download-btn" id="downloadTranscriptPDF" style="margin-left: 10px;">下载 PDF</a>
                    </div>
                </div>
                
                <div class="result-section">
                    <h3>📋 文本总结</h3>
                    <div class="result-content" id="summary"></div>
                    <a href="#" class="download-btn" id="downloadSummary">下载总结</a>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const form = document.getElementById('videoForm');
        const submitBtn = document.getElementById('submitBtn');
        const statusDiv = document.getElementById('status');
        const progressDiv = document.getElementById('progress');
        const progressFill = document.getElementById('progressFill');
        const stepsDiv = document.getElementById('steps');
        const resultsDiv = document.getElementById('results');
        const inputType = document.getElementById('input_type');
        const urlLabel = document.getElementById('url_label');
        const urlInput = document.getElementById('youtube_url');
        const enableTranslate = document.getElementById('enable_translate');
        const translateLangGroup = document.getElementById('translate_lang_group');
        
        // 处理输入类型切换
        inputType.addEventListener('change', (e) => {
            if (e.target.value === 'rss') {
                urlLabel.textContent = '播客RSS链接：';
                urlInput.placeholder = 'https://example.com/podcast.rss 或 https://feeds.example.com/rss';
            } else {
                urlLabel.textContent = 'YouTube视频链接：';
                urlInput.placeholder = 'https://www.youtube.com/watch?v=...';
            }
        });
        
        // 处理翻译选项显示/隐藏
        enableTranslate.addEventListener('change', (e) => {
            if (e.target.checked) {
                translateLangGroup.style.display = 'block';
            } else {
                translateLangGroup.style.display = 'none';
            }
        });
        
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const url = document.getElementById('youtube_url').value;
            const inputTypeValue = document.getElementById('input_type').value;
            const modelName = document.getElementById('model_name').value;
            const language = document.getElementById('language').value;
            const enableDiarize = document.getElementById('enable_diarize').checked;
            const enableTranslate = document.getElementById('enable_translate').checked;
            const translateLang = document.getElementById('translate_lang').value;
            
            // 重置UI
            submitBtn.disabled = true;
            submitBtn.textContent = '处理中...';
            statusDiv.style.display = 'none';
            resultsDiv.style.display = 'none';
            stepsDiv.style.display = 'block';
            progressDiv.style.display = 'block';
            updateProgress(0);
            
            // 重置下载按钮显示状态
            document.getElementById('downloadTranscript').style.display = 'inline-block';
            document.getElementById('downloadTranscriptPDF').style.display = 'inline-block';
            document.getElementById('downloadSummary').style.display = 'inline-block';
            
            // 重置步骤
            ['step1', 'step2', 'step3'].forEach(id => {
                const step = document.getElementById(id);
                step.className = 'step';
            });
            
            try {
                // 发送请求
                const response = await fetch('/process', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        url: url,
                        input_type: inputTypeValue,
                        model_name: modelName,
                        language: language || null,
                        enable_diarize: enableDiarize,
                        enable_translate: enableTranslate,
                        translate_lang: translateLang
                    })
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || '处理失败');
                }
                
                const taskId = data.task_id;
                
                // 使用SSE实时接收进度更新
                setupSSEConnection(taskId);
                
            } catch (error) {
                showStatus('error', '错误: ' + error.message);
                submitBtn.disabled = false;
                submitBtn.textContent = '开始处理';
            }
        });
        
        function setupSSEConnection(taskId) {
            // 使用Server-Sent Events实时接收进度
            const eventSource = new EventSource(`/stream/${taskId}`);
            
            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    
                    // 更新进度条
                    updateProgress(data.progress || 0);
                    
                    // 更新步骤状态
                    updateStepStatus(data.step, data.message);
                    
                    // 更新状态消息
                    if (data.message) {
                        showStatus('info', data.message);
                        
                        // 检查消息中是否包含预计时长信息
                        if (data.message.includes('预计转录时间')) {
                            const estimatedTimeDiv = document.getElementById('estimatedTime');
                            const estimatedTimeValue = document.getElementById('estimatedTimeValue');
                            if (estimatedTimeDiv && estimatedTimeValue) {
                                // 提取预计时间
                                const match = data.message.match(/预计转录时间[：:]\s*(\d+分\d+秒)/);
                                if (match) {
                                    estimatedTimeValue.textContent = match[1];
                                    estimatedTimeDiv.style.display = 'block';
                                }
                            }
                        }
                    }
                    
                    // 检查是否完成
                    if (data.status === 'completed') {
                        eventSource.close();
                        loadFinalResults(taskId);
                    } else if (data.status === 'error') {
                        eventSource.close();
                        showStatus('error', '错误: ' + (data.message || '未知错误'));
                        submitBtn.disabled = false;
                        submitBtn.textContent = '开始处理';
                    }
                    
                } catch (error) {
                    console.error('解析SSE消息失败:', error);
                }
            };
            
            eventSource.onerror = (error) => {
                console.error('SSE连接错误:', error);
                // 如果连接关闭，可能是任务完成，尝试获取最终结果
                setTimeout(() => {
                    loadFinalResults(taskId);
                }, 1000);
                eventSource.close();
            };
        }
        
        function updateStepStatus(step, message) {
            // 重置所有步骤
            ['step1', 'step2', 'step3'].forEach(id => {
                const stepEl = document.getElementById(id);
                stepEl.className = 'step';
            });
            
            // 根据当前步骤更新状态
            if (step === 'download') {
                document.getElementById('step1').classList.add('active');
                document.getElementById('step1').innerHTML = `<strong>步骤 1:</strong> ${message || '下载YouTube音频...'}`;
            } else if (step === 'transcribe') {
                document.getElementById('step1').classList.add('completed');
                document.getElementById('step2').classList.add('active');
                document.getElementById('step2').innerHTML = `<strong>步骤 2:</strong> ${message || '转录音频为文本...'}`;
            } else if (step === 'summarize') {
                document.getElementById('step2').classList.add('completed');
                document.getElementById('step3').classList.add('active');
                document.getElementById('step3').innerHTML = `<strong>步骤 3:</strong> ${message || '生成文本总结...'}`;
            } else if (step === 'completed') {
                ['step1', 'step2', 'step3'].forEach(id => {
                    document.getElementById(id).classList.add('completed');
                });
            }
        }
        
        function formatTime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);
            if (hours > 0) {
                return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
            }
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        }
        
        function formatTranscript(segments, hasSpeakers) {
            if (!segments || segments.length === 0) {
                return '<p>无转录内容</p>';
            }
            
            // 总是显示带时间戳的格式，如果有说话人信息则显示说话人标签
            let html = '';
            segments.forEach((segment, idx) => {
                const startTime = formatTime(segment.start || 0);
                const endTime = formatTime(segment.end || 0);
                const speaker = segment.speaker || '';
                const text = segment.text || '';
                
                html += `
                    <div class="segment-item">
                        <div class="segment-header">
                            <span class="segment-time">${startTime} - ${endTime}</span>
                            ${hasSpeakers && speaker ? `<span class="segment-speaker">${speaker}</span>` : ''}
                        </div>
                        <div class="segment-text">${text}</div>
                    </div>
                `;
            });
            
            return html;
        }
        
        async function loadFinalResults(taskId) {
            try {
                const response = await fetch(`/status/${taskId}`);
                const data = await response.json();
                
                if (data.status === 'completed') {
                    // 显示转录结果（带说话人信息）
                    const transcriptDiv = document.getElementById('transcript');
                    if (data.segments && data.segments.length > 0) {
                        transcriptDiv.innerHTML = formatTranscript(data.segments, data.has_speakers || false);
                    } else {
                        transcriptDiv.textContent = data.transcript || '无转录内容';
                    }
                    
                    // 显示总结
                    document.getElementById('summary').textContent = data.summary || '无总结内容';
                    resultsDiv.style.display = 'block';
                    
                    // 设置下载链接
                    if (data.summary_file) {
                        document.getElementById('downloadSummary').href = `/download/${taskId}/summary`;
                    }
                    
                    // 设置转录文本下载链接
                    const downloadTranscriptBtn = document.getElementById('downloadTranscript');
                    if (data.transcript_file) {
                        downloadTranscriptBtn.href = `/download/${taskId}/transcript`;
                        downloadTranscriptBtn.style.display = 'inline-block';
                    } else {
                        downloadTranscriptBtn.style.display = 'none';
                    }
                    
                    // 设置转录PDF下载链接
                    const downloadTranscriptPDFBtn = document.getElementById('downloadTranscriptPDF');
                    if (data.transcript_pdf_file) {
                        downloadTranscriptPDFBtn.href = `/download/${taskId}/transcript_pdf`;
                        downloadTranscriptPDFBtn.style.display = 'inline-block';
                    } else {
                        downloadTranscriptPDFBtn.style.display = 'none';
                    }
                    
                    submitBtn.disabled = false;
                    submitBtn.textContent = '开始处理';
                    showStatus('success', '处理完成！');
                }
            } catch (error) {
                showStatus('error', '获取结果时出错: ' + error.message);
                submitBtn.disabled = false;
                submitBtn.textContent = '开始处理';
            }
        }
        
        function updateProgress(percent) {
            progressFill.style.width = percent + '%';
            progressFill.textContent = percent + '%';
        }
        
        function showStatus(type, message) {
            statusDiv.className = 'status ' + type;
            statusDiv.textContent = message;
            statusDiv.style.display = 'block';
        }
    </script>
</body>
</html>
    '''


@app.route('/')
def index():
    """主页面"""
    return render_template_string(get_html_template())


@app.route('/process', methods=['POST'])
def process_video():
    """处理YouTube视频或播客RSS"""
    data = request.json
    url = data.get('url')
    input_type = data.get('input_type', 'youtube')
    model_name = data.get('model_name', 'base')
    language = data.get('language')
    enable_diarize = data.get('enable_diarize', False)
    enable_translate = data.get('enable_translate', False)
    translate_lang = data.get('translate_lang', 'zh-cn')
    
    if not url:
        return jsonify({'error': '请提供链接'}), 400
    
    # 生成任务ID
    task_id = f"task_{int(time.time())}"
    
    # 初始化任务状态
    tasks[task_id] = {
        'status': 'processing',
        'step': 'download',
        'progress': 0,
        'message': '正在初始化...',
        'transcript': '',
        'segments': [],  # 保存带说话人信息的段落
        'summary': '',
        'error': None,
        'summary_file': None,
        'transcript_file': None,  # 转录文本文件路径
        'transcript_pdf_file': None,  # 转录PDF文件路径
        'has_speakers': False
    }
    
    # 创建进度队列
    progress_queues[task_id] = queue.Queue()
    
    # 在后台线程中处理
    if input_type == 'rss':
        thread = threading.Thread(
            target=process_podcast_rss,
            args=(task_id, url, model_name, language, enable_diarize, enable_translate, translate_lang)
        )
    else:
        thread = threading.Thread(
            target=process_youtube_video,
            args=(task_id, url, model_name, language, enable_diarize, enable_translate, translate_lang)
        )
    thread.daemon = True
    thread.start()
    
    return jsonify({'task_id': task_id})


def update_progress(task_id, step, progress, message):
    """更新进度并推送"""
    tasks[task_id]['step'] = step
    tasks[task_id]['progress'] = progress
    tasks[task_id]['message'] = message
    
    if task_id in progress_queues:
        try:
            progress_queues[task_id].put({
                'step': step,
                'progress': progress,
                'message': message,
                'status': tasks[task_id]['status']
            }, timeout=0.1)
        except queue.Full:
            pass


def process_youtube_video(task_id, url, model_name, language, enable_diarize=False, enable_translate=False, translate_lang='zh-cn'):
    """处理YouTube视频的主函数"""
    try:
        # 步骤1: 下载音频
        update_progress(task_id, 'download', 5, '正在获取视频信息...')
        output_dir = Path(__file__).parent / 'downloads'
        output_dir.mkdir(exist_ok=True)
        
        # 定义下载进度回调函数
        def download_progress_hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    # 下载进度：5% - 25%
                    percent = 5 + int((downloaded / total) * 20)
                    download_percent = (downloaded / total) * 100
                    speed = d.get('speed', 0)
                    if speed:
                        speed_mb = speed / 1024 / 1024
                        message = f'正在下载音频: {download_percent:.1f}% ({speed_mb:.1f} MB/s)'
                    else:
                        message = f'正在下载音频: {download_percent:.1f}%'
                    update_progress(task_id, 'download', percent, message)
            elif d['status'] == 'finished':
                # 下载完成，开始转换格式：25% - 30%
                update_progress(task_id, 'download', 25, '下载完成，正在转换音频格式...')
        
        audio_file = download_youtube_audio(
            url, 
            output_dir=str(output_dir),
            progress_hook=download_progress_hook
        )
        if not audio_file:
            raise Exception("音频下载失败")
        
        update_progress(task_id, 'download', 30, '✓ 音频下载完成')
        time.sleep(0.5)  # 短暂延迟以便用户看到更新
        
        # 获取音频时长和预计转录时间
        from src.transcribe_audio import get_audio_duration, estimate_transcription_time
        import torch
        
        audio_duration = get_audio_duration(audio_file)
        # 检测设备
        device = "cpu"
        try:
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = "cpu"  # WhisperX不支持MPS
        except:
            pass
        
        estimated_time = estimate_transcription_time(audio_duration, model_name, device)
        
        # 存储预计时长信息
        tasks[task_id]['audio_duration'] = audio_duration
        tasks[task_id]['estimated_transcription_time'] = estimated_time
        
        duration_str = f"{int(audio_duration//60)}分{int(audio_duration%60)}秒"
        est_time_str = f"{int(estimated_time//60)}分{int(estimated_time%60)}秒"
        update_progress(task_id, 'transcribe', 35, f'音频时长: {duration_str}，预计转录时间: {est_time_str}')
        
        # 步骤2: 转录（使用分块转录）
        def transcription_progress(current, total, message):
            # 转录进度：35% - 70%
            progress = 35 + int((current / total) * 35)
            update_progress(task_id, 'transcribe', progress, message)
        
        # 获取 HF_TOKEN 用于说话人检测
        hf_token = os.getenv("HF_TOKEN") if enable_diarize else None
        if enable_diarize and not hf_token:
            update_progress(task_id, 'transcribe', 40, '⚠️ 说话人检测需要 HF_TOKEN，跳过说话人检测...')
            enable_diarize = False
        
        # 进行说话人检测
        if enable_diarize:
            update_progress(task_id, 'transcribe', 70, '正在进行说话人分离...')
        
        result = transcribe_audio(
            audio_file,
            model_name=model_name,
            language=language if language else None,
            output_dir=str(output_dir),
            diarize=enable_diarize,
            hf_token=hf_token,
            enable_chunking=True,  # 启用分块转录
            chunk_duration=60.0,   # 每块60秒
            max_workers=4,         # 4个并发线程
            progress_callback=transcription_progress
        )
        
        # 转录完成，进入文本提取阶段
        update_progress(task_id, 'transcribe', 65, '✓ 转录完成，正在提取文本...')
        
        # 提取转录文本和段落信息
        transcript_text = ''
        segments_data = []
        total_segments = len(result.get('segments', []))
        has_speakers = False
        
        if total_segments > 0:
            for idx, segment in enumerate(result.get('segments', [])):
                text = segment.get('text', '').strip()
                transcript_text += text + ' '
                
                # 提取段落信息
                segment_info = {
                    'text': text,
                    'start': segment.get('start', 0),
                    'end': segment.get('end', 0),
                    'speaker': segment.get('speaker', '')
                }
                segments_data.append(segment_info)
                
                if segment.get('speaker'):
                    has_speakers = True
                
                # 每处理一段文本更新一次进度：65% - 70%
                if idx % 5 == 0 or idx == total_segments - 1:
                    progress = 65 + int((idx / total_segments) * 5)
                    update_progress(task_id, 'transcribe', 
                                   progress,
                                   f'正在提取文本: {idx + 1}/{total_segments} 段落 ({(idx + 1) / total_segments * 100:.1f}%)')
        else:
            transcript_text = ''
        
        tasks[task_id]['transcript'] = transcript_text.strip()
        tasks[task_id]['segments'] = segments_data
        tasks[task_id]['has_speakers'] = has_speakers
        
        # 保存转录文本文件
        base_name = Path(audio_file).stem
        transcript_txt_file = output_dir / f"{base_name}_transcript.txt"
        with open(transcript_txt_file, 'w', encoding='utf-8') as f:
            if has_speakers:
                # 带说话人信息的格式
                for seg in segments_data:
                    speaker = seg.get('speaker', '')
                    text = seg.get('text', '').strip()
                    if speaker:
                        f.write(f"[{speaker}] {text}\n")
                    else:
                        f.write(f"{text}\n")
            else:
                # 简单文本格式
                for seg in segments_data:
                    f.write(f"{seg.get('text', '').strip()}\n")
        tasks[task_id]['transcript_file'] = str(transcript_txt_file)
        
        # 生成PDF文件
        transcript_pdf_file = output_dir / f"{base_name}_transcript.pdf"
        
        # 如果启用了翻译，生成双语PDF
        if enable_translate:
            try:
                update_progress(task_id, 'transcribe', 72, f'正在翻译文本到 {translate_lang}...')
                
                # 提取所有文本用于翻译
                texts_to_translate = [seg.get('text', '').strip() for seg in segments_data]
                
                # 并行翻译
                print(f"开始翻译 {len(texts_to_translate)} 条文本到 {translate_lang}...")
                translated_texts = translate_list_parallel(
                    texts_to_translate,
                    dest=translate_lang,
                    batch_size=15,
                    max_workers=5
                )
                
                # 验证翻译结果
                if not translated_texts or len(translated_texts) != len(texts_to_translate):
                    print(f"⚠ 翻译结果数量不匹配: 期望 {len(texts_to_translate)}, 实际 {len(translated_texts) if translated_texts else 0}")
                    # 如果翻译失败，使用原文
                    translated_texts = texts_to_translate
                
                # 打印前几条翻译结果用于调试
                if translated_texts:
                    print(f"翻译示例（前3条）:")
                    for i in range(min(3, len(translated_texts))):
                        print(f"  原文: {texts_to_translate[i][:50]}...")
                        print(f"  翻译: {translated_texts[i][:50]}...")
                
                update_progress(task_id, 'transcribe', 73, '✓ 翻译完成，正在生成双语PDF...')
                
                # 生成双语PDF
                generate_transcript_pdf_with_translation(
                    segments_data,
                    translated_texts,
                    str(transcript_pdf_file),
                    has_speakers=has_speakers,
                    title=f"转录文本（含翻译） - {base_name}"
                )
                
                # 确保文件存在并存储绝对路径
                if os.path.exists(transcript_pdf_file):
                    tasks[task_id]['transcript_pdf_file'] = str(os.path.abspath(transcript_pdf_file))
                    print(f"✓ 双语PDF文件已生成并存储: {tasks[task_id]['transcript_pdf_file']}")
                else:
                    print(f"⚠ PDF文件生成失败，文件不存在: {transcript_pdf_file}")
                    tasks[task_id]['transcript_pdf_file'] = None
            except Exception as e:
                print(f"⚠ 翻译或生成双语PDF失败: {e}")
                import traceback
                traceback.print_exc()
                # 如果翻译失败，生成普通PDF
                try:
                    generate_transcript_pdf(
                        segments_data, 
                        str(transcript_pdf_file),
                        has_speakers=has_speakers,
                        title=f"转录文本 - {base_name}"
                    )
                    if os.path.exists(transcript_pdf_file):
                        tasks[task_id]['transcript_pdf_file'] = str(os.path.abspath(transcript_pdf_file))
                except Exception as e2:
                    print(f"⚠ 生成普通PDF也失败: {e2}")
                    tasks[task_id]['transcript_pdf_file'] = None
        else:
            # 生成普通PDF
            try:
                generate_transcript_pdf(
                    segments_data, 
                    str(transcript_pdf_file),
                    has_speakers=has_speakers,
                    title=f"转录文本 - {base_name}"
                )
                # 确保文件存在并存储绝对路径
                if os.path.exists(transcript_pdf_file):
                    tasks[task_id]['transcript_pdf_file'] = str(os.path.abspath(transcript_pdf_file))
                    print(f"✓ PDF文件已生成并存储: {tasks[task_id]['transcript_pdf_file']}")
                else:
                    print(f"⚠ PDF文件生成失败，文件不存在: {transcript_pdf_file}")
                    tasks[task_id]['transcript_pdf_file'] = None
            except Exception as e:
                print(f"⚠ 生成PDF失败: {e}")
                import traceback
                traceback.print_exc()
                tasks[task_id]['transcript_pdf_file'] = None
        
        speaker_msg = f'，检测到 {len(set([s["speaker"] for s in segments_data if s["speaker"]]))} 个说话人' if has_speakers else ''
        update_progress(task_id, 'transcribe', 70, f'✓ 文本提取完成 ({total_segments} 段落{speaker_msg})')
        time.sleep(0.5)
        
        # 步骤3: 总结
        update_progress(task_id, 'summarize', 75, '正在准备总结...')
        
        # 检查是否有API密钥
        api_key = os.getenv("API_KEY_302_AI") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            tasks[task_id]['summary'] = "⚠️ 未设置API密钥，无法生成总结。请设置环境变量 API_KEY_302_AI 或 OPENAI_API_KEY"
            update_progress(task_id, 'summarize', 100, '⚠️ 跳过总结（缺少API密钥）')
        else:
            update_progress(task_id, 'summarize', 80, '正在分块文本（充分利用 GPT-4o 的 128k tokens 上下文）...')
            
            # 使用异步总结，充分利用 GPT-4o 的 128k tokens 上下文能力
            summary = summarize_text(
                text=transcript_text,
                api_key=api_key,
                chunk_size=100000,  # GPT-4o 支持 128k tokens，约等于 100k 字符
                chunk_overlap=300,  # 增大重叠以保持上下文连贯性
                enable_async=True,  # 启用异步并发
                max_workers=5,      # 5个并发线程
                show_progress=False
            )
            
            tasks[task_id]['summary'] = summary
            
            # 保存总结到文件
            summary_file = output_dir / f"{base_name}_summary.txt"
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(summary)
            tasks[task_id]['summary_file'] = str(summary_file)
            
            update_progress(task_id, 'summarize', 100, '✓ 总结完成')
        
        tasks[task_id]['status'] = 'completed'
        update_progress(task_id, 'completed', 100, '✓ 全部完成！')
        
    except Exception as e:
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['error'] = str(e)
        update_progress(task_id, 'error', 0, f'❌ 错误: {str(e)}')
    
    finally:
        # 发送结束信号
        if task_id in progress_queues:
            progress_queues[task_id].put(None)


def process_podcast_rss(task_id, rss_url, model_name, language, enable_diarize=False, enable_translate=False, translate_lang='zh-cn'):
    """处理播客RSS的主函数"""
    try:
        # 步骤1: 解析RSS并下载音频
        update_progress(task_id, 'download', 5, '正在解析RSS feed...')
        output_dir = Path(__file__).parent / 'downloads'
        output_dir.mkdir(exist_ok=True)
        
        # 解析RSS feed
        try:
            episodes = parse_rss_feed(rss_url)
        except Exception as e:
            raise Exception(f"RSS feed解析失败: {str(e)}")
        
        if not episodes:
            raise Exception("RSS feed中未找到播客集数")
        
        update_progress(task_id, 'download', 10, f'✓ 找到 {len(episodes)} 个播客集数，正在下载最新一集...')
        
        # 选择最新一集
        selected_episode = episodes[0]
        audio_url = selected_episode.get('audio_url', '')
        
        if not audio_url:
            raise Exception("播客集数中没有找到音频URL")
        
        update_progress(task_id, 'download', 15, f'正在下载: {selected_episode.get("title", "未知标题")[:50]}...')
        
        # 下载音频文件（带进度更新）
        import requests
        
        response = requests.get(audio_url, stream=True, timeout=120)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        filename = selected_episode.get('title', 'podcast_episode')
        # 清理文件名
        filename = ''.join(c for c in filename if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = filename[:100]  # 限制长度
        
        # 确定文件扩展名
        ext = '.mp3'  # 默认
        content_type = response.headers.get('content-type', '').lower()
        if 'mp3' in content_type:
            ext = '.mp3'
        elif 'm4a' in content_type or 'mp4' in content_type:
            ext = '.m4a'
        elif 'ogg' in content_type:
            ext = '.ogg'
        elif 'wav' in content_type:
            ext = '.wav'
        
        output_path = output_dir / f"{filename}{ext}"
        
        # 如果文件已存在，添加编号
        counter = 1
        while output_path.exists():
            output_path = output_dir / f"{filename}_{counter}{ext}"
            counter += 1
        
        start_time = time.time()
        downloaded_size = 0
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # 更新进度：15% - 30%
                    if total_size > 0:
                        download_percent = (downloaded_size / total_size) * 100
                        progress = 15 + int((downloaded_size / total_size) * 15)
                        elapsed_time = time.time() - start_time
                        if elapsed_time > 0:
                            speed = downloaded_size / elapsed_time
                            speed_mb = speed / 1024 / 1024
                            message = f'正在下载音频: {download_percent:.1f}% ({speed_mb:.1f} MB/s)'
                        else:
                            message = f'正在下载音频: {download_percent:.1f}%'
                        update_progress(task_id, 'download', progress, message)
        
        audio_file = str(output_path)
        update_progress(task_id, 'download', 30, '✓ 音频下载完成')
        time.sleep(0.5)
        
        # 获取音频时长和预计转录时间
        from src.transcribe_audio import get_audio_duration, estimate_transcription_time
        import torch
        
        audio_duration = get_audio_duration(audio_file)
        # 检测设备
        device = "cpu"
        try:
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = "cpu"  # WhisperX不支持MPS
        except:
            pass
        
        estimated_time = estimate_transcription_time(audio_duration, model_name, device)
        
        # 存储预计时长信息
        tasks[task_id]['audio_duration'] = audio_duration
        tasks[task_id]['estimated_transcription_time'] = estimated_time
        
        duration_str = f"{int(audio_duration//60)}分{int(audio_duration%60)}秒"
        est_time_str = f"{int(estimated_time//60)}分{int(estimated_time%60)}秒"
        update_progress(task_id, 'transcribe', 35, f'音频时长: {duration_str}，预计转录时间: {est_time_str}')
        
        # 步骤2: 转录（使用分块转录）
        def transcription_progress(current, total, message):
            # 转录进度：35% - 70%
            progress = 35 + int((current / total) * 35)
            update_progress(task_id, 'transcribe', progress, message)
        
        # 获取 HF_TOKEN 用于说话人检测
        hf_token = os.getenv("HF_TOKEN") if enable_diarize else None
        if enable_diarize and not hf_token:
            update_progress(task_id, 'transcribe', 40, '⚠️ 说话人检测需要 HF_TOKEN，跳过说话人检测...')
            enable_diarize = False
        
        # 进行说话人检测
        if enable_diarize:
            update_progress(task_id, 'transcribe', 70, '正在进行说话人分离...')
        
        result = transcribe_audio(
            audio_file,
            model_name=model_name,
            language=language if language else None,
            output_dir=str(output_dir),
            diarize=enable_diarize,
            hf_token=hf_token,
            enable_chunking=True,  # 启用分块转录
            chunk_duration=60.0,   # 每块60秒
            max_workers=4,         # 4个并发线程
            progress_callback=transcription_progress
        )
        
        update_progress(task_id, 'transcribe', 65, '✓ 转录完成，正在提取文本...')
        
        # 提取转录文本和段落信息
        transcript_text = ''
        segments_data = []
        total_segments = len(result.get('segments', []))
        has_speakers = False
        
        if total_segments > 0:
            for idx, segment in enumerate(result.get('segments', [])):
                text = segment.get('text', '').strip()
                transcript_text += text + ' '
                
                # 提取段落信息
                segment_info = {
                    'text': text,
                    'start': segment.get('start', 0),
                    'end': segment.get('end', 0),
                    'speaker': segment.get('speaker', '')
                }
                segments_data.append(segment_info)
                
                if segment.get('speaker'):
                    has_speakers = True
                
                if idx % 5 == 0 or idx == total_segments - 1:
                    progress = 65 + int((idx / total_segments) * 5)
                    update_progress(task_id, 'transcribe', 
                                   progress,
                                   f'正在提取文本: {idx + 1}/{total_segments} 段落 ({(idx + 1) / total_segments * 100:.1f}%)')
        else:
            transcript_text = ''
        
        tasks[task_id]['transcript'] = transcript_text.strip()
        tasks[task_id]['segments'] = segments_data
        tasks[task_id]['has_speakers'] = has_speakers
        
        # 保存转录文本文件
        base_name = Path(audio_file).stem
        transcript_txt_file = output_dir / f"{base_name}_transcript.txt"
        with open(transcript_txt_file, 'w', encoding='utf-8') as f:
            if has_speakers:
                # 带说话人信息的格式
                for seg in segments_data:
                    speaker = seg.get('speaker', '')
                    text = seg.get('text', '').strip()
                    if speaker:
                        f.write(f"[{speaker}] {text}\n")
                    else:
                        f.write(f"{text}\n")
            else:
                # 简单文本格式
                for seg in segments_data:
                    f.write(f"{seg.get('text', '').strip()}\n")
        tasks[task_id]['transcript_file'] = str(transcript_txt_file)
        
        # 生成PDF文件
        transcript_pdf_file = output_dir / f"{base_name}_transcript.pdf"
        
        # 如果启用了翻译，生成双语PDF
        if enable_translate:
            try:
                update_progress(task_id, 'transcribe', 72, f'正在翻译文本到 {translate_lang}...')
                
                # 提取所有文本用于翻译
                texts_to_translate = [seg.get('text', '').strip() for seg in segments_data]
                
                # 并行翻译
                print(f"开始翻译 {len(texts_to_translate)} 条文本到 {translate_lang}...")
                translated_texts = translate_list_parallel(
                    texts_to_translate,
                    dest=translate_lang,
                    batch_size=15,
                    max_workers=5
                )
                
                # 验证翻译结果
                if not translated_texts or len(translated_texts) != len(texts_to_translate):
                    print(f"⚠ 翻译结果数量不匹配: 期望 {len(texts_to_translate)}, 实际 {len(translated_texts) if translated_texts else 0}")
                    # 如果翻译失败，使用原文
                    translated_texts = texts_to_translate
                
                # 打印前几条翻译结果用于调试
                if translated_texts:
                    print(f"翻译示例（前3条）:")
                    for i in range(min(3, len(translated_texts))):
                        print(f"  原文: {texts_to_translate[i][:50]}...")
                        print(f"  翻译: {translated_texts[i][:50]}...")
                
                update_progress(task_id, 'transcribe', 73, '✓ 翻译完成，正在生成双语PDF...')
                
                # 生成双语PDF
                generate_transcript_pdf_with_translation(
                    segments_data,
                    translated_texts,
                    str(transcript_pdf_file),
                    has_speakers=has_speakers,
                    title=f"转录文本（含翻译） - {base_name}"
                )
                
                # 确保文件存在并存储绝对路径
                if os.path.exists(transcript_pdf_file):
                    tasks[task_id]['transcript_pdf_file'] = str(os.path.abspath(transcript_pdf_file))
                    print(f"✓ 双语PDF文件已生成并存储: {tasks[task_id]['transcript_pdf_file']}")
                else:
                    print(f"⚠ PDF文件生成失败，文件不存在: {transcript_pdf_file}")
                    tasks[task_id]['transcript_pdf_file'] = None
            except Exception as e:
                print(f"⚠ 翻译或生成双语PDF失败: {e}")
                import traceback
                traceback.print_exc()
                # 如果翻译失败，生成普通PDF
                try:
                    generate_transcript_pdf(
                        segments_data, 
                        str(transcript_pdf_file),
                        has_speakers=has_speakers,
                        title=f"转录文本 - {base_name}"
                    )
                    if os.path.exists(transcript_pdf_file):
                        tasks[task_id]['transcript_pdf_file'] = str(os.path.abspath(transcript_pdf_file))
                except Exception as e2:
                    print(f"⚠ 生成普通PDF也失败: {e2}")
                    tasks[task_id]['transcript_pdf_file'] = None
        else:
            # 生成普通PDF
            try:
                generate_transcript_pdf(
                    segments_data, 
                    str(transcript_pdf_file),
                    has_speakers=has_speakers,
                    title=f"转录文本 - {base_name}"
                )
                # 确保文件存在并存储绝对路径
                if os.path.exists(transcript_pdf_file):
                    tasks[task_id]['transcript_pdf_file'] = str(os.path.abspath(transcript_pdf_file))
                    print(f"✓ PDF文件已生成并存储: {tasks[task_id]['transcript_pdf_file']}")
                else:
                    print(f"⚠ PDF文件生成失败，文件不存在: {transcript_pdf_file}")
                    tasks[task_id]['transcript_pdf_file'] = None
            except Exception as e:
                print(f"⚠ 生成PDF失败: {e}")
                import traceback
                traceback.print_exc()
                tasks[task_id]['transcript_pdf_file'] = None
        
        speaker_msg = f'，检测到 {len(set([s["speaker"] for s in segments_data if s["speaker"]]))} 个说话人' if has_speakers else ''
        update_progress(task_id, 'transcribe', 70, f'✓ 文本提取完成 ({total_segments} 段落{speaker_msg})')
        time.sleep(0.5)
        
        # 步骤3: 总结（使用异步总结）
        update_progress(task_id, 'summarize', 75, '正在准备总结...')
        
        api_key = os.getenv("API_KEY_302_AI") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            tasks[task_id]['summary'] = "⚠️ 未设置API密钥，无法生成总结。请设置环境变量 API_KEY_302_AI 或 OPENAI_API_KEY"
            update_progress(task_id, 'summarize', 100, '⚠️ 跳过总结（缺少API密钥）')
        else:
            update_progress(task_id, 'summarize', 80, '正在分块文本（充分利用 GPT-4o 的 128k tokens 上下文）...')
            
            # 使用异步总结，充分利用 GPT-4o 的 128k tokens 上下文能力
            summary = summarize_text(
                text=transcript_text,
                api_key=api_key,
                chunk_size=100000,  # GPT-4o 支持 128k tokens，约等于 100k 字符
                chunk_overlap=300,  # 增大重叠以保持上下文连贯性
                enable_async=True,  # 启用异步并发
                max_workers=5,      # 5个并发线程
                show_progress=False
            )
            
            tasks[task_id]['summary'] = summary
            
            summary_file = output_dir / f"{base_name}_summary.txt"
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(summary)
            tasks[task_id]['summary_file'] = str(summary_file)
            
            update_progress(task_id, 'summarize', 100, '✓ 总结完成')
        
        tasks[task_id]['status'] = 'completed'
        update_progress(task_id, 'completed', 100, '✓ 全部完成！')
        
    except Exception as e:
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['error'] = str(e)
        update_progress(task_id, 'error', 0, f'❌ 错误: {str(e)}')
    
    finally:
        # 发送结束信号
        if task_id in progress_queues:
            progress_queues[task_id].put(None)


@app.route('/status/<task_id>')
def get_status(task_id):
    """获取任务状态"""
    if task_id not in tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    return jsonify(tasks[task_id])


@app.route('/stream/<task_id>')
def stream_progress(task_id):
    """SSE流式推送进度更新"""
    def generate():
        if task_id not in progress_queues:
            yield f"data: {json.dumps({'error': '任务不存在'})}\n\n"
            return
        
        queue_obj = progress_queues[task_id]
        while True:
            try:
                # 从队列获取进度更新
                message = queue_obj.get(timeout=1)
                if message is None:  # 结束信号
                    break
                yield f"data: {json.dumps(message)}\n\n"
            except queue.Empty:
                # 发送心跳保持连接
                yield f": heartbeat\n\n"
                continue
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route('/download/<task_id>/summary')
def download_summary(task_id):
    """下载总结文件"""
    if task_id not in tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    summary_file = tasks[task_id].get('summary_file')
    if not summary_file or not os.path.exists(summary_file):
        return jsonify({'error': '文件不存在'}), 404
    
    return send_file(summary_file, as_attachment=True)


@app.route('/download/<task_id>/transcript')
def download_transcript(task_id):
    """下载转录文本文件"""
    if task_id not in tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    transcript_file = tasks[task_id].get('transcript_file')
    if not transcript_file or not os.path.exists(transcript_file):
        return jsonify({'error': '文件不存在'}), 404
    
    return send_file(transcript_file, as_attachment=True)


@app.route('/download/<task_id>/transcript_pdf')
def download_transcript_pdf(task_id):
    """下载转录PDF文件"""
    if task_id not in tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    transcript_pdf_file = tasks[task_id].get('transcript_pdf_file')
    if not transcript_pdf_file:
        return jsonify({'error': 'PDF文件路径未设置'}), 404
    
    # 尝试使用绝对路径或相对路径
    pdf_path = transcript_pdf_file
    if not os.path.isabs(pdf_path):
        # 如果是相对路径，转换为绝对路径
        pdf_path = os.path.abspath(pdf_path)
    
    if not os.path.exists(pdf_path):
        print(f"⚠ PDF文件不存在: {pdf_path}")
        print(f"   任务中的路径: {transcript_pdf_file}")
        return jsonify({'error': f'PDF文件不存在: {pdf_path}'}), 404
    
    return send_file(pdf_path, as_attachment=True, mimetype='application/pdf')


if __name__ == '__main__':
    import socket
    
    # 尝试找到可用端口
    def find_free_port(start_port=5000, max_attempts=10):
        for port in range(start_port, start_port + max_attempts):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('127.0.0.1', port)) != 0:
                    return port
        return 5001  # 默认备用端口
    
    port = find_free_port()
    
    print("=" * 60)
    print("YouTube视频总结工具 - Web服务")
    print("=" * 60)
    print(f"\n访问地址: http://127.0.0.1:{port}")
    print("\n注意事项:")
    print("1. 确保已设置API密钥 (API_KEY_302_AI 或 OPENAI_API_KEY)")
    print("2. 首次使用需要下载转录模型")
    print("3. 处理时间取决于视频长度和选择的模型")
    print("\n按 Ctrl+C 停止服务")
    print("=" * 60)
    
    app.run(host='127.0.0.1', port=port, debug=True)

