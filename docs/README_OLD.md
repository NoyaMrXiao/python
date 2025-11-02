# 應用需求文檔與流程圖項目

本項目包含 Web/Mobile 應用的需求文檔和用戶流程圖，並提供多種格式的文檔輸出。

## 文件說明

### 文檔文件
- **需求文檔.md** - 完整的需求文檔（Markdown格式）
- **需求文檔與流程圖.pdf** - 包含需求文檔和流程圖的PDF文檔（可直接使用）

### 流程圖文件
- **user_flow.mmd** - Mermaid格式的流程圖源文件
- **user_flowchart.png** - 流程圖的PNG圖片
- **flowchart_viewer.html** - 可在瀏覽器中查看的交互式流程圖（使用Mermaid.js）

### 腳本文件
- **generate_flowchart.py** - 生成流程圖的Python腳本
- **generate_pdf.py** - 生成PDF文檔的Python腳本

## 使用方法

### 查看PDF文檔（推薦）
直接打開 `需求文檔與流程圖.pdf` 文件即可查看完整的需求文檔和流程圖。

### 查看HTML流程圖
在瀏覽器中打開 `flowchart_viewer.html` 查看交互式流程圖。

### 重新生成文件

1. **生成流程圖PNG**：
```bash
uv run python generate_flowchart.py
```

2. **生成PDF文檔**：
```bash
uv run python generate_pdf.py
```

## 項目結構

```
.
├── 需求文檔.md                 # 需求文檔源文件
├── 需求文檔與流程圖.pdf        # 最終PDF文檔
├── user_flow.mmd              # Mermaid流程圖源文件
├── user_flowchart.png         # 流程圖圖片
├── flowchart_viewer.html      # HTML流程圖查看器
├── generate_flowchart.py       # 流程圖生成腳本
├── generate_pdf.py            # PDF生成腳本
└── pyproject.toml             # 項目依賴配置
```

## 依賴項

- matplotlib - 用於生成流程圖圖片
- numpy - 數值計算支持
- reportlab - 用於生成PDF文檔
- markdown - Markdown解析支持

安裝依賴：
```bash
uv sync
```

## 功能模塊概述

應用包含以下主要功能模塊：

1. **登錄/註冊** - 用戶認證
2. **首頁** - 主導航頁面
3. **比賽信息** - 比賽詳情、評審團、作品提交
4. **展示中心** - 作品展示、精選內容、朋友推薦
5. **個人資料** - 好友中心、消息、成長數據
6. **日誌/通知** - 媒體報導、訪談、社交媒體
7. **幫助與資源** - 關於我們、資源庫、通知更新

詳細的流程和需求說明請參考PDF文檔或Markdown源文件。

