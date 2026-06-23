import logging
import os
import time
import io
import html
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from google import genai
from google.genai import types
from PIL import Image

# 引入本機資料庫與簡報模組
from database import init_db, add_note, get_notes, delete_note
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
    welcome_text = (
        f"哈囉 {update.effective_user.first_name}！我是您的 Telegram 智慧小助手。🤖\n\n"
        "目前已升級為 **Lab 5：個人隨手筆記本整合版 (最終版)**！\n"
        "您可以使用小助手來記錄日常筆記、產生簡報、繪製與修改圖片。\n\n"
        "📝 **隨手筆記本功能：**\n"
        "• `/addnote <內容>` - 新增一筆筆記 (例：`/addnote 下午記得買咖啡`)\n"
        "• `/notes` - 查詢筆記清單，可直接點選按鈕進行刪除\n\n"
        "📸 **圖片修改功能：**\n"
        "• 直接上傳一張圖片至對話框，並回覆您想做什麼修改。\n\n"
        "🎨 **圖片生成功能：**\n"
        "• `/draw [比例] <描述>` (例：`/draw 16:9 賽博朋克貓咪`)\n\n"
        "📊 **簡報生成功能：**\n"
        "• `/ppt [light|dark] <主題>` (例：`/ppt 區塊鏈的技術架構`)"
    )
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "💡 **可用指令清單：**\n"
        "• `/start` - 重啟小助手並顯示歡迎說明\n"
        "• `/help` - 顯示指令清單\n"
        "• `/addnote <內容>` - 新增一筆隨手筆記\n"
        "• `/notes` - 列出個人所有筆記並提供刪除按鈕\n"
        "• `/ppt [light|dark] <主題>` - 生成簡報投影片檔案 (.pptx)\n"
        "• `/draw [比例] <描述>` - 生成 AI 圖片\n"
        "• 直接上傳圖片 - 啟動圖片修改流程\n"
        "• `/cancel` - 取消目前的圖片修改操作\n"
        "• 直接傳送文字 - 回覆相同內容（Echo 測試）"
    )
    await update.message.reply_text(help_text)

# --- 隨手筆記本 (Note-Taking) 處理函數 ---

def format_notes_message(notes: list) -> tuple:
    """將筆記清單格式化為 HTML 訊息與 Inline 刪除鍵盤。"""
    text = "📝 <b>您的個人隨手筆記清單：</b>\n\n"
    keyboard = []
    row = []
    
    for idx, (note_id, content, created_at) in enumerate(notes, 1):
        short_content = content[:25] + "..." if len(content) > 25 else content
        escaped_content = html.escape(short_content)
        
        # 顯示格式： 數字. 內容 (時間)
        text += f"<b>{idx}.</b> {escaped_content} <i>({created_at[5:16]})</i>\n"
        
        # 建立專屬刪除按鈕
        button = InlineKeyboardButton(f"🗑️ {idx}", callback_data=f"delnote_{note_id}")
        row.append(button)
        # 每 5 個按鈕換一行
        if len(row) == 5:
            keyboard.append(row)
            row = []
            
    if row:
        keyboard.append(row)
        
    text += "\n💡 點擊下方對應的數字按鈕可直接<b>刪除</b>該筆記。"
    return text, InlineKeyboardMarkup(keyboard)

async def add_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /addnote 指令，新增筆記。"""
    user_id = update.effective_user.id
    content = " ".join(context.args)
    
    if not content.strip():
        await update.message.reply_text("❌ 筆記內容不能為空！\n用法：`/addnote <內容>`\n例如：`/addnote 明天記得倒垃圾`")
        return
        
    add_note(user_id, content)
    await update.message.reply_text("📝 <b>筆記儲存成功！</b>", parse_mode="HTML")

async def list_notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /notes 指令，列出所有筆記。"""
    user_id = update.effective_user.id
    notes = get_notes(user_id)
    
    if not notes:
        await update.message.reply_text(
            "📝 <b>您目前沒有任何筆記！</b>\n\n使用 <code>/addnote &lt;內容&gt;</code> 來新增第一筆筆記。",
            parse_mode="HTML"
        )
        return
        
    text, reply_markup = format_notes_message(notes)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)

async def delete_note_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """點擊按鈕直接刪除筆記，並原地重新整理訊息內容。"""
    query = update.callback_query
    await query.answer() # 停止載入中的圈圈
    
    user_id = update.effective_user.id
    note_id = int(query.data.split("_")[1])
    
    # 執行刪除
    success = delete_note(user_id, note_id)
    
    if success:
        notes = get_notes(user_id)
        if not notes:
            await query.edit_message_text(
                "📝 <b>您目前沒有任何筆記！</b>\n\n使用 <code>/addnote &lt;內容&gt;</code> 來新增第一筆筆記。",
                parse_mode="HTML"
            )
        else:
            text, reply_markup = format_notes_message(notes)
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await query.message.reply_text("❌ 刪除筆記失敗，該筆記可能已被刪除。")

