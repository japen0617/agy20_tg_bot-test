import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# 載入環境變數
load_dotenv()

# 設定日誌紀錄
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# 取得 Telegram Bot Token
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """當使用者發送 /start 時觸發，發送歡迎訊息。"""
    user = update.effective_user
    welcome_text = (
        f"哈囉 {user.first_name}！我是您的 Telegram 智慧小助手。🤖\n\n"
        "目前這是 Lab 1 基礎版本，支援以下指令：\n"
        "• /start - 開始使用小助手\n"
        "• /help - 顯示指令說明\n"
        "• 直接傳送文字給我，我會回傳相同的內容（Echo 測試）\n\n"
        "後續的 Lab 將會逐步解鎖 PPT 生成、圖片生成與修改、Google Drive 與 Calendar 串接等功能，敬請期待！"
    )
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """當使用者發送 /help 時觸發，發送指令說明。"""
    help_text = (
        "💡 可用指令說明：\n"
        "• /start - 重啟並開始與機器人互動\n"
        "• /help - 顯示此指令說明\n"
        "• 直接發送任何文字訊息，我會回覆相同的內容以測試連線。"
    )
    await update.message.reply_text(help_text)

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """當收到文字訊息時觸發，回傳相同文字以進行 Echo 測試。"""
    user_text = update.message.text
    reply_text = f"收到您的訊息：『{user_text}』\n（這是 Echo 測試）"
    await update.message.reply_text(reply_text)

def main() -> None:
    """啟動機器人的主函數。"""
    if not BOT_TOKEN:
        logger.error("錯誤：請確認已在 .env 檔案中設定 TELEGRAM_BOT_TOKEN！")
        print("【系統提示】請先複製 .env.example 並命名為 .env，填入您的 Telegram Bot Token 後再啟動。")
        return

    # 建立 Application 並傳入 token
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # 註冊指令與訊息處理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # 開始輪詢 (Polling) 接聽訊息
    logger.info("機器人已啟動，正在接聽訊息...")
    application.run_polling()

if __name__ == "__main__":
    main()
