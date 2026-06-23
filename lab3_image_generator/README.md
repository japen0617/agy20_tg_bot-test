# Lab 3：AI 圖片生成器

在此階段（Lab 3），我們為 Telegram 小助手新增了 **AI 圖片生成** 功能。小助手會串接 Google Gemini API（採用最新的 `google-genai` SDK 與 `imagen-3.0-generate-002` 模型），支援多種圖片長寬比設定，並將產生的圖片發送給使用者。

本階段保留了 Lab 2 的簡報生成與 Lab 1 的基礎 Bot 功能，實現功能堆疊。

---

## 🛠️ 新增與設定的環境變數

本階段在 `.env` 中新增了 `IMAGEN_MODEL`，用以指定圖片生成模型：

```env
TELEGRAM_BOT_TOKEN=您的_TELEGRAM_BOT_TOKEN
GEMINI_API_KEY=您的_GEMINI_API_KEY
GEMINI_MODEL=gemini-2.5-flash
IMAGEN_MODEL=imagen-3.0-generate-002
```

---

## 🚀 本地執行步驟

### 1. 建立並啟用虛擬環境

進入 `lab3_image_generator` 資料夾：

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

將目錄下的 `.env.example` 複製一份並命名為 `.env`，填入您的 **Telegram Bot Token** 與 **Gemini API Key**。

### 4. 啟動機器人

```bash
python bot.py
```

---

## 🧪 測試 AI 圖片生成

打開 Telegram，找到您的機器人，並發送以下指令進行測試：

1. **基本測試（預設 1:1 方形）**：
   發送 `/draw 一隻戴著太陽眼鏡的柴犬在沙灘上喝椰子汁`。
2. **寬螢幕測試（16:9）**：
   發送 `/draw 16:9 未來感賽博朋克風格的台北街頭`。
3. **手機桌布尺寸測試（9:16）**：
   發送 `/draw 9:16 奇幻森林中的精靈木屋，月光灑落，吉卜力畫風`。
4. **其他支援比例**：
   可自由嘗試 `4:3` 或 `3:4` 等比例。