# --- 圖片修改與生成 (維持 Lab 4 功能) ---

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    photo_file = await update.message.photo[-1].get_file()
    os.makedirs("outputs", exist_ok=True)
    filename = f"outputs/uploaded_{update.effective_user.id}_{int(time.time())}.jpg"
    await photo_file.download_to_drive(filename)
    
    context.user_data['state'] = 'waiting_for_edit_prompt'
    context.user_data['uploaded_img_path'] = filename
    
    await update.message.reply_text(
        "📸 <b>已收到您的圖片！</b>\n\n"
        "請直接回覆我您想對這張圖進行什麼<b>修改</b>。\n"
        "（例如：<i>「把背景換成粉紅色的櫻花林」</i>）\n\n"
        "如果您想放棄修改，請輸入 /cancel。",
        parse_mode="HTML"
    )

async def process_image_modification(update: Update, context: ContextTypes.DEFAULT_TYPE, user_instruction: str) -> None:
    uploaded_path = context.user_data.get('uploaded_img_path')
    if not uploaded_path or not os.path.exists(uploaded_path):
        await update.message.reply_text("❌ 找不到上傳的圖片快取，請重新上傳！")
        context.user_data.pop('state', None)
        return
        
    status_message = await update.message.reply_text("⏳ 正在使用 Gemini 3.5 Flash 深度分析原圖與修改指令...")
    try:
        img = Image.open(uploaded_path)
        prompt = (
            f"Here is an image uploaded by the user, and they want to modify it with this instruction: \"{user_instruction}\".\n\n"
            f"Tasks:\n"
            f"1. Analyze the original image's main subjects, composition, and style.\n"
            f"2. Incorporate the user's modification request seamlessly.\n"
            f"3. Generate a highly detailed, descriptive English prompt for an Image Generation model (Imagen 3) to generate the final modified image. "
            f"The prompt must preserve the style, mood, and main subject features of the original image.\n"
            f"4. Output ONLY the English prompt. Do not include explanations, introduction, or markdown wrapping."
        )
        
        response = client.models.generate_content(model=GEMINI_MODEL, contents=[img, prompt])
        detailed_prompt = response.text.strip()
        
        await status_message.edit_text("🎨 圖像分析完成！正在使用 Imagen 3 生成修改後的圖片...")
        
        response_img = client.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=detailed_prompt,
            config=dict(number_of_images=1, output_mime_type="image/jpeg", aspect_ratio="1:1")
        )
        
        if not response_img.generated_images:
            raise Exception("Imagen API 沒有回傳任何圖片。")
            
        await status_message.edit_text("📤 圖片修改完成，正在上傳...")
        for gen_img in response_img.generated_images:
            image_bytes = gen_img.image.image_bytes
            await update.message.reply_photo(
                photo=io.BytesIO(image_bytes),
                caption=(
                    f"✨ **圖片修改完成！**\n\n"
                    f"📝 修改指令：{user_instruction}"
                )
            )
        
    except Exception as e:
        logger.exception("圖片修改過程中發生錯誤")
        await update.message.reply_text(f"❌ 圖片修改失敗，原因：`{str(e)}`")
    finally:
        if os.path.exists(uploaded_path):
            try:
                os.remove(uploaded_path)
            except Exception:
                pass
        context.user_data.pop('state', None)
        context.user_data.pop('uploaded_img_path', None)
        await status_message.delete()

async def generate_ppt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not client:
        await update.message.reply_text("❌ 伺服器未設定 GEMINI_API_KEY。")
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
    if not client:
        await update.message.reply_text("❌ 伺服器未設定 GEMINI_API_KEY。")
        return

    args = context.args
    if not args:
        await update.message.reply_text("❌ 請輸入圖片描述！\n用法：`/draw [比例] <描述>`")
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

    status_message = await update.message.reply_text(f"⏳ 正在使用 Imagen 3 生成圖片...")
    try:
        response = client.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=prompt_text,
            config=dict(number_of_images=1, output_mime_type="image/jpeg", aspect_ratio=aspect_ratio)
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
    user_state = context.user_data.get('state')
    user_text = update.message.text
    if user_state == 'waiting_for_edit_prompt':
        await process_image_modification(update, context, user_text)
    else:
        reply_text = f"收到您的訊息：『{user_text}』\n（這是 Echo 測試）"
        await update.message.reply_text(reply_text)

def main() -> None:
    init_db()
    if not BOT_TOKEN:
        logger.error("錯誤：請確認已在 .env 檔案中設定 TELEGRAM_BOT_TOKEN！")
        return

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # 註冊指令與處理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # 筆記本功能
    application.add_handler(CommandHandler("addnote", add_note_command))
    application.add_handler(CommandHandler("notes", list_notes_command))
    application.add_handler(CallbackQueryHandler(delete_note_callback, pattern="^delnote_\\d+$"))
    
    # 簡報與圖片生成
    application.add_handler(CommandHandler("ppt", generate_ppt))
    application.add_handler(CommandHandler("draw", generate_image))
    
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("機器人 (Lab 5 - 最終版) 已啟動，正在接聽訊息...")
    application.run_polling()

if __name__ == "__main__":
    main()
