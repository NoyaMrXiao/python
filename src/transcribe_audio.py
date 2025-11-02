"""
使用WhisperX將音頻轉換為文本
支持詞級別時間戳和說話人分離（diarization）
支持分塊轉錄加速和並發處理
"""
import warnings
# 抑制 torchaudio 弃用警告
warnings.filterwarnings('ignore', category=UserWarning, module='torchaudio')
warnings.filterwarnings('ignore', category=UserWarning, module='pyannote')

import whisperx
import gc
import os
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

# 抑制 WhisperX 对齐警告
logging.getLogger("whisperx.alignment").setLevel(logging.ERROR)


def get_audio_duration(audio_file: str) -> float:
    """
    获取音频文件的时长（秒）
    
    参数:
        audio_file (str): 音频文件路径
    
    返回:
        float: 音频时长（秒）
    """
    try:
        # 使用 ffprobe 获取音频时长
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return duration
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as e:
        # 如果 ffprobe 不可用，尝试使用 whisperx 加载音频来估算
        try:
            audio = whisperx.load_audio(audio_file)
            # 假设采样率为 16000 (whisperx 默认)
            duration = len(audio) / 16000.0
            return duration
        except Exception:
            print(f"⚠ 无法获取音频时长: {e}")
            return 0.0


def estimate_transcription_time(
    audio_duration: float,
    model_name: str = "base",
    device: str = "cpu"
) -> float:
    """
    估算转录所需时间（秒）
    
    参数:
        audio_duration (float): 音频时长（秒）
        model_name (str): 模型名称
        device (str): 设备类型
    
    返回:
        float: 估算的转录时间（秒）
    """
    # 不同模型的相对速度（相对于 base 模型）
    model_speeds = {
        "tiny": 0.3,    # 非常快
        "base": 1.0,    # 基准
        "small": 2.0,   # 较慢
        "medium": 4.0,  # 慢
        "large-v2": 6.0,
        "large-v3": 6.0
    }
    
    # 设备因子
    device_factors = {
        "cuda": 0.5,    # GPU 快 2 倍
        "cpu": 1.0,
        "mps": 0.8      # MPS 稍快
    }
    
    base_speed = model_speeds.get(model_name, 1.0)
    device_factor = device_factors.get(device, 1.0)
    
    # 转录时间通常是音频时长的 base_speed / device_factor 倍
    # 加上固定的模型加载和对齐时间（约 10-30 秒）
    overhead = 20.0  # 模型加载和对齐的固定开销
    
    transcription_time = (audio_duration * base_speed / device_factor) + overhead
    
    # 如果有分块处理，可以进一步优化（并发优势）
    return transcription_time


def split_audio_file(
    audio_file: str,
    chunk_duration: float = 60.0,
    output_dir: Optional[str] = None
) -> List[Tuple[str, float, float]]:
    """
    将音频文件按时间分割成多个块
    
    参数:
        audio_file (str): 输入音频文件路径
        chunk_duration (float): 每块的时长（秒），默认 60 秒
        output_dir (str, optional): 输出目录，默认为临时目录
    
    返回:
        List[Tuple[str, float, float]]: [(块文件路径, 开始时间, 结束时间), ...]
    """
    duration = get_audio_duration(audio_file)
    
    if duration == 0:
        # 如果无法获取时长，返回原文件
        return [(audio_file, 0.0, duration)]
    
    if duration <= chunk_duration:
        # 音频太短，不需要分割
        return [(audio_file, 0.0, duration)]
    
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(audio_file))
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    chunks = []
    base_name = Path(audio_file).stem
    chunk_index = 0
    
    start_time = 0.0
    
    while start_time < duration:
        end_time = min(start_time + chunk_duration, duration)
        
        # 使用 ffmpeg 切割音频
        chunk_file = os.path.join(output_dir, f"{base_name}_chunk_{chunk_index:04d}.wav")
        
        try:
            cmd = [
                'ffmpeg', '-i', audio_file,
                '-ss', str(start_time),
                '-t', str(end_time - start_time),
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                '-y',  # 覆盖已存在文件
                chunk_file
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            chunks.append((chunk_file, start_time, end_time))
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"⚠ 切割音频块失败: {e}")
            # 如果 ffmpeg 不可用，返回原文件
            if chunk_index == 0:
                return [(audio_file, 0.0, duration)]
            break
        
        start_time = end_time
        chunk_index += 1
    
    return chunks


