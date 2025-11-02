"""
生成包含需求文檔和流程圖的PDF文件
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
import os

def register_fonts():
    """註冊中文字體"""
    # 嘗試註冊常見的中文字體
    font_paths = [
        '/System/Library/Fonts/STHeiti Light.ttc',  # macOS 系統字體
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STSong.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux fallback
        '/Windows/Fonts/simsun.ttc',  # Windows 字體
    ]
    
    # 如果找不到中文字體，使用默認字體
    try:
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                    print(f"成功註冊字體: {font_path}")
                    return 'ChineseFont'
                except:
                    continue
    except:
        pass
    
    print("警告: 未找到中文字體，使用默認字體（可能無法正確顯示中文）")
    return 'Helvetica'

def create_pdf():
    """創建PDF文檔"""
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    output_dir = os.path.join(project_root, 'outputs')
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, '需求文檔與流程圖.pdf')
    doc = SimpleDocTemplate(output_file, pagesize=A4)
    story = []
    
    # 註冊字體
    chinese_font = register_fonts()
    base_font = chinese_font if chinese_font != 'Helvetica' else 'Helvetica'
    
    # 創建樣式
    styles = getSampleStyleSheet()
    
    # 標題樣式
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName=base_font,
        leading=32
    )
    
    heading1_style = ParagraphStyle(
        'CustomHeading1',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        spaceBefore=24,
        fontName=base_font,
        leading=24
    )
    
    heading2_style = ParagraphStyle(
        'CustomHeading2',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=10,
        spaceBefore=18,
        fontName=base_font,
        leading=20
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        spaceAfter=12,
        alignment=TA_JUSTIFY,
        fontName=base_font,
        leading=16
    )
    
    bullet_style = ParagraphStyle(
        'CustomBullet',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        spaceAfter=8,
        leftIndent=20,
        fontName=base_font,
        leading=16
    )
    
    # 添加標題
    story.append(Paragraph("Web/Mobile 應用需求文檔與流程圖", title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # 讀取需求文檔並添加到PDF
    # 使用實際的文件名
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    doc_file = os.path.join(project_root, 'docs', '需求文档.md')
    with open(doc_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
        
        # 檢測標題級別
        if line.startswith('# '):
            text = line[2:].strip()
            story.append(Paragraph(text, heading1_style))
            story.append(Spacer(1, 0.3*cm))
        elif line.startswith('## '):
            text = line[3:].strip()
            story.append(Paragraph(text, heading2_style))
            story.append(Spacer(1, 0.2*cm))
        elif line.startswith('### '):
            text = line[4:].strip()
            story.append(Paragraph(f"<b>{text}</b>", heading2_style))
            story.append(Spacer(1, 0.15*cm))
        elif line.startswith('**'):
            # 粗體文本（功能描述等）
            text = line.replace('**', '').strip()
            if text:
                story.append(Paragraph(f"<b>{text}</b>", normal_style))
        elif line.startswith('- '):
            # 列表項
            text = line[2:].strip()
            story.append(Paragraph(f"• {text}", bullet_style))
        elif line.startswith('---'):
            # 分隔線
            story.append(Spacer(1, 0.5*cm))
        else:
            # 普通段落
            if line:
                # 處理特殊格式
                text = line.replace('**', '').strip()
                story.append(Paragraph(text, normal_style))
        
        i += 1
    
    # 添加分頁
    story.append(PageBreak())
    
    # 添加流程圖標題
    story.append(Paragraph("用戶流程圖", heading1_style))
    story.append(Spacer(1, 0.5*cm))
    
    # 添加流程圖圖片
    flowchart_path = os.path.join(project_root, 'outputs', 'user_flowchart.png')
    if os.path.exists(flowchart_path):
        # 獲取圖片尺寸並調整大小以適應頁面
        img = Image(flowchart_path)
        img_width, img_height = img.imageWidth, img.imageHeight
        
        # 計算縮放比例以適應A4頁面（留邊距）
        page_width = A4[0] - 2*cm
        page_height = A4[1] - 4*cm
        
        scale_w = page_width / img_width
        scale_h = page_height / img_height
        scale = min(scale_w, scale_h, 1.0)  # 不放大，只縮小
        
        img_width = img_width * scale
        img_height = img_height * scale
        
        img = Image(flowchart_path, width=img_width, height=img_height)
        story.append(img)
    else:
        story.append(Paragraph("流程图图片未找到，请先运行 generate_flowchart.py 生成流程图", normal_style))
    
    # 生成PDF
    doc.build(story)
    print(f"PDF已生成: {output_file}")

if __name__ == "__main__":
    create_pdf()

