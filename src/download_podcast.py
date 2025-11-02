"""
下載播客音頻到本地
支持直接音頻URL下載和RSS feed解析下載
"""
import os
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, urljoin
import xml.etree.ElementTree as ET
import re


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除非法字符
    
    參數:
        filename (str): 原始文件名
    
    返回:
        str: 清理後的文件名
    """
    # 移除或替換非法字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 移除多餘的空白
    filename = ' '.join(filename.split())
    # 限制文件名長度
    if len(filename) > 200:
        filename = filename[:200]
    return filename


def get_file_extension_from_url(url: str) -> str:
    """
    從URL中提取文件擴展名
    
    參數:
        url (str): 文件URL
    
    返回:
        str: 文件擴展名（如 .mp3, .m4a 等）
    """
    parsed = urlparse(url)
    path = parsed.path
    if '.' in path:
        ext = os.path.splitext(path)[1].lower()
        # 只返回常見的音頻擴展名
        if ext in ['.mp3', '.m4a', '.mp4', '.ogg', '.wav', '.flac', '.aac', '.opus']:
            return ext
    return '.mp3'  # 默認擴展名


def download_audio_file(
    audio_url: str,
    output_path: str,
    show_progress: bool = True
) -> bool:
    """
    下載音頻文件到本地
    
    參數:
        audio_url (str): 音頻文件的URL
        output_path (str): 保存路徑（包含文件名）
        show_progress (bool): 是否顯示下載進度
    
    返回:
        bool: 下載是否成功
    """
    try:
        # 發送GET請求，stream=True以支持大文件下載
        response = requests.get(audio_url, stream=True, timeout=60)
        response.raise_for_status()
        
        # 獲取文件大小（如果可用）
        total_size = int(response.headers.get('content-length', 0))
        
        # 確保輸出目錄存在
        output_dir = os.path.dirname(output_path)
        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 下載文件
        downloaded_size = 0
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # 顯示進度
                    if show_progress and total_size > 0:
                        percent = (downloaded_size / total_size) * 100
                        print(f"\r  下載進度: {percent:.1f}% ({downloaded_size}/{total_size} bytes)", end='', flush=True)
        
        if show_progress:
            print()  # 換行
        
        return True
        
    except requests.exceptions.RequestException as e:
        if show_progress:
            print(f"\n❌ 下載失敗: {e}")
        return False
    except Exception as e:
        if show_progress:
            print(f"\n❌ 發生錯誤: {e}")
        return False


def parse_rss_feed(rss_url: str) -> List[Dict[str, Any]]:
    """
    解析RSS feed，提取播客集數信息
    
    參數:
        rss_url (str): RSS feed URL
    
    返回:
        List[Dict]: 播客集數列表，每個字典包含：
            - title: 標題
            - link: 鏈接
            - audio_url: 音頻URL
            - description: 描述
            - pub_date: 發布日期
            - duration: 時長（如果有）
    """
    episodes = []
    
    try:
        response = requests.get(rss_url, timeout=30)
        response.raise_for_status()
        
        # 解析XML
        root = ET.fromstring(response.content)
        
        # RSS feed的命名空間
        namespaces = {
            'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
            'atom': 'http://www.w3.org/2005/Atom',
            'content': 'http://purl.org/rss/1.0/modules/content/'
        }
        
        # 查找所有item元素（RSS 2.0標準）
        items = root.findall('.//item')
        
        for item in items:
            episode = {}
            
            # 提取標題
            title_elem = item.find('title')
            episode['title'] = title_elem.text if title_elem is not None else 'Unknown'
            
            # 提取鏈接
            link_elem = item.find('link')
            episode['link'] = link_elem.text if link_elem is not None else ''
            
            # 提取描述
            desc_elem = item.find('description')
            episode['description'] = desc_elem.text if desc_elem is not None else ''
            
            # 提取發布日期
            pub_date_elem = item.find('pubDate')
            episode['pub_date'] = pub_date_elem.text if pub_date_elem is not None else ''
            
            # 提取音頻URL（通常在enclosure標籤中）
            audio_url = None
            enclosure = item.find('enclosure')
            if enclosure is not None:
                audio_url = enclosure.get('url', '')
            
            # 如果沒有enclosure，嘗試從description或content中提取
            if not audio_url:
                # 嘗試從itunes:enclosure獲取
                itunes_enclosure = item.find('itunes:enclosure', namespaces)
                if itunes_enclosure is not None:
                    audio_url = itunes_enclosure.get('url', '')
            
            if not audio_url:
                # 從描述中搜索音頻鏈接
                desc_text = episode['description']
                url_pattern = r'https?://[^\s<>"\'{}|\\^`\[\]]+\.(?:mp3|m4a|mp4|ogg|wav|flac|aac|opus)'
                matches = re.findall(url_pattern, desc_text, re.IGNORECASE)
                if matches:
                    audio_url = matches[0]
            
            episode['audio_url'] = audio_url if audio_url else ''
            
            # 提取時長（itunes:duration）
            duration_elem = item.find('itunes:duration', namespaces)
            episode['duration'] = duration_elem.text if duration_elem is not None else ''
            
            if episode['audio_url']:
                episodes.append(episode)
        
        return episodes
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"無法獲取RSS feed: {e}")
    except ET.ParseError as e:
        raise Exception(f"RSS feed解析失敗: {e}")
    except Exception as e:
        raise Exception(f"處理RSS feed時發生錯誤: {e}")


def download_podcast_from_url(
    audio_url: str,
    output_dir: Optional[str] = None,
    filename: Optional[str] = None,
    show_progress: bool = True
) -> Optional[str]:
    """
    從直接音頻URL下載播客
    
    參數:
        audio_url (str): 音頻文件的直接URL
        output_dir (str, optional): 輸出目錄，默認為 'downloads'
        filename (str, optional): 輸出文件名（不含擴展名），如果為None則從URL提取
        show_progress (bool): 是否顯示下載進度
    
    返回:
        str: 下載的文件路徑，如果失敗則返回None
    """
    # 設置輸出目錄
    if output_dir is None:
        output_dir = os.path.join(os.getcwd(), 'downloads')
    
    # 創建輸出目錄
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 確定文件名
    if filename is None:
        # 嘗試從URL提取文件名
        parsed = urlparse(audio_url)
        filename = os.path.basename(parsed.path)
        if not filename or '.' not in filename:
            filename = 'podcast_audio'
    
    # 清理文件名
    filename = sanitize_filename(filename)
    
    # 獲取文件擴展名
    ext = get_file_extension_from_url(audio_url)
    if not filename.endswith(ext):
        filename = os.path.splitext(filename)[0] + ext
    
    # 構建完整路徑
    output_path = os.path.join(output_dir, filename)
    
    # 如果文件已存在，添加編號
    if os.path.exists(output_path):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(output_path):
            new_filename = f"{base}_{counter}{ext}"
            output_path = os.path.join(output_dir, new_filename)
            counter += 1
    
    if show_progress:
        print(f"正在下載: {audio_url}")
        print(f"保存到: {output_path}")
    
    # 下載文件
    success = download_audio_file(audio_url, output_path, show_progress=show_progress)
    
    if success:
        if show_progress:
            print(f"✓ 下載完成: {output_path}")
        return output_path
    else:
        return None


def download_podcast_from_rss(
    rss_url: str,
    output_dir: Optional[str] = None,
    episode_index: int = 0,
    latest: bool = True,
    show_progress: bool = True
) -> Optional[str]:
    """
    從RSS feed下載播客
    
    參數:
        rss_url (str): RSS feed URL
        output_dir (str, optional): 輸出目錄，默認為 'downloads'
        episode_index (int): 要下載的集數索引（從0開始，0為最新），只在latest=False時使用
        latest (bool): 是否下載最新一集，默認為True
        show_progress (bool): 是否顯示進度
    
    返回:
        str: 下載的文件路徑，如果失敗則返回None
    """
    if show_progress:
        print(f"📡 正在解析RSS feed: {rss_url}")
    
    # 解析RSS feed
    try:
        episodes = parse_rss_feed(rss_url)
    except Exception as e:
        if show_progress:
            print(f"❌ 錯誤: {e}")
        return None
    
    if not episodes:
        if show_progress:
            print("❌ RSS feed中未找到音頻文件")
        return None
    
    if show_progress:
        print(f"✓ 找到 {len(episodes)} 個播客集數")
    
    # 選擇要下載的集數
    if latest:
        selected_episode = episodes[0]  # 第一集通常是最新的
        index = 0
    else:
        if episode_index >= len(episodes):
            if show_progress:
                print(f"❌ 索引 {episode_index} 超出範圍（共有 {len(episodes)} 集）")
            return None
        selected_episode = episodes[episode_index]
        index = episode_index
    
    # 顯示選中的集數信息
    if show_progress:
        print(f"\n選擇下載: {selected_episode['title']}")
        if selected_episode.get('pub_date'):
            print(f"發布日期: {selected_episode['pub_date']}")
        if selected_episode.get('duration'):
            print(f"時長: {selected_episode['duration']}")
    
    # 確定文件名
    filename = sanitize_filename(selected_episode['title'])
    
    # 下載音頻
    return download_podcast_from_url(
        audio_url=selected_episode['audio_url'],
        output_dir=output_dir,
        filename=filename,
        show_progress=show_progress
    )


def download_podcast_simple(url: str) -> Optional[str]:
    """
    簡單版本：自動檢測URL類型並下載
    
    參數:
        url (str): 音頻URL或RSS feed URL
    
    返回:
        str: 下載的文件路徑，如果失敗則返回None
    """
    # 檢查是否是RSS feed（通常包含rss或feed關鍵字，或返回XML格式）
    is_rss = False
    url_lower = url.lower()
    
    # 簡單的RSS檢測
    if 'rss' in url_lower or 'feed' in url_lower or url_lower.endswith('.xml'):
        is_rss = True
    else:
        # 嘗試發送HEAD請求檢查Content-Type
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            content_type = response.headers.get('content-type', '').lower()
            if 'xml' in content_type or 'rss' in content_type or 'atom' in content_type:
                is_rss = True
        except:
            pass
    
    if is_rss:
        return download_podcast_from_rss(url)
    else:
        return download_podcast_from_url(url)


if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("播客音頻下載器")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("\n使用方法:")
        print("  python download_podcast.py <音頻URL或RSS feed URL> [輸出目錄]")
        print("\n示例:")
        print("  # 下載直接音頻URL")
        print("  python download_podcast.py https://example.com/podcast.mp3")
        print("\n  # 從RSS feed下載最新一集")
        print("  python download_podcast.py https://example.com/podcast.rss")
        print("\n  # 指定輸出目錄")
        print("  python download_podcast.py https://example.com/podcast.rss ./my_podcasts")
        sys.exit(1)
    
    url = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        result = download_podcast_simple(url)
        
        if result:
            print(f"\n✓ 成功！音頻文件已保存到: {result}")
        else:
            print("\n❌ 下載失敗，請檢查URL或網絡連接")
    
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

