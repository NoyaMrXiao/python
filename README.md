# Python 學習項目

這是一個包含多種功能的Python學習項目，涵蓋文檔生成、流程圖繪製、YouTube音頻下載等功能。

## 📁 項目結構

```
.
├── src/                    # 主要功能源代碼
│   ├── download_youtube_audio.py   # YouTube音頻下載功能
│   ├── transcribe_audio.py         # WhisperX語音轉文本
│   ├── youtube_to_text.py          # YouTube完整流程（下載+轉錄）
│   ├── example_download.py          # 下載功能示例
│   └── example_transcribe.py        # 轉錄功能示例
│
├── scripts/                # 工具腳本
│   ├── generate_flowchart.py       # 生成流程圖
│   ├── generate_pdf.py            # 生成PDF文檔
│   ├── convert_to_traditional.py  # 簡體轉繁體工具
│   └── convert_scripts_to_traditional.py
│
├── docs/                   # 文檔目錄
│   ├── 需求文档.md                 # 需求文檔（Markdown）
│   ├── 需求文檔與流程圖.pdf        # 完整PDF文檔
│   ├── user_flow.mmd               # Mermaid流程圖源文件
│   ├── YOUTUBE_DOWNLOAD_README.md  # YouTube下載功能說明
│   ├── WHISPERX_README.md          # WhisperX轉錄功能說明
│   └── README_OLD.md               # 舊版README
│
├── outputs/                # 生成的輸出文件
│   ├── user_flowchart.png          # 流程圖PNG
│   └── flowchart_viewer.html       # HTML流程圖查看器
│
├── downloads/              # 下載的文件（YouTube音頻等）
│
├── main.py                 # 主程序（BBC新聞搜索示例）
├── pyproject.toml          # 項目配置和依賴
├── uv.lock                 # 依賴鎖定文件
└── README.md               # 本文件
```

## 🚀 功能模塊

### 1. YouTube 音頻下載

下載YouTube視頻的音頻軌道並轉換為MP3格式。

**使用方法：**
```python
from src.download_youtube_audio import download_youtube_audio_simple

url = "https://www.youtube.com/watch?v=VIDEO_ID"
audio_file = download_youtube_audio_simple(url)
```

**詳細說明：** 參見 [docs/YOUTUBE_DOWNLOAD_README.md](docs/YOUTUBE_DOWNLOAD_README.md)

### 2. 語音轉文本 (WhisperX)

使用WhisperX進行高精度語音轉文本，支持詞級時間戳和說話人分離。

**使用方法：**
```python
from src.transcribe_audio import transcribe_audio_simple

audio_file = "path/to/audio.mp3"
result = transcribe_audio_simple(audio_file, model_name="base")
```

**完整流程（YouTube直接轉文本）：**
```python
from src.youtube_to_text import youtube_to_text

url = "https://www.youtube.com/watch?v=VIDEO_ID"
result = youtube_to_text(url, model_name="base")
```

**詳細說明：** 參見 [docs/WHISPERX_README.md](docs/WHISPERX_README.md)

### 3. 流程圖生成

根據需求文檔生成用戶流程圖。

**使用方法：**
```bash
uv run python scripts/generate_flowchart.py
```

生成的流程圖會保存在 `outputs/user_flowchart.png`

### 4. PDF 文檔生成

將Markdown需求文檔和流程圖合併生成PDF。

**使用方法：**
```bash
uv run python scripts/generate_pdf.py
```

生成的PDF會保存在 `outputs/需求文檔與流程圖.pdf`

### 5. 文檔轉換工具

將簡體中文文檔轉換為繁體中文。

**使用方法：**
```bash
uv run python scripts/convert_to_traditional.py
```

## 📦 安裝依賴

本項目使用 `uv` 作為包管理器：

```bash
# 安裝所有依賴
uv sync
```

## 🔧 系統要求

### Python版本
- Python >= 3.12

### 外部工具
- **FFmpeg** (用於YouTube音頻下載)
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt-get install ffmpeg`
  - Windows: 從 [FFmpeg官網](https://ffmpeg.org/download.html) 下載

## 📋 依賴項列表

主要依賴：
- `selenium` - 網頁自動化
- `matplotlib` - 圖表繪製
- `numpy` - 數值計算
- `reportlab` - PDF生成
- `yt-dlp` - YouTube下載
- `whisperx` - 語音轉文本
- `torch` - 深度學習框架（WhisperX需要）
- `zhconv` - 簡繁轉換

完整列表見 `pyproject.toml`

## 🎯 快速開始

1. **安裝依賴**
   ```bash
   uv sync
   ```

2. **下載YouTube音頻**
   ```bash
   uv run python -c "from src.download_youtube_audio import download_youtube_audio_simple; download_youtube_audio_simple('YOUR_URL')"
   ```

3. **轉錄音頻為文本**
   ```bash
   # 轉錄本地音頻
   uv run python src/transcribe_audio.py audio.mp3 base
   
   # 或直接從YouTube轉文本
   uv run python src/youtube_to_text.py https://www.youtube.com/watch?v=VIDEO_ID base
   ```

4. **生成流程圖**
   ```bash
   uv run python scripts/generate_flowchart.py
   ```

5. **生成PDF文檔**
   ```bash
   uv run python scripts/generate_pdf.py
   ```

## 📝 文檔說明

- **需求文檔**: `docs/需求文档.md` - 應用需求規格說明
- **流程圖**: `docs/user_flow.mmd` - Mermaid格式流程圖源文件
- **PDF文檔**: `docs/需求文檔與流程圖.pdf` - 完整的PDF文檔

## 🔍 項目特點

- ✅ 模塊化設計，功能清晰分離
- ✅ 完整的文檔和註釋（繁體中文）
- ✅ 支持多種輸出格式（PNG, PDF, HTML）
- ✅ 易於擴展和使用

## 📄 許可證

本項目僅供學習使用。

## 🤝 貢獻

歡迎提交Issue和Pull Request！

---

**注意：** 請遵守相關平台的使用條款和版權法律，僅下載允許下載的公開內容。

