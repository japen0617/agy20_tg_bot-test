# Lab 4：AI 圖像修改功能

在此階段（Lab 4），我們為 Telegram 小助手新增了 **AI 圖片修改**功能。

使用者可以點擊並上傳一張圖片到 Telegram 對話中，接著小助手會引導使用者輸入一段修改要求文字（例如：*「在背景加上富士山與櫻花」*）。

小助手會使用 **Gemini 3.5 Flash** 多模態模型分析原圖與修改指令，自動生成一段高畫質的英文 prompt，再交給 **Imagen 3** 生成出融合了原圖主體、風格與修改內容的新圖片。

本階段仍支援之前的所有功能（簡報生成、圖片生成、基礎 Bot 響應）。

---

## 🚀 本地執行步驟

### 1. 建立並啟用虛擬環境

進入 `lab4_image_modifier` 資料夾：

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

複製 `.env.example` 並命名為 `.env`，填入您的 **Telegram Bot Token** 與 **Gemini API Key**。

### 4. 啟動機器人

```bash
python bot.py
```

---

## 🧪 測試 AI 圖片修改

打開 Telegram，找到您的機器人：

1. **上傳原圖**：
   直接上傳一張圖片。
2. **輸入修改要求**：
   上傳成功後，機器人會提示您輸入修改要求。此時直接發送文字，例如：*「幫牠戴上一頂紅色魔術帽」*。
3. **等待生成**：
   機器人會回傳修改後的圖片。
4. **取消操作**：
   在上傳圖片後、輸入修改文字前，您可以隨時發送 `/cancel` 取消當前操作。
