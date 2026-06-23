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
from PIL import Image

# 引入 PPT 生成模組與資料結構 (維持 Lab 2/3 功能)
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
    """歡迎訊息，列出所有可用指令。"""
    welcome_text = (
        f"哈囉 {update.effective_user.first_name}！我是您的 Telegram 智慧小助手。🤖\n\n"
        "目前已升級為 **Lab 4：AI 圖片修改版本**！\n"
        "您可以上傳圖片，並透過對話告訴我如何修改這張圖片。\n\n"
        "📸 **新增功能 - 圖片修改：**\n"
        "• 直接上傳一張圖片至對話框。\n"
        "• 接著傳送文字，告訴我您想做什麼修改（如：<i>「在桌面上加一個馬克杯」</i>）。\n"
        "• 輸入 `/cancel` 可以取消圖片修改操作。\n\n"
        "🎨 **圖片生成：**\n"
        "• `/draw [比例] <描述>` (例：`/draw 16:9 賽博朋克貓咪`)\n\n"
        "📊 **簡報生成：**\n"
        "• `/ppt [light|dark] <主題>` (例：`/ppt 區塊鏈的技術架構`)"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """指令說明。"""
    help_text = (
        "💡 **可用指令說明：**\n"
        "• `/start` - 重啟小助手並顯示歡迎說明\n"
        "• `/help` - 顯示指令清單\n"
        "• `/ppt [light|dark] <主題>` - 生成簡報投影片檔案 (.pptx)\n"
        "• `/draw [比例] <圖片描述>` - 生成 AI 圖片 (1:1, 16:9, 9:16 等)\n"
        "• 直接上傳圖片 - 啟動圖片修改流程\n"
        "• `/cancel` - 取消目前的圖片修改操作\n"
        "• 直接發送文字訊息 - 回覆相同內容（Echo 測試）"
    )
    await update.message.reply_text(help_text)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """取消目前的圖片修改操作。"""
    state = context.user_data.get('state')
    if state == 'waiting_for_edit_prompt':
        uploaded_path = context.user_data.get('uploaded_img_path')
        if uploaded_path and os.path.exists(uploaded_path):
            try:
                os.remove(uploaded_path)
            except Exception:
                pass
        context.user_data.pop('state', None)
        context.user_data.pop('uploaded_img_path', None)
        await update.message.reply_text("🚫 已取消圖片修改操作。")
    else:
        await update.message.reply_text("目前沒有進行中的圖片修改操作。")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """接收上傳的圖片，並進入等待修改指令狀態。"""
    photo_file = await update.message.photo[-1].get_file()
    
    os.makedirs("outputs", exist_ok=True)
    filename = f"outputs/uploaded_{update.effective_user.id}_{int(time.time())}.jpg"
    await photo_file.download_to_drive(filename)
    
    context.user_data['state'] = 'waiting_for_edit_prompt'
    context.user_data['uploaded_img_path'] = filename
    
    await update.message.reply_text(
        "📸 <b>已收到您的圖片！</b>\n\n"
        "請直接回覆我您想對這張圖進行什麼<b>修改</b>。\n"
        "（例如：<i>「將背景換成粉紅色的櫻花林」</i>、<i>「在盤子裡加一顆蘋果」</i>）\n\n"
        "若想放棄修改，請輸入 /cancel。",
        parse_mode="HTML"
    )

async def process_image_modification(update: Update, context: ContextTypes.DEFAULT_TYPE, user_instruction: str) -> None:
    """整合 Gemini 3.5 Flash 與 Imagen 3 進行圖像修改與回傳。"""
    uploaded_path = context.user_data.get('uploaded_img_path')
    
    if not uploaded_path or not os.path.exists(uploaded_path):
        await update.message.reply_text("❌ 找不到上傳的圖片快取，請重新上傳圖片！")
        context.user_data.pop('state', None)
        return
        
    status_message = await update.message.reply_text("⏳ 正在使用 Gemini 3.5 Flash 深度分析原圖與修改指令...")
    
    try:
        # 使用 PIL 開啟圖片
        img = Image.open(uploaded_path)
        
        # 呼叫 Gemini 多模態生成英文的詳細修改描述詞
        prompt = (
            f"Here is an image uploaded by the user, and they want to modify it with this instruction: \"{user_instruction}\".\n\n"
            f"Tasks:\n"
            f"1. Analyze the original image's main subjects, composition, and style (e.g., photo, digital art, watercolor, anime, sketch).\n"
            f"2. Incorporate the user's modification request seamlessly.\n"
            f"3. Generate a highly detailed, descriptive English prompt for an Image Generation model (Imagen 3) to generate the final modified image. "
            f"The prompt must preserve the style, mood, and main subject features of the original image, making the new image look like an edited version of the original.\n"
            f"4. Output ONLY the English prompt. Do not include any explanations, introduction, or markdown wrapping."
        )
        
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[img, prompt]
        )
        
        detailed_prompt = response.text.strip()
        logger.info(f"Gemini 生成的修改提示詞: {detailed_prompt}")
        
        await status_message.edit_text("🎨 圖像分析完成！正在使用 Imagen 3 生成修改後的圖片，這需要 10-15 秒，請稍候...")
        
        # 呼叫 Imagen 3 生成修改後的圖片
        response_img = client.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=detailed_prompt,
            config=dict(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio="1:1"
            )
        )
        
        if not response_img.generated_images:
            raise Exception("Imagen API 沒有回傳任何圖片。")
            
        await status_message.edit_text("📤 圖片修改完成，正在上傳...")
        
        # 發送圖片
        for gen_img in response_img.generated_images:
            image_bytes = gen_img.image.image_bytes
            await update.message.reply_photo(
                photo=io.BytesIO(image_bytes),
                caption=(
                    f"✨ **圖片修改完成！**\n\n"
                    f"📝 您的修改指令：{user_instruction}"
                )
            )

    except Exception as e:
        logger.exception("圖片修改過程中發生錯誤")
        await update.message.reply_text(f"❌ 圖片修改失敗，原因：`{str(e)}`")
    finally:
        # 清理暫存的原圖與對話狀態
        if os.path.exists(uploaded_path):
            try:
                os.remove(uploaded_path)
            except Exception:
                pass
        context.user_data.pop('state', None)
        context.user_data.pop('uploaded_img_path', None)
        await status_message.delete()