def transcribe_chunk(
    chunk_file: str,
    chunk_start: float,
    model,
    model_name: str,
    device: str,
    batch_size: int,
    language: Optional[str],
    align_model: Optional[Any],
    align_metadata: Optional[Any],
    audio_data: Any
) -> Dict[str, Any]:
    """
    转录单个音频块
    
    参数:
        chunk_file (str): 音频块文件路径
        chunk_start (float): 块的起始时间（用于调整时间戳）
        model: WhisperX 模型对象
        model_name (str): 模型名称
        device (str): 设备类型
        batch_size (int): 批次大小
        language (str, optional): 语言代码
        align_model: 对齐模型
        align_metadata: 对齐元数据
        audio_data: 音频数据
    
    返回:
        dict: 转录结果
    """
    try:
        # 加载音频块
        chunk_audio = whisperx.load_audio(chunk_file)
        
        # 转录
        result = model.transcribe(chunk_audio, batch_size=batch_size, language=language)
        
        # 调整时间戳（加上块的起始时间）
        for segment in result['segments']:
            segment['start'] += chunk_start
            segment['end'] += chunk_start
            
            # 调整词级时间戳
            if 'words' in segment:
                for word in segment['words']:
                    word['start'] += chunk_start
                    word['end'] += chunk_start
        
        # 对齐时间戳（如果提供了对齐模型）
        if align_model and align_metadata:
            try:
                # 过滤掉空文本或无效的段落
                valid_segments = [
                    seg for seg in result["segments"]
                    if seg.get('text', '').strip() and len(seg.get('text', '').strip()) > 0
                ]
                
                if valid_segments:
                    aligned_result = whisperx.align(
                        valid_segments,
                        align_model,
                        align_metadata,
                        chunk_audio,
                        device,
                        return_char_alignments=False
                    )
                    
                    # 使用对齐后的结果
                    result['segments'] = aligned_result.get('segments', valid_segments)
                else:
                    # 如果没有有效段落，保持原结果
                    pass
                    
            except Exception as align_error:
                # 对齐失败时，保持原始转录结果（不带词级时间戳）
                print(f"⚠ 对齐失败，使用原始转录结果: {align_error}")
                # 移除可能存在的无效词级时间戳
                for segment in result['segments']:
                    if 'words' in segment:
                        # 只保留有效的词级时间戳
                        segment['words'] = [
                            w for w in segment.get('words', [])
                            if w.get('word', '').strip() and w.get('start', 0) >= 0 and w.get('end', 0) > w.get('start', 0)
                        ]
            
            # 调整对齐后的时间戳
            for segment in result.get('segments', []):
                segment['start'] += chunk_start
                segment['end'] += chunk_start
                if 'words' in segment:
                    for word in segment['words']:
                        word['start'] += chunk_start
                        word['end'] += chunk_start
        
        return result
    except Exception as e:
        print(f"⚠ 转录块失败 {chunk_file}: {e}")
        return {'segments': [], 'language': language or 'unknown'}


