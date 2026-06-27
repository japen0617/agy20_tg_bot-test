# Telegram 智慧小助手 (Telegram Assistant Bot) - 5 Labs Series

[English Summary below](#english-summary)

本專案是一個循序漸進的 Telegram 機器人（智慧小助手）開發教學與範例專案。專案共劃分為 5 個獨立可執行的 Lab 目錄，展示如何從零建置一個整合 Google Gemini 3.5 Flash 與 Imagen 3 的智慧助理。

---

## 📂 專案目錄結構 (Lab 規劃)

本專案採用功能遞增的方式，每個 Lab 都是一個完整且可獨立執行的專案：

* **📂 [Lab 1: 基礎 Bot 框架](lab1_basic_bot)**
  * 建置 Telegram Bot 連線、基本指令（`/start` 與 `/help`）與 Echo 訊息回覆。
* **📂 [Lab 2: AI 簡報生成器](lab2_ppt_generator)**
  * 串接 Gemini 3.5 Flash 生成結構化大綱，並使用 `python-pptx` 自動繪製簡報（支援 Light/Dark 主題設定）。
* **📂 [Lab 3: AI 圖片生成器](lab3_image_generator)**
  * 串接 Gemini Imagen 3 圖片生成模型，提供 `/draw [比例] <描述>` 指令，支援 `1:1`、`16:9`、`9:16`、`4:3`、`3:4` 等多種長寬比。
* **📂 [Lab 4: AI 圖像修改器](lab4_image_modifier)**
  * 上傳圖片至機器人，機器人會進入等待指令狀態，呼叫 Gemini 多模態與 Imagen 3 協同為您修改原圖並回傳。
* **📂 [Lab 5: 個人隨手筆記本](lab5_note_taking)**
  * 引入本機 SQLite 資料庫儲存個人筆記，並實作 `/addnote` 與 `/notes`。清單底部提供內聯按鈕（Inline Keyboard）非同步、無縫刪除個別筆記。
* **📂 [Lab 6: 語音轉譯與摘要筆記本 (最新整合版)](lab6_voice_summarizer)**
  * 引入語音訊息監聽，使用 Gemini 原生多模態音訊引擎進行轉譯與重點摘要，支援獨立的 `voice_notes` 資料庫儲存，並提供 `/voicenotes` 列出清單以進行詳細檢視、重播及刪除。本 Lab 亦納入非同步 I/O 及資源洩漏防護之重構優化。

---

## 🛠️ 開發前準備

要執行此機器人，您需要準備以下憑證：

1. **Telegram Bot Token**：在 Telegram 上對 [@BotFather](https://t.me/BotFather) 發送 `/newbot` 指令取得。
2. **Gemini API Key**：前往 [Google AI Studio](https://aistudio.google.com/) 免費申請。

---

## 🚀 快速啟動 (以 Lab 5 最終版為例)

### 1. 進入目錄並建立虛擬環境
```bash
cd lab5_note_taking
python3 -m venv venv
source venv/bin/activate  # Windows 請執行 .\venv\Scripts\Activate.ps1
```

### 2. 安裝依賴套件
```bash
pip install -r requirements.txt
```

### 3. 設定環境變數
將目錄下的 `.env.example` 複製一份並命名為 `.env`，填入您的金鑰：
```env
TELEGRAM_BOT_TOKEN=您的_TELEGRAM_BOT_TOKEN
GEMINI_API_KEY=您的_GEMINI_API_KEY
GEMINI_MODEL=gemini-2.5-flash
IMAGEN_MODEL=imagen-3.0-generate-002
```

### 4. 啟動機器人
```bash
python bot.py
```

---

## <a name="english-summary"></a> English Summary

This repository is a step-by-step tutorial and project series containing 6 independent labs for building a multi-functional Telegram Assistant Bot integrated with Google Gemini 3.5 Flash and Imagen 3.

* **📂 [Lab 1: Basic Bot](lab1_basic_bot)**: Basic setup, handles `/start`, `/help` and echoes messages.
* **📂 [Lab 2: AI PPT Generator](lab2_ppt_generator)**: Generates PPT presentations (.pptx) based on a topic using Gemini 3.5 Flash and `python-pptx` (supports light/dark themes).
* **📂 [Lab 3: AI Image Generator](lab3_image_generator)**: Generates high-quality images from prompts with custom aspect ratios (`1:1`, `16:9`, `9:16`, etc.) using Imagen 3.
* **📂 [Lab 4: AI Image Modifier](lab4_image_modifier)**: Upload an image, send edit instructions, and get the modified image back using Gemini Multimodal and Imagen 3.
* **📂 [Lab 5: Note-Taking](lab5_note_taking)**: Implements note-taking using SQLite database. Displays notes with inline keyboards for seamless delete callbacks.
* **📂 [Lab 6: Voice Transcription & Summarization (Latest Version)](lab6_voice_summarizer)**: Subscribes to voice messages, using Gemini's native multimodal audio engine for transcription and core summarization. Includes sqlite data model for voice notes, and `/voicenotes` management controls for detail viewing, voice replay, and deletion. Integrated with async I/O thread-pooling and strict resource-leak protections.

### Quick Start
Rename `.env.example` to `.env` in the target lab directory, fill in your `TELEGRAM_BOT_TOKEN` and `GEMINI_API_KEY`, install dependencies using `pip install -r requirements.txt`, and run `python bot.py`.