async def generate_ppt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /ppt 指令，呼叫 Gemini 生成大綱並繪製成 PPTX 傳送。"""
    if not client:
        await update.message.reply_text("❌ 伺服器未設定 GEMINI_API_KEY，無法使用 AI 功能。")
        return

    args = context.args
    if not args:
        await update.message.reply_text("❌ 請輸入簡報主題！\n用法：`/ppt <主題>` 或 `/ppt [light|dark] <主題>`")
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
    """處理 /draw 指令，呼叫 Imagen 3 生成圖片。"""
    if not client:
        await update.message.reply_text("❌ 伺服器未設定 GEMINI_API_KEY，無法使用 AI 功能。")
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ 請輸入圖片描述！\n"
            "用法：`/draw <圖片描述>` 或 `/draw [比例] <圖片描述>`\n"
            "可用比例：`1:1`、`16:9`、`9:16`、`4:3`、`3:4`"
        )
        return

    valid_aspect_ratios = ["1:1", "16:9", "9:16", "4:3", "3:4"]
    aspect_ratio = "1:1"
    first_arg = args[0]

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

        await status_message.edit_text("📤 圖片生成成功，正在上傳...")

        for gen_img in response.generated_images:
            image_bytes = gen_img.image.image_bytes
            await update.message.reply_photo(
                photo=io.BytesIO(image_bytes),
                caption=(
                    f"🎨 **AI 圖片生成完成！**\n\n"
                    f"📝 描述：{prompt_text}\n"
                    f"📐 比例：{aspect_ratio}"
                )
            )

        await status_message.delete()

    except Exception as e:
        logger.exception("生成圖片時發生錯誤")
        await status_message.edit_text(f"❌ 圖片生成失敗，錯誤訊息：\n`{str(e)}`")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理普通文字訊息。如果是在等待修改指令狀態，就執行修改流程；否則執行 Echo。"""
    user_state = context.user_data.get('state')
    user_text = update.message.text
    
    if user_state == 'waiting_for_edit_prompt':
        await process_image_modification(update, context, user_text)
    else:
        reply_text = f"收到您的訊息：『{user_text}』\n（這是 Echo 測試）"
        await update.message.reply_text(reply_text)

def main() -> None:
    if not BOT_TOKEN:
        logger.error("錯誤：請確認已在 .env 檔案中設定 TELEGRAM_BOT_TOKEN！")
        return

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("ppt", generate_ppt))
    application.add_handler(CommandHandler("draw", generate_image))
    
    # 處理相片上傳
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    # 處理一般文字
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("機器人 (Lab 4) 已啟動，正在接聽訊息...")
    application.run_polling()

if __name__ == "__main__":
    main()
