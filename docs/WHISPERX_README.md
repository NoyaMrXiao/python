# WhisperX 語音轉文本功能

使用 [WhisperX](https://github.com/m-bain/whisperX) 進行高精度語音轉文本轉錄，支持詞級別時間戳和說話人分離。

## 功能特點

- ✅ 高精度語音轉文本（70x實時速度，large-v2模型）
- ✅ 詞級別時間戳（精確到單詞）
- ✅ 說話人分離（Diarization）
- ✅ 多語言支持（自動檢測或手動指定）
- ✅ 輸出多種格式（TXT, SRT, JSON）
- ✅ 支持GPU加速（CUDA）

## 安裝依賴

```bash
uv sync
```

### 額外要求

**FFmpeg** (用於音頻處理)
- macOS: `brew install ffmpeg`
- Linux: `sudo apt-get install ffmpeg`
- Windows: 從 [FFmpeg官網](https://ffmpeg.org/download.html) 下載

**HuggingFace Token** (用於說話人分離，可選)
- 獲取token: https://huggingface.co/settings/tokens
- 設置環境變量: `export HF_TOKEN=your_token_here`

## 使用方法

### 方法1: 轉錄本地音頻文件

```python
from src.transcribe_audio import transcribe_audio_simple

audio_file = "path/to/audio.mp3"
result = transcribe_audio_simple(audio_file, model_name="base")
```

### 方法2: 自定義轉錄設置

```python
from src.transcribe_audio import transcribe_audio

result = transcribe_audio(
    audio_file="audio.mp3",
    model_name="large-v2",  # 更大模型，更高準確度
    device="cuda",          # 使用GPU
    batch_size=8,           # 批次大小
    language="en"          # 指定語言（可選）
)
```

### 方法3: 帶說話人分離的轉錄

```python
import os
from src.transcribe_audio import transcribe_audio

hf_token = os.getenv("HF_TOKEN")  # 需要HuggingFace token

result = transcribe_audio(
    audio_file="audio.mp3",
    model_name="base",
    diarize=True,          # 啟用說話人分離
    hf_token=hf_token
)
```

### 方法4: 從YouTube直接轉文本

```python
from src.youtube_to_text import youtube_to_text

url = "https://www.youtube.com/watch?v=VIDEO_ID"
result = youtube_to_text(url, model_name="base")
```

### 命令行使用

**轉錄本地音頻:**
```bash
uv run python src/transcribe_audio.py audio.mp3 base
```

**YouTube轉文本:**
```bash
uv run python src/youtube_to_text.py https://www.youtube.com/watch?v=VIDEO_ID base
```

## 模型選擇

WhisperX支持以下模型（按準確度和速度排序）：

| 模型 | 大小 | 速度 | 準確度 | 推薦用途 |
|------|------|------|--------|----------|
| tiny | 39M | 最快 | 較低 | 快速測試 |
| base | 74M | 快 | 中等 | **推薦用於一般用途** |
| small | 244M | 中等 | 較好 | 平衡選擇 |
| medium | 769M | 慢 | 好 | 需要高準確度 |
| large-v2 | 1550M | 很慢 | 最好 | 專業用途 |
| large-v3 | 1550M | 很慢 | 最好 | 最新版本 |

## 輸出格式

轉錄功能會自動生成三種格式的文件：

1. **TXT** (`*_transcript.txt`) - 純文本格式，僅包含轉錄文本
2. **SRT** (`*_transcript.srt`) - 字幕文件，包含時間戳和說話人標籤
3. **JSON** (`*_transcript.json`) - 完整數據，包含所有時間戳和元信息

### 輸出示例

**TXT格式:**
```
Hello, this is a transcription example.
Welcome to WhisperX.
```

**SRT格式:**
```
1
00:00:00,000 --> 00:00:05,000
[SPEAKER_00] Hello, this is a transcription example.

2
00:00:05,000 --> 00:00:08,000
Welcome to WhisperX.
```

## API 文檔

### `transcribe_audio(audio_file, ...)`

主要轉錄函數。

**參數:**
- `audio_file` (str): 音頻文件路徑
- `model_name` (str): 模型名稱，默認 "base"
- `device` (str): 計算設備 ("cpu", "cuda", "auto")，默認 "auto"
- `compute_type` (str): 計算類型 ("float16", "int8", "auto")，默認 "auto"
- `batch_size` (int): 批次大小，默認 16（降低以減少GPU內存）
- `language` (str, optional): 語言代碼（如 "en", "zh", "de"）
- `diarize` (bool): 是否進行說話人分離，默認 False
- `hf_token` (str, optional): HuggingFace token（用於說話人分離）
- `output_dir` (str, optional): 輸出目錄
- `highlight_words` (bool): 是否在SRT中高亮詞級時間戳

**返回:**
- `dict`: 包含轉錄結果的字典

### `youtube_to_text(url, ...)`

完整的YouTube轉文本流程。

**參數:**
- `url` (str): YouTube視頻URL
- 其他參數與 `transcribe_audio` 相同
- `keep_audio` (bool): 是否保留下載的音頻文件，默認 False

**返回:**
- `dict`: 轉錄結果

## 性能優化建議

### GPU內存不足時

1. 降低批次大小: `batch_size=4`
2. 使用較小的模型: `model_name="base"` 或 `"small"`
3. 使用較輕的計算類型: `compute_type="int8"`

### CPU運行時

```python
result = transcribe_audio(
    audio_file,
    model_name="base",
    device="cpu",
    compute_type="int8",
    batch_size=4
)
```

## 支持的語言

WhisperX支持100+種語言，包括：
- 英語 (en)
- 中文 (zh)
- 德語 (de)
- 法語 (fr)
- 西班牙語 (es)
- 日語 (ja)
- 等等...

更多語言支持請參考 [WhisperX文檔](https://github.com/m-bain/whisperX)

## 故障排除

### 錯誤：找不到模型

首次運行時會自動下載模型，確保網絡連接正常。

### 錯誤：GPU內存不足

- 降低 `batch_size`
- 使用較小的模型
- 使用 `compute_type="int8"`

### 錯誤：說話人分離失敗

- 確保已設置 `HF_TOKEN` 環境變量
- 在 [HuggingFace](https://huggingface.co/settings/tokens) 獲取token

### 音頻文件格式不支持

WhisperX支持多種音頻格式（MP3, WAV, M4A等）。如果遇到問題，使用FFmpeg轉換：
```bash
ffmpeg -i input.audio output.wav
```

## 參考資源

- [WhisperX GitHub](https://github.com/m-bain/whisperX)
- [WhisperX論文](https://arxiv.org/abs/2303.00747)
- [HuggingFace模型中心](https://huggingface.co/models)

## 注意事項

1. 首次運行會下載模型文件（可能較大）
2. GPU運行需要CUDA支持的GPU和PyTorch CUDA版本
3. 說話人分離需要HuggingFace token
4. 轉錄長音頻文件可能需要較長時間

