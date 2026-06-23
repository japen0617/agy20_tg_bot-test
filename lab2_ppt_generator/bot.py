import logging
import os
import time
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from google import genai
from google.genai import types

# 引入 PPT 生成模組與資料結構
from ppt_creator import PPTOutline, create_presentation

# 載入環境變數
load_dotenv()

# 設定日誌紀錄
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# 取得 Token 與 API Key
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# 初始化 Gemini Client
client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    logger.warning("未偵測到 GEMINI_API_KEY，AI 功能將無法運作！")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """當使用者發送 /start 時觸發，發送歡迎與指令說明。"""
    welcome_text = (
        f"哈囉 {update.effective_user.first_name}！我是您的 Telegram 智慧小助手。🤖\n\n"
        "目前已升級為 **Lab 2：AI 簡報生成版本**！\n"
        "您可以使用 `/ppt` 指令讓 AI 幫您自動生成一份簡報投影片。\n\n"
        "💡 **指令用法：**\n"
        "• `/ppt <主題>` - 以預設的「淺色」主題生成簡報\n"
        "• `/ppt light <主題>` - 套用「淺色」主題生成簡報\n"
        "• `/ppt dark <主題>` - 套用「深色」主題生成簡報\n\n"
        "範例：\n"
        "`/ppt 區塊鏈的技術與應用`\n"
        "`/ppt dark 2026年人工智慧發展趨勢`"
    )
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """當使用者發送 /help 時觸發，發送指令說明。"""
    help_text = (
        "💡 **可用指令說明：**\n"
        "• `/start` - 重啟小助手並顯示歡迎訊息\n"
        "• `/help` - 顯示指令說明\n"
        "• `/ppt [light|dark] <主題>` - 依據指定的主題與配色生成簡報投影片檔案\n"
        "• 直接傳送文字訊息 - 機器人會回傳相同內容（Echo 測試）"
    )
    await update.message.reply_text(help_text)

async def generate_ppt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /ppt 指令，呼叫 Gemini 生成大綱並繪製成 PPTX 傳送給使用者。"""
    if not client:
        await update.message.reply_text("❌ 伺服器未設定 GEMINI_API_KEY，無法使用 AI 功能。")
        return

    # 解析參數
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ 請輸入簡報主題！\n"
            "用法：`/ppt <主題>` 或 `/ppt [light|dark] <主題>`\n"
            "例如：`/ppt 人工智慧介紹` 或 `/ppt dark 綠色能源未來`"
        )
        return

    # 判斷是否指定主題 (Theme)
    theme = "light"
    first_arg = args[0].lower()
    if first_arg in ["light", "dark"]:
        theme = first_arg
        topic = " ".join(args[1:])
    else:
        topic = " ".join(args)

    if not topic.strip():
        await update.message.reply_text("❌ 請輸入有效的簡報主題！")
        return

    # 送出等待提示訊息
    status_message = await update.message.reply_text(f"⏳ 正在規劃『{topic}』的簡報大綱，請稍候...")

    try:
        # 設計給 Gemini 的提示詞 (Prompt)
        prompt = (
            f"請針對主題『{topic}』設計一份具有學術或商業價值的簡報大綱與詳細頁面內容。\n"
            f"簡報頁數請規劃在 5 至 8 頁之間。\n"
            f"請務必包含：\n"
            f"1. 首頁 (版面必須設為 'title_slide')。\n"
            f"2. 其他頁面，請根據內容自由調配為標準條列式 ('bullets') 或左右雙欄對比式 ('two_columns')。\n"
            f"3. 內容請以使用者提問的語言 (繁體中文) 回覆，結構必須符合 PPTOutline JSON 格式。"
        )

        # 呼叫 Gemini API，並強制指定輸出 JSON Schema 結構
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PPTOutline,
                temperature=0.7,
            )
        )

        # 使用 Pydantic 驗證並解析 API 回傳的 JSON 內容
        outline = PPTOutline.model_validate_json(response.text)
        
        # 更新進度提示
        await status_message.edit_text("🎨 內容大綱生成完畢！正在為您排版並繪製簡報...")

        # 建立並排版簡報
        prs = create_presentation(outline, theme)

        # 儲存簡報到暫存檔
        os.makedirs("outputs", exist_ok=True)
        # 過濾不合法檔案字元作為檔名
        safe_topic = "".join(c for c in topic if c.isalnum() or c in (" ", "_", "-")).strip()[:20]
        safe_topic = safe_topic.replace(" ", "_")
        filename = f"outputs/{safe_topic}_{theme}_{int(time.time())}.pptx"
        prs.save(filename)

        # 更新進度提示
        await status_message.edit_text("📤 簡報排版完成，正在發送檔案...")

        # 發送文件
        with open(filename, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"{topic}_{theme}.pptx",
                caption=f"✅ 成功為您生成簡報！\n\n主題：{topic}\n風格主題：{theme.upper()}\n總頁數：{len(outline.slides)} 頁"
            )

        # 刪除發送中的等待訊息
        await status_message.delete()
        
        # 清理暫存檔
        if os.path.exists(filename):
            os.remove(filename)

    except Exception as e:
        logger.exception("生成 PPT 時發生錯誤")
        await status_message.edit_text(f"❌ 簡報生成失敗，錯誤訊息：\n`{str(e)}`")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """當收到文字訊息時觸發，回傳相同文字以進行 Echo 測試。"""
    user_text = update.message.text
    reply_text = f"收到您的訊息：『{user_text}』\n（這是 Echo 測試）"
    await update.message.reply_text(reply_text)

def main() -> None:
    """啟動機器人的主函數。"""
    if not BOT_TOKEN:
        logger.error("錯誤：請確認已在 .env 檔案中設定 TELEGRAM_BOT_TOKEN！")
        print("【系統提示】請先複製 .env.example 並命名為 .env，填入您的 Token 後再啟動。")
        return

    # 建立 Application 並傳入 token
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # 註冊指令與訊息處理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ppt", generate_ppt))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # 開始輪詢 (Polling) 接聽訊息
    logger.info("機器人 (Lab 2) 已啟動，正在接聽訊息...")
    application.run_polling()

if __name__ == "__main__":
    main()
