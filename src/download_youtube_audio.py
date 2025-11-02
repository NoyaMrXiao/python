"""
下載YouTube視頻的音頻到本地
使用yt-dlp庫來下載音頻
"""
import yt_dlp
import os
from pathlib import Path


def download_youtube_audio(url, output_dir=None, filename=None, progress_hook=None):
    """
    下載YouTube視頻的音頻到本地
    
    參數:
        url (str): YouTube視頻URL
        output_dir (str, optional): 輸出目錄，默認為當前目錄下的 'downloads' 文件夾
        filename (str, optional): 輸出文件名（不含擴展名），如果為None則使用視頻標題
        progress_hook (callable, optional): 進度回調函數，接收字典參數包含下載進度信息
    
    返回:
        str: 下載的音頻文件路徑，如果失敗則返回None
    """
    # 設置輸出目錄
    if output_dir is None:
        output_dir = os.path.join(os.getcwd(), 'downloads')
    
    # 創建輸出目錄（如果不存在）
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 定義進度回調函數
    def default_progress_hook(d):
        if progress_hook:
            progress_hook(d)
        # 保持原有打印輸出（當沒有自定義回調時）
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                percent = (downloaded / total) * 100
                speed = d.get('speed', 0)
                if speed:
                    speed_str = f"{speed/1024/1024:.1f}MB/s"
                else:
                    speed_str = "計算中..."
                print(f"\r下載進度: {percent:.1f}% ({speed_str})", end='', flush=True)
        elif d['status'] == 'finished':
            print(f"\n✓ 下載完成，正在轉換音頻格式...")
    
    # 配置yt-dlp選項
    ydl_opts = {
        'format': 'bestaudio/best',  # 選擇最佳音頻格式
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',  # 使用FFmpeg提取音頻
            'preferredcodec': 'mp3',      # 輸出為MP3格式
            'preferredquality': '192',    # 音質：192kbps
        }],
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),  # 輸出文件名模板
        'quiet': False,  # 顯示下載進度
        'no_warnings': False,
        'progress_hooks': [default_progress_hook],  # 添加進度回調
    }
    
    # 如果指定了自定義文件名，則使用它
    if filename:
        ydl_opts['outtmpl'] = os.path.join(output_dir, f'{filename}.%(ext)s')
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 獲取視頻信息（不下載）
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'Unknown')
            video_id = info.get('id', 'Unknown')
            
            print(f"正在下載: {video_title}")
            print(f"視頻ID: {video_id}")
            print(f"保存位置: {output_dir}")
            
            # 下載音頻
            ydl.download([url])
            
            # 查找剛下載的文件（查找最新的MP3文件）
            mp3_files = list(Path(output_dir).glob('*.mp3'))
            if mp3_files:
                # 按修改時間排序，獲取最新的文件
                latest_file = max(mp3_files, key=os.path.getmtime)
                print(f"✓ 下載完成: {latest_file}")
                return str(latest_file)
            else:
                print("⚠ 下載完成，但無法找到MP3輸出文件")
                # 嘗試查找其他音頻格式
                audio_files = list(Path(output_dir).glob('*.m4a')) + \
                             list(Path(output_dir).glob('*.opus')) + \
                             list(Path(output_dir).glob('*.webm'))
                if audio_files:
                    latest_file = max(audio_files, key=os.path.getmtime)
                    print(f"⚠ 找到音頻文件（非MP3格式）: {latest_file}")
                    return str(latest_file)
                return None
                    
    except yt_dlp.utils.DownloadError as e:
        print(f"❌ 下載錯誤: {e}")
        return None
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
        return None


def download_youtube_audio_simple(url):
    """
    簡單版本：使用默認設置下載音頻
    
    參數:
        url (str): YouTube視頻URL
    
    返回:
        str: 下載的音頻文件路徑，如果失敗則返回None
    """
    return download_youtube_audio(url)


if __name__ == "__main__":
    # 測試下載
    video_url = "https://www.youtube.com/watch?v=oOylEw3tPQ8&t=330s"
    
    print("=" * 50)
    print("YouTube 音頻下載器")
    print("=" * 50)
    
    # 方法1: 使用默認設置
    result = download_youtube_audio_simple(video_url)
    
    if result:
        print(f"\n成功！音頻文件已保存到: {result}")
    else:
        print("\n下載失敗，請檢查URL或網絡連接")
        print("\n注意：需要安裝FFmpeg才能提取音頻")
        print("macOS安裝: brew install ffmpeg")
        print("Linux安裝: sudo apt-get install ffmpeg")
        print("Windows: 從 https://ffmpeg.org/download.html 下載")

