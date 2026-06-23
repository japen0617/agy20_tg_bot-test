import logging
import os
import time
import io
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

# 引入 PPT 生成模組與資料結構 (維持 Lab 2 功能)
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
IMAGEN_MODEL = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")

# 初始化 Gemini Client
client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    logger.warning("未偵測到 GEMINI_API_KEY，AI 功能將無法運作！")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """歡迎訊息，列出 PPT 與圖片生成指令。"""
    welcome_text = (
        f"哈囉 {update.effective_user.first_name}！我是您的 Telegram 智慧小助手。🤖\n\n"
        "目前已升級為 **Lab 3：AI 圖片生成版本**！\n"
        "除了原本的簡報生成，您現在也可以讓 AI 幫您畫畫了。\n\n"
        "🎨 **新增功能 - 圖片生成：**\n"
        "指令：`/draw [比例] <圖片描述>`\n"
        "• 預設為 `1:1` 方形圖片。\n"
        "• 支援比例：`1:1`、`16:9`、`9:16`、`4:3`、`3:4`\n\n"
        "圖片生成範例：\n"
        "`/draw 一隻戴著太陽眼鏡的柴犬在沙灘上喝椰子汁`\n"
        "`/draw 16:9 未來感賽博朋克風格的台北街頭`\n\n"
        "📊 **簡報生成功能（維持）：**\n"
        "指令：`/ppt [light|dark] <主題>`\n"
        "範例：`/ppt dark 人工智慧簡介`"
    )
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """指令說明。"""
    help_text = (
        "💡 **可用指令說明：**\n"
        "• `/start` - 重啟小助手並顯示歡迎訊息\n"
        "• `/help` - 顯示指令說明\n"
        "• `/ppt [light|dark] <主題>` - 生成簡報投影片檔案 (.pptx)\n"
        "• `/draw [比例] <圖片描述>` - 生成 AI 圖片 (支援 1:1, 16:9, 9:16 等)\n"
        "• 直接傳送文字訊息 - 機器人會回傳相同內容（Echo 測試）"
    )
    await update.message.reply_text(help_text)

async def generate_ppt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """(維持 Lab 2 功能) 處理 /ppt 指令，呼叫 Gemini 生成大綱並繪製成 PPTX 傳送。"""
    if not client:
        await update.message.reply_text("❌ 伺服器未設定 GEMINI_API_KEY，無法使用 AI 功能。")
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ 請輸入簡報主題！\n"
            "用法：`/ppt <主題>` 或 `/ppt [light|dark] <主題>`"
        )
        return

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

    status_message = await update.message.reply_text(f"⏳ 正在規劃『{topic}』的簡報大綱，請稍候...")

    try:
        prompt = (
            f"請針對主題『{topic}』設計一份具有學術或商業價值的簡報大綱與詳細頁面內容。\n"
            f"簡報頁數請規劃在 5 至 8 頁之間。\n"
            f"請務必包含：\n"
            f"1. 首頁 (版面必須設為 'title_slide')。\n"
            f"2. 其他頁面，請根據內容自由調配為標準條列式 ('bullets') 或左右雙欄對比式 ('two_columns')。\n"
            f"3. 內容請以使用者提問的語言 (繁體中文) 回覆，結構必須符合 PPTOutline JSON 格式。"
        )

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PPTOutline,
                temperature=0.7,
            )
        )

        outline = PPTOutline.model_validate_json(response.text)
        await status_message.edit_text("🎨 內容大綱生成完畢！正在為您排版並繪製簡報...")

        prs = create_presentation(outline, theme)

        os.makedirs("outputs", exist_ok=True)
        safe_topic = "".join(c for c in topic if c.isalnum() or c in (" ", "_", "-")).strip()[:20]
        safe_topic = safe_topic.replace(" ", "_")
        filename = f"outputs/{safe_topic}_{theme}_{int(time.time())}.pptx"
        prs.save(filename)

        await status_message.edit_text("📤 簡報排版完成，正在發送檔案...")

        with open(filename, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"{topic}_{theme}.pptx",
                caption=f"✅ 成功為您生成簡報！\n\n主題：{topic}\n風格主題：{theme.upper()}\n總頁數：{len(outline.slides)} 頁"
            )

        await status_message.delete()
        if os.path.exists(filename):
            os.remove(filename)

    except Exception as e:
        logger.exception("生成 PPT 時發生錯誤")
        await status_message.edit_text(f"❌ 簡報生成失敗，錯誤訊息：\n`{str(e)}`")

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /draw 指令，呼叫 Imagen 3 生成圖片並發送給使用者。"""
    if not client:
        await update.message.reply_text("❌ 伺服器未設定 GEMINI_API_KEY，無法使用 AI 功能。")
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ 請輸入圖片描述！\n"
            "用法：`/draw <圖片描述>` 或 `/draw [比例] <圖片描述>`\n"
            "可用比例：`1:1`、`16:9`、`9:16`、`4:3`、`3:4`\n"
            "例如：`/draw 16:9 壯麗的富士山櫻花季`"
        )
        return

    # 支援的長寬比例清單
    valid_aspect_ratios = ["1:1", "16:9", "9:16", "4:3", "3:4"]
    aspect_ratio = "1:1"
    first_arg = args[0]

    # 檢查第一個參數是否為長寬比
    if first_arg in valid_aspect_ratios:
        aspect_ratio = first_arg
        prompt_text = " ".join(args[1:])
    else:
        prompt_text = " ".join(args)

    if not prompt_text.strip():
        await update.message.reply_text("❌ 請輸入有效的圖片描述！")
        return

    status_message = await update.message.reply_text(
        f"⏳ 正在使用 Imagen 3 生成圖片...\n"
        f"• 描述：『{prompt_text}』\n"
        f"• 比例：{aspect_ratio}\n"
        f"（這可能需要 10-15 秒，請稍候...）"
    )

    try:
        # 呼叫 Imagen 3 圖片生成模型
        response = client.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=prompt_text,
            config=dict(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio=aspect_ratio,
            )
        )

        if not response.generated_images:
            raise Exception("Imagen API 沒有回傳任何圖片。")

        # 更新進度提示
        await status_message.edit_text("📤 圖片生成成功，正在上傳...")

        # 發送圖片
        for gen_img in response.generated_images:
            image_bytes = gen_img.image.image_bytes
            
            # 使用 io.BytesIO 包裝二進位資料，免去存檔的步驟
            await update.message.reply_photo(
                photo=io.BytesIO(image_bytes),
                caption=(
                    f"🎨 **AI 圖片生成完成！**\n\n"
                    f"📝 描述：{prompt_text}\n"
                    f"📐 比例：{aspect_ratio}"
                )
            )

        # 刪除等待提示
        await status_message.delete()

    except Exception as e:
        logger.exception("生成圖片時發生錯誤")
        await status_message.edit_text(f"❌ 圖片生成失敗，錯誤訊息：\n`{str(e)}`")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    reply_text = f"收到您的訊息：『{user_text}』\n（這是 Echo 測試）"
    await update.message.reply_text(reply_text)

def main() -> None:
    if not BOT_TOKEN:
        logger.error("錯誤：請確認已在 .env 檔案中設定 TELEGRAM_BOT_TOKEN！")
        print("【系統提示】請先複製 .env.example 並命名為 .env，填入您的 Token 後再啟動。")
        return

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ppt", generate_ppt))
    application.add_handler(CommandHandler("draw", generate_image))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    logger.info("機器人 (Lab 3) 已啟動，正在接聽訊息...")
    application.run_polling()

if __name__ == "__main__":
    main()
