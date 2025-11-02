"""
完整的YouTube視頻轉文本流程
結合下載和轉錄功能
"""
import os
import sys
from pathlib import Path
from typing import Optional
from download_youtube_audio import download_youtube_audio
from transcribe_audio import transcribe_audio


def youtube_to_text(
    url: str,
    model_name: str = "base",
    device: str = "auto",
    batch_size: int = 16,
    language: Optional[str] = None,
    diarize: bool = False,
    hf_token: Optional[str] = None,
    output_dir: Optional[str] = None,
    keep_audio: bool = False
) -> dict:
    """
    完整流程：從YouTube URL下載音頻並轉換為文本
    
    參數:
        url (str): YouTube視頻URL
        model_name (str): Whisper模型名稱
        device (str): 計算設備
        batch_size (int): 批次大小
        language (str, optional): 語言代碼
        diarize (bool): 是否進行說話人分離
        hf_token (str, optional): HuggingFace token
        output_dir (str, optional): 輸出目錄
        keep_audio (bool): 是否保留下載的音頻文件
    
    返回:
        dict: 轉錄結果
    """
    print("=" * 60)
    print("YouTube 視頻轉文本流程")
    print("=" * 60)
    
    # 步驟1: 下載音頻
    print("\n[步驟 1/2] 正在下載YouTube音頻...")
    audio_file = download_youtube_audio(url, output_dir=output_dir)
    
    if not audio_file:
        raise Exception("音頻下載失敗")
    
    # 步驟2: 轉錄音頻
    print("\n[步驟 2/2] 正在轉錄音頻為文本...")
    result = transcribe_audio(
        audio_file,
        model_name=model_name,
        device=device,
        batch_size=batch_size,
        language=language,
        diarize=diarize,
        hf_token=hf_token,
        output_dir=output_dir
    )
    
    # 可選：刪除音頻文件
    if not keep_audio and os.path.exists(audio_file):
        try:
            os.remove(audio_file)
            print(f"\n已刪除臨時音頻文件: {audio_file}")
        except:
            print(f"\n⚠ 無法刪除音頻文件: {audio_file}")
    
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python youtube_to_text.py <YouTube_URL> [模型名稱]")
        print("示例: python youtube_to_text.py https://www.youtube.com/watch?v=VIDEO_ID base")
        sys.exit(1)
    
    url = sys.argv[1]
    model_name = sys.argv[2] if len(sys.argv) > 2 else "base"
    hf_token = os.getenv("HF_TOKEN")
    
    try:
        result = youtube_to_text(
            url,
            model_name=model_name,
            diarize=False,  # 設置為True並提供HF_TOKEN以啟用說話人分離
            hf_token=hf_token,
            keep_audio=True  # 保留音頻文件
        )
        
        print("\n" + "=" * 60)
        print("流程完成！")
        print("=" * 60)
        print(f"\n輸出文件: {result.get('output_file', 'Unknown')}")
        
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()

