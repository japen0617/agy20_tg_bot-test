# Lab 2：AI 簡報生成器

在此階段（Lab 2），我們為 Telegram 小助手新增了 **AI 簡報生成** 功能。小助手會串接 Google Gemini API（採用最新的 `google-genai` SDK 與 `gemini-2.5-flash` 或 `gemini-3.5-flash` 模型），利用**結構化輸出 (Structured Outputs)** 自動規劃簡報大綱，並透過 `python-pptx` 動態排版繪製出工整、美觀的簡報檔案（.pptx）。

此外，本專案支援**主題切換（Light 淺色 / Dark 深色）**，供使用者自由選擇。

---

## 🛠️ 新增依賴套件

本階段新增了以下套件：
* `google-genai`：Google 官方最新的 Gemini API Python SDK。
* `python-pptx`：用於程式化建立、修改簡報檔案的函式庫。
* `pydantic`：用於對 Gemini 回傳的 JSON 結構進行強型別校驗與解析。

---

## 🚀 本地執行步驟

### 1. 建立並啟用虛擬環境

進入 `lab2_ppt_generator` 資料夾：

```bash
# 建立虛擬環境
python3 -m venv venv

# 啟用虛擬環境 (macOS / Linux)
source venv/bin/activate

# 啟用虛擬環境 (Windows)
# .\venv\Scripts\Activate.ps1
```

### 2. 安裝依賴套件

```bash
pip install -r requirements.txt
```

### 3. 設定環境變數

將目錄下的 `.env.example` 複製一份並命名為 `.env`：

```bash
cp .env.example .env
```

接著填入您的 **Telegram Bot Token** 與 **Gemini API Key**：

```env
TELEGRAM_BOT_TOKEN=您的_TELEGRAM_BOT_TOKEN
GEMINI_API_KEY=您的_GEMINI_API_KEY
GEMINI_MODEL=gemini-2.5-flash
```

> 💡 **如何取得 Gemini API Key**：您可以前往 [Google AI Studio](https://aistudio.google.com/) 免費申請 API Key。

### 4. 啟動機器人

```bash
python bot.py
```

---

## 🧪 測試 AI 簡報生成

打開 Telegram，找到您的機器人，並發送以下指令進行測試：

1. **基本測試（預設淺色主題）**：
   發送 `/ppt 區塊鏈的技術架構與去中心化應用`。機器人會提示正在規劃，規劃完成後會自動傳送產出的簡報檔案給您。
2. **深色主題測試**：
   發送 `/ppt dark 綠色能源與永續發展的未來`。機器人將使用深灰色背景與琥珀橘配色生成簡報。
3. **淺色主題測試（顯式指定）**：
   發送 `/ppt light 2026年人工智慧發展趨勢`。
