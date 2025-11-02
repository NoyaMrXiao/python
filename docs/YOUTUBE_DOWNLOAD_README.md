# YouTube 音頻下載功能

這個模塊提供了下載YouTube視頻音頻到本地的功能。

## 功能特點

- ✅ 下載YouTube視頻的音頻軌道
- ✅ 自動轉換為MP3格式（192kbps）
- ✅ 支持自定義輸出目錄和文件名
- ✅ 自動創建下載目錄
- ✅ 顯示下載進度和狀態

## 安裝依賴

```bash
uv sync
```

## 系統要求

**重要：需要安裝FFmpeg才能提取和轉換音頻**

### macOS
```bash
brew install ffmpeg
```

### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

### Windows
從 [FFmpeg官網](https://ffmpeg.org/download.html) 下載並添加到系統PATH

## 使用方法

### 方法1：最簡單的用法

```python
from download_youtube_audio import download_youtube_audio_simple

url = "https://www.youtube.com/watch?v=oOylEw3tPQ8&t=330s"
audio_file = download_youtube_audio_simple(url)
```

### 方法2：指定輸出目錄

```python
from download_youtube_audio import download_youtube_audio

url = "https://www.youtube.com/watch?v=oOylEw3tPQ8&t=330s"
audio_file = download_youtube_audio(url, output_dir="./my_downloads")
```

### 方法3：指定自定義文件名

```python
from download_youtube_audio import download_youtube_audio

url = "https://www.youtube.com/watch?v=oOylEw3tPQ8&t=330s"
audio_file = download_youtube_audio(
    url, 
    output_dir="./downloads",
    filename="my_custom_name"
)
```

### 直接運行腳本

```bash
uv run python download_youtube_audio.py
```

這會下載指定的YouTube視頻音頻（URL在腳本中定義）。

## API 文檔

### `download_youtube_audio(url, output_dir=None, filename=None)`

下載YouTube視頻的音頻到本地。

**參數:**
- `url` (str): YouTube視頻URL（完整URL或短URL）
- `output_dir` (str, optional): 輸出目錄，默認為 `./downloads`
- `filename` (str, optional): 輸出文件名（不含擴展名），如果為None則使用視頻標題

**返回:**
- `str`: 下載的音頻文件路徑，如果失敗則返回None

### `download_youtube_audio_simple(url)`

簡單版本，使用默認設置下載音頻。

**參數:**
- `url` (str): YouTube視頻URL

**返回:**
- `str`: 下載的音頻文件路徑，如果失敗則返回None

## 輸出格式

- **格式**: MP3
- **音質**: 192 kbps
- **默認目錄**: `./downloads/`

## 示例

查看 `example_download.py` 文件了解更多使用示例。

## 注意事項

1. 確保已安裝FFmpeg，否則無法轉換音頻格式
2. 需要穩定的網絡連接
3. 下載的視頻必須是公開的或可訪問的
4. 請遵守YouTube的使用條款和版權法律

## 故障排除

### 錯誤：找不到FFmpeg

確保FFmpeg已正確安裝並在系統PATH中。可以使用以下命令檢查：

```bash
ffmpeg -version
```

### 下載失敗

- 檢查網絡連接
- 確認URL是否有效
- 確認視頻是否可訪問（非私有或受限制）

### 文件未找到

即使下載成功，有時文件名可能與預期不同。函數會自動查找最新的音頻文件並返回其路徑。