def merge_transcription_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    合并多个转录结果
    
    参数:
        results (List[Dict[str, Any]]): 多个转录结果列表
    
    返回:
        dict: 合并后的转录结果
    """
    if not results:
        return {'segments': [], 'language': 'unknown'}
    
    merged = {
        'segments': [],
        'language': results[0].get('language', 'unknown')
    }
    
    # 按时间戳排序并合并所有段落
    all_segments = []
    for result in results:
        all_segments.extend(result.get('segments', []))
    
    # 按开始时间排序
    all_segments.sort(key=lambda x: x.get('start', 0))
    
    merged['segments'] = all_segments
    return merged


def transcribe_audio(
    audio_file: str,
    model_name: str = "base",
    device: str = "auto",
    compute_type: str = "auto",
    batch_size: int = 16,  # M系列芯片可以使用更大的batch_size（如32-64）獲得更好性能
    language: Optional[str] = None,
    diarize: bool = False,
    hf_token: Optional[str] = None,
    output_dir: Optional[str] = None,
    highlight_words: bool = False,
    enable_chunking: bool = True,
    chunk_duration: float = 60.0,
    max_workers: int = 4,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Dict[str, Any]:
    """
    使用WhisperX轉錄音頻文件
    
    參數:
        audio_file (str): 音頻文件路徑
        model_name (str): Whisper模型名稱 (tiny/base/small/medium/large-v2/large-v3)
        device (str): 計算設備 ("cpu", "cuda", "auto") - 注意：WhisperX目前不支持MPS設備
        compute_type (str): 計算類型 ("float16", "int8", "auto")
        batch_size (int): 批次大小（降低以減少GPU內存使用）
        language (str, optional): 語言代碼（如 "en", "zh", "de"），None為自動檢測
        diarize (bool): 是否進行說話人分離
        hf_token (str, optional): HuggingFace token（用於說話人分離）
        output_dir (str, optional): 輸出目錄，默認為音頻文件所在目錄
        highlight_words (bool): 是否在SRT文件中高亮詞級時間戳
        enable_chunking (bool): 是否啟用分塊轉錄加速，默認為 True
        chunk_duration (float): 每塊的時長（秒），默認為 60.0
        max_workers (int): 並發轉錄的最大線程數，默認為 4
        progress_callback (callable, optional): 進度回調函數，接收 (current, total, message) 參數
    
    返回:
        dict: 包含轉錄結果的字典，包含 'duration' 和 'estimated_time' 字段
    """
    # 檢查文件是否存在
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"音頻文件不存在: {audio_file}")
    
    # 自動檢測設備
    if device == "auto":
        try:
            import torch
            # 注意：WhisperX目前不支持MPS設備，所以跳過MPS檢測
            # 優先檢測CUDA（NVIDIA GPU）
            if torch.cuda.is_available():
                device = "cuda"
                print("✓ 檢測到CUDA GPU，使用GPU加速")
            # 對於Apple Silicon，雖然有MPS，但WhisperX不支持，所以使用CPU
            # 但可以使用更大的batch_size和優化的計算類型來提升性能
            else:
                device = "cpu"
                # 檢查是否為Apple Silicon
                if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    print("ℹ️  檢測到Apple Silicon，雖然WhisperX不支持MPS，但已優化CPU設置")
                    print("💡 提示：M系列芯片使用CPU模式，建議使用較小的模型（base/small）獲得更好性能")
                else:
                    print("⚠ 未檢測到GPU，使用CPU（速度較慢）")
        except ImportError:
            device = "cpu"
            print("⚠ PyTorch未安裝，使用CPU")
    
    # 自動選擇計算類型
    if compute_type == "auto":
        if device == "cpu":
            # 對於Apple Silicon，即使使用CPU，也可以嘗試使用更快的設置
            import torch
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                # Apple Silicon的CPU性能很好，可以使用int8獲得更好性能
                compute_type = "int8"
            else:
                compute_type = "int8"
        else:
            compute_type = "float16"
    
    # 設置輸出目錄
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(audio_file))
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 获取音频时长
    audio_duration = get_audio_duration(audio_file)
    estimated_time = estimate_transcription_time(audio_duration, model_name, device)
    
    print(f"開始轉錄: {audio_file}")
    print(f"音頻時長: {audio_duration:.1f} 秒 ({audio_duration/60:.1f} 分鐘)")
    print(f"預計轉錄時間: {estimated_time:.1f} 秒 ({estimated_time/60:.1f} 分鐘)")
    print(f"模型: {model_name}")
    print(f"設備: {device}")
    print(f"計算類型: {compute_type}")
    
    try:
        # 檢查本地緩存
        cache_dir = os.path.expanduser('~/.cache/huggingface/hub')
        model_repo = f"Systran/faster-whisper-{model_name}"
        model_cache_path = os.path.join(cache_dir, f"models--{model_repo.replace('/', '--')}")
        
        if os.path.exists(model_cache_path):
            print(f"✓ 發現本地模型緩存，使用緩存中的模型...")
            os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '300')
        
        # 決定是否使用分塊轉錄
        should_chunk = enable_chunking and audio_duration > chunk_duration * 1.5  # 只有當時長超過1.5倍塊大小時才分塊
        
        if should_chunk:
            print(f"\n[使用分塊轉錄] 音頻時長 {audio_duration:.1f} 秒，將分塊處理...")
            
            # 1. 切割音頻
            if progress_callback:
                progress_callback(0, 100, "正在切割音頻文件...")
            chunks = split_audio_file(audio_file, chunk_duration, output_dir)
            print(f"✓ 已切割成 {len(chunks)} 個塊")
            
            if progress_callback:
                progress_callback(10, 100, f"已切割成 {len(chunks)} 個塊，開始並發轉錄...")
            
            # 2. 加載模型（共享模型對象，但需要注意線程安全）
            print("\n[1/3] 正在加載模型...")
            model = None
            try:
                model = whisperx.load_model(model_name, device, compute_type=compute_type)
            except Exception as load_error:
                error_str = str(load_error).lower()
                if ('ssl' in error_str or 'connection' in error_str or 'network' in error_str) and os.path.exists(model_cache_path):
                    print("⚠ 網絡連接失敗，嘗試離線模式使用本地緩存...")
                    os.environ['HF_HUB_OFFLINE'] = '1'
                    try:
                        model = whisperx.load_model(model_name, device, compute_type=compute_type)
                        os.environ.pop('HF_HUB_OFFLINE', None)
                        print("✓ 成功使用本地緩存模型")
                    except Exception as offline_error:
                        os.environ.pop('HF_HUB_OFFLINE', None)
                        raise Exception(f"無法從本地緩存加載模型: {offline_error}. 原始錯誤: {load_error}")
                else:
                    raise
            
            # 3. 先轉錄第一個塊來檢測語言（如果未指定）
            detected_language = language
            if not detected_language and chunks:
                first_chunk_audio = whisperx.load_audio(chunks[0][0])
                first_result = model.transcribe(first_chunk_audio, batch_size=batch_size)
                detected_language = first_result.get('language', 'unknown')
                print(f"檢測到的語言: {detected_language}")
            
            # 4. 加載對齊模型（如果需要對齊）
            model_a = None
            align_metadata = None
            if detected_language:
                try:
                    model_a, align_metadata = whisperx.load_align_model(
                        language_code=detected_language,
                        device=device
                    )
                except Exception as e:
                    print(f"⚠ 無法加載對齊模型: {e}，跳過詞級對齊")
                    model_a = None
                    align_metadata = None
            
            # 5. 並發轉錄所有塊
            print(f"\n[2/3] 正在並發轉錄 {len(chunks)} 個音頻塊（最大 {max_workers} 個線程）...")
            results = []
            chunk_files_to_cleanup = []
            
            # 使用線程池並發轉錄
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_chunk = {}
                
                for idx, (chunk_file, chunk_start, chunk_end) in enumerate(chunks):
                    chunk_files_to_cleanup.append(chunk_file)
                    future = executor.submit(
                        transcribe_chunk,
                        chunk_file,
                        chunk_start,
                        model,
                        model_name,
                        device,
                        batch_size,
                        detected_language,
                        model_a,
                        align_metadata,
                        None  # 不使用原音頻數據
                    )
                    future_to_chunk[future] = (idx, chunk_start)
                
                # 收集結果
                completed = 0
                for future in as_completed(future_to_chunk):
                    idx, chunk_start = future_to_chunk[future]
                    try:
                        chunk_result = future.result()
                        results.append(chunk_result)
                        completed += 1
                        
                        if progress_callback:
                            progress = 20 + int((completed / len(chunks)) * 50)
                            progress_callback(
                                progress,
                                100,
                                f"已轉錄 {completed}/{len(chunks)} 個塊 ({completed/len(chunks)*100:.1f}%)"
                            )
                        print(f"✓ 塊 {idx + 1}/{len(chunks)} 轉錄完成")
                    except Exception as e:
                        print(f"⚠ 塊 {idx + 1} 轉錄失敗: {e}")
            
            # 清理臨時文件
            for chunk_file in chunk_files_to_cleanup:
                try:
                    if chunk_file != audio_file and os.path.exists(chunk_file):
                        os.remove(chunk_file)
                except Exception as e:
                    print(f"⚠ 清理臨時文件失敗 {chunk_file}: {e}")
            
            # 6. 合併結果
            print("\n[3/3] 正在合併轉錄結果...")
            result = merge_transcription_results(results)
            result['language'] = detected_language or 'unknown'
            
            # 清理模型內存
            if device == "cuda":
                gc.collect()
                import torch
                torch.cuda.empty_cache()
            
            if model:
                del model
            if model_a:
                del model_a
            
            print(f"合併後的段落數: {len(result['segments'])}")
            
            # 7. 說話人分離（如果啟用，需要在完整音頻上進行）
            if diarize:
                if hf_token is None:
                    print("⚠ 警告: 需要HuggingFace token才能進行說話人分離")
                    diarize = False
                else:
                    print("\n[4/4] 正在進行說話人分離（需要在完整音頻上執行）...")
                    from whisperx.diarize import DiarizationPipeline
                    
                    audio = whisperx.load_audio(audio_file)
                    diarize_model = DiarizationPipeline(
                        use_auth_token=hf_token,
                        device=device
                    )
                    diarize_segments = diarize_model(audio)
                    result = whisperx.assign_word_speakers(diarize_segments, result)
                    
                    print(f"檢測到的說話人數量: {len(set([seg.get('speaker', 'UNKNOWN') for seg in diarize_segments]))}")
            
        else:
            # 使用原有方法（不分塊）
            print("\n[使用傳統方法] 音頻較短或未啟用分塊，使用完整轉錄...")
            
            # 1. 加載模型並轉錄
            print("\n[1/3] 正在加載模型並轉錄...")
            
        model = None
        try:
            model = whisperx.load_model(model_name, device, compute_type=compute_type)
        except Exception as load_error:
            error_str = str(load_error).lower()
            if ('ssl' in error_str or 'connection' in error_str or 'network' in error_str) and os.path.exists(model_cache_path):
                print("⚠ 網絡連接失敗，嘗試離線模式使用本地緩存...")
                os.environ['HF_HUB_OFFLINE'] = '1'
                try:
                    model = whisperx.load_model(model_name, device, compute_type=compute_type)
                    os.environ.pop('HF_HUB_OFFLINE', None)
                    print("✓ 成功使用本地緩存模型")
                except Exception as offline_error:
                    os.environ.pop('HF_HUB_OFFLINE', None)
                    raise Exception(f"無法從本地緩存加載模型: {offline_error}. 原始錯誤: {load_error}")
            else:
                raise
        
        audio = whisperx.load_audio(audio_file)
        result = model.transcribe(audio, batch_size=batch_size, language=language)
        
        print(f"檢測到的語言: {result['language']}")
        print(f"轉錄段落數: {len(result['segments'])}")
        
        # 清理模型內存（如果使用GPU）
        if device == "cuda":
            gc.collect()
            import torch
            torch.cuda.empty_cache()
            del model
        
        # 2. 對齊時間戳（詞級別）
        print("\n[2/3] 正在對齊詞級時間戳...")
        model_a = None
        try:
            model_a, metadata = whisperx.load_align_model(
                language_code=result["language"], 
                device=device
            )
            
            # 过滤掉空文本或无效的段落
            valid_segments = [
                seg for seg in result["segments"]
                if seg.get('text', '').strip() and len(seg.get('text', '').strip()) > 0
            ]
            
            if valid_segments:
                aligned_result = whisperx.align(
                    valid_segments, 
                    model_a, 
                    metadata, 
                    audio, 
                    device,
                    return_char_alignments=False
                )
                
                # 合并对齐后的段落和未对齐的段落
                aligned_segments = aligned_result.get('segments', [])
                aligned_texts = {seg.get('text', '').strip() for seg in aligned_segments if seg.get('text', '').strip()}
                
                # 保留无法对齐的段落（没有文本匹配的）
                for seg in result["segments"]:
                    if seg.get('text', '').strip() not in aligned_texts:
                        aligned_segments.append(seg)
                
                result['segments'] = aligned_segments
                print(f"✓ 對齊完成: {len([s for s in aligned_segments if 'words' in s])} 個段落有詞級時間戳")
            else:
                print("⚠ 沒有有效段落需要對齊")
                
        except Exception as align_error:
            print(f"⚠ 對齊過程出錯，使用原始轉錄結果: {align_error}")
            # 保持原始结果，不影响后续处理
            pass
        
        print(f"對齊後的段落數: {len(result.get('segments', []))}")
        
        # 清理對齊模型內存
        if model_a:
            if device == "cuda":
                gc.collect()
                import torch
                torch.cuda.empty_cache()
            
            try:
                del model_a
            except:
                pass
        
        # 3. 說話人分離（可選）
        if diarize:
            if hf_token is None:
                print("⚠ 警告: 需要HuggingFace token才能進行說話人分離")
                print("   設置環境變量 HF_TOKEN 或傳入 hf_token 參數")
                diarize = False
        
        if diarize:
            print("\n[3/3] 正在進行說話人分離...")
            from whisperx.diarize import DiarizationPipeline
            
            diarize_model = DiarizationPipeline(
                use_auth_token=hf_token,
                device=device
            )
            diarize_segments = diarize_model(audio)
            result = whisperx.assign_word_speakers(diarize_segments, result)
            
            print(f"檢測到的說話人數量: {len(set([seg.get('speaker', 'UNKNOWN') for seg in diarize_segments]))}")
        else:
            print("\n[3/3] 跳過說話人分離")
        
        # 保存結果
        base_name = Path(audio_file).stem
        output_path = save_transcription_result(
            result, 
            output_dir, 
            base_name,
            highlight_words=highlight_words
        )
        
        result['output_file'] = output_path
        result['duration'] = audio_duration
        result['estimated_time'] = estimated_time
        
        print(f"\n✓ 轉錄完成！")
        print(f"輸出文件: {output_path}")
        
        return result
        
    except Exception as e:
        print(f"❌ 轉錄錯誤: {e}")
        raise


def save_transcription_result(
    result: Dict[str, Any],
    output_dir: str,
    base_name: str,
    highlight_words: bool = False
) -> str:
    """
    保存轉錄結果為多種格式
    
    參數:
        result: WhisperX轉錄結果
        output_dir: 輸出目錄
        base_name: 基礎文件名
        highlight_words: 是否在SRT中高亮詞級時間戳
    
    返回:
        str: 主要輸出文件路徑
    """
    output_dir = Path(output_dir)
    
    # 1. 保存為文本文件
    txt_file = output_dir / f"{base_name}_transcript.txt"
    with open(txt_file, 'w', encoding='utf-8') as f:
        for segment in result['segments']:
            text = segment.get('text', '').strip()
            if text:
                f.write(text + '\n')
    
    # 2. 保存為SRT字幕文件
    srt_file = output_dir / f"{base_name}_transcript.srt"
    with open(srt_file, 'w', encoding='utf-8') as f:
        for idx, segment in enumerate(result['segments'], 1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            
            # 獲取說話人標籤（如果有的話）
            speaker = segment.get('speaker', '')
            text = segment.get('text', '').strip()
            
            f.write(f"{idx}\n")
            f.write(f"{start} --> {end}\n")
            if speaker:
                f.write(f"[{speaker}] {text}\n")
            else:
                f.write(f"{text}\n")
            f.write("\n")
            
            # 如果有詞級時間戳且啟用高亮
            if highlight_words and 'words' in segment:
                for word_info in segment['words']:
                    word = word_info.get('word', '')
                    word_start = format_timestamp(word_info.get('start', 0))
                    word_end = format_timestamp(word_info.get('end', 0))
                    f.write(f"{idx}.{word_info.get('id', 0)}\n")
                    f.write(f"{word_start} --> {word_end}\n")
                    f.write(f"<font color=\"#ffff00\">{word}</font>\n")
                    f.write("\n")
    
    # 3. 保存為JSON文件（完整信息）
    import json
    json_file = output_dir / f"{base_name}_transcript.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return str(txt_file)


def format_timestamp(seconds: float) -> str:
    """將秒數格式化為SRT時間戳格式 (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def transcribe_audio_simple(audio_file: str, model_name: str = "base") -> Dict[str, Any]:
    """
    簡單版本：使用默認設置轉錄音頻
    
    參數:
        audio_file (str): 音頻文件路徑
        model_name (str): Whisper模型名稱
    
    返回:
        dict: 轉錄結果
    """
    return transcribe_audio(audio_file, model_name=model_name)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法: python transcribe_audio.py <音頻文件> [模型名稱]")
        print("示例: python transcribe_audio.py audio.mp3 base")
        print("模型選項: tiny, base, small, medium, large-v2, large-v3")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    model_name = sys.argv[2] if len(sys.argv) > 2 else "base"
    
    # 從環境變量獲取HuggingFace token
    hf_token = os.getenv("HF_TOKEN")
    
    print("=" * 60)
    print("WhisperX 音頻轉文本")
    print("=" * 60)
    
    try:
        result = transcribe_audio(
            audio_file,
            model_name=model_name,
            diarize=False,  # 如果需要說話人分離，設置為True並提供HF_TOKEN
            hf_token=hf_token
        )
        
        print(f"\n轉錄摘要:")
        print(f"- 語言: {result.get('language', 'Unknown')}")
        print(f"- 段落數: {len(result.get('segments', []))}")
        
        # 顯示前幾個段落
        print(f"\n前3個段落預覽:")
        for i, segment in enumerate(result.get('segments', [])[:3], 1):
            print(f"{i}. [{format_timestamp(segment['start'])} - {format_timestamp(segment['end'])}]")
            print(f"   {segment.get('text', '').strip()}")
        
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()

