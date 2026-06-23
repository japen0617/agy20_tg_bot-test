# Lab 1：基礎 Telegram 機器人建置

這是 Telegram 小助手的起步專案（Lab 1）。在此階段，我們實作了機器人的基礎框架，包含連接 Telegram 伺服器、指令處理器（`/start` 與 `/help`），以及基礎的 Echo 訊息回覆。

---

## 🛠️ 開發前準備

1. **取得 Telegram Bot Token**：
   - 在 Telegram 上搜尋 [@BotFather](https://t.me/BotFather)。
   - 發送 `/newbot` 指令，並依據指示設定機器人的名稱與帳號（username）。
   - 建立成功後，`BotFather` 會給您一串 Token（格式類似 `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`）。

---

## 🚀 本地執行步驟

### 1. 建立並啟用虛擬環境（建議）

在終端機中進入 `lab1_basic_bot` 資料夾：

```bash
# 建立虛擬環境
python3 -m venv venv

# 啟用虛擬環境 (macOS / Linux)
source venv/bin/activate

# 啟用虛擬環境 (Windows PowerShell)
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

接著用編輯器打開 `.env`，填入您的 Telegram Bot Token：

```env
TELEGRAM_BOT_TOKEN=您的_TELEGRAM_BOT_TOKEN
```

### 4. 啟動機器人

```bash
python bot.py
```

若看到終端機輸出 `機器人已啟動，正在接聽訊息...`，代表連線成功！

---

## 🧪 測試您的機器人

打開 Telegram，搜尋您為機器人設定的 username，點擊 **開始 (Start)**，或發送以下內容：
* `/start`：應收到機器人的歡迎訊息。
* `/help`：應收到可用指令說明。
* 隨意發送任何文字訊息（例如 `Hello!`）：機器人應會 Echo 回傳您所寫的內容。
