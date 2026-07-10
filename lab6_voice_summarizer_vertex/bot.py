import logging
import os
import time
import io
import html
import asyncio
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
from database import (
    init_db,
    add_note,
    get_notes,
    delete_note,
    add_voice_note,
    get_voice_notes,
    get_voice_note_by_id,
    delete_voice_note,
)
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

# 初始化 Vertex AI Client
client = None
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "little-shrimp")
GCP_LOCATION = os.getenv("GCP_LOCATION", "global")

# 1. 如果有設定 GEMINI_API_KEY 且為 Vertex AI API 金鑰 (以 AQ. 開頭)，優先使用金鑰模式
if GEMINI_API_KEY and GEMINI_API_KEY.startswith("AQ."):
    try:
        # Vertex AI Express 金鑰模式下，不能設定 project/location，由金鑰本身自動對接專案
        client = genai.Client(
            vertexai=True,
            api_key=GEMINI_API_KEY
        )
        logger.info("已成功以 Vertex AI API 金鑰模式 (AQ. 憑證) 啟動 Client")
    except Exception as e:
        logger.exception(f"使用 Vertex AI API 金鑰啟動失敗: {e}")

# 2. 否則，使用本地 gcp-key.json 服務帳戶模式
else:
    gcp_key_path = os.path.join(os.path.dirname(__file__), "gcp-key.json")
    if os.path.exists(gcp_key_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = gcp_key_path
        logger.info("已偵測到本地 gcp-key.json，已將其設定為 GOOGLE_APPLICATION_CREDENTIALS")
    
    try:
        client = genai.Client(
            vertexai=True,                # 啟用 Vertex AI 模式
            project=GCP_PROJECT_ID,       # GCP 專案 ID
            location=GCP_LOCATION         # GCP 伺服器地區
        )
        logger.info(f"已使用 Vertex AI 服務帳戶模式啟動 (Project: {GCP_PROJECT_ID}, Location: {GCP_LOCATION})")
    except Exception as e:
        logger.exception(f"Vertex AI 初始化失敗: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome_text = (
        f"哈囉 {update.effective_user.first_name}！我是您的 Telegram 智慧小助手 (Vertex AI 版)。🤖\n\n"
        "目前已升級為 **Lab 6：語音轉譯與摘要功能 Vertex AI 整合版 (最新版)**！\n"
        "您可以使用小助手來記錄日常隨手筆記、錄製語音筆記、產生簡報、繪製與修改圖片。\n\n"
        "🎙️ **語音筆記功能 (Lab 6)：**\n"
        "• 直接對我發送一個語音訊息，我會自動為您轉譯文字並撰寫摘要，且提供儲存按鈕。\n"
        "• `/voicenotes` - 查詢語音筆記清單，可直接重聽、查看原文或刪除。\n\n"
        "📝 **隨手筆記本功能：**\n"
        "• `/addnote <內容>` - 新增一筆文字筆記 (例：`/addnote 下午記得買咖啡`)\n"
        "• `/notes` - 查詢文字筆記清單，可直接點選按鈕進行刪除\n\n"
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
        "• `/notes` - 列出個人所有文字筆記與刪除按鈕\n"
        "• `/voicenotes` - 列出個人所有語音筆記，提供播放、查看原文與刪除按鈕\n"
        "• `/ppt [light|dark] <主題>` - 生成簡報投影片檔案 (.pptx)\n"
        "• `/draw [比例] <描述>` - 生成 AI 圖片\n"
        "• 直接傳送語音 - 自動進行語音轉譯與摘要分析\n"
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
        
    # 非同步執行資料庫操作
    await asyncio.to_thread(add_note, user_id, content)
    await update.message.reply_text("📝 <b>筆記儲存成功！</b>", parse_mode="HTML")

async def list_notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /notes 指令，列出所有筆記。"""
    user_id = update.effective_user.id
    notes = await asyncio.to_thread(get_notes, user_id)
    
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
    
    # 非同步執行資料庫刪除
    success = await asyncio.to_thread(delete_note, user_id, note_id)
    
    if success:
        notes = await asyncio.to_thread(get_notes, user_id)
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


# --- Lab 6：語音轉譯與摘要功能處理函數 ---

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理接收到的語音訊息，下載並呼叫 Gemini 進行語音轉譯與摘要。"""
    if not client:
        await update.message.reply_text("❌ 伺服器未設定 GEMINI_API_KEY，語音功能無法使用。")
        return

    voice = update.message.voice
    file_id = voice.file_id
    duration = voice.duration # 語音時長（秒）

    status_message = await update.message.reply_text("⏳ 收到語音訊息！正在下載音檔...")
    
    os.makedirs("outputs", exist_ok=True)
    temp_filename = f"outputs/voice_{update.effective_user.id}_{int(time.time())}.ogg"

    try:
        # 下載語音檔 (Telegram 語音通常是 .ogg / Opus 編碼)
        voice_file = await voice.get_file()
        await voice_file.download_to_drive(temp_filename)

        await status_message.edit_text("🤖 正在使用 Gemini 原生多模態音訊引擎進行轉譯與分析...")

        # 讀取音訊為 bytes 並非同步呼叫 Gemini 進行處理
        def run_audio_transcription():
            with open(temp_filename, "rb") as f:
                audio_bytes = f.read()

            prompt = (
                "請你扮演一個專業的助理。以下是使用者傳送的語音訊息音訊檔。\n"
                "請完成以下任務：\n"
                "1. 將語音逐字完整轉譯成文字（若是中文，請使用繁體中文）。\n"
                "2. 針對轉譯後的文字，寫一段精簡、重點明確的摘要。\n\n"
                "輸出格式請嚴格符合以下結構，不需要額外的說明文字：\n"
                "【語音轉譯】\n"
                "(在這裡輸出逐字轉譯內容)\n\n"
                "【內容摘要】\n"
                "(在這裡輸出重點摘要)"
            )

            return client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
                    prompt
                ]
            )

        response = await asyncio.to_thread(run_audio_transcription)
        result_text = response.text.strip()

        # 解析轉譯全文與摘要
        transcription = ""
        summary = ""

        if "【語音轉譯】" in result_text and "【內容摘要】" in result_text:
            parts = result_text.split("【內容摘要】")
            transcription = parts[0].replace("【語音轉譯】", "").strip()
            summary = parts[1].strip()
        else:
            transcription = result_text
            summary = result_text[:100] + "..." if len(result_text) > 100 else result_text

        # 暫存語音資料至 user_data，以供後續儲存
        context.user_data['temp_voice_note'] = {
            'file_id': file_id,
            'transcription': transcription,
            'summary': summary,
            'duration': duration
        }

        # 格式化回傳訊息
        response_msg = (
            f"🎙️ <b>語音轉譯與分析結果</b> <i>(時長: {duration} 秒)</i>\n\n"
            f"📝 <b>逐字轉譯：</b>\n<i>{html.escape(transcription)}</i>\n\n"
            f"💡 <b>核心摘要：</b>\n<b>{html.escape(summary)}</b>\n\n"
            f"❓ 是否將此筆記儲存至您的語音筆記本？"
        )

        keyboard = [[
            InlineKeyboardButton("💾 儲存至語音筆記", callback_data="save_voice_note"),
            InlineKeyboardButton("❌ 不儲存", callback_data="discard_voice_note")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(response_msg, parse_mode="HTML", reply_markup=reply_markup)

    except Exception as e:
        logger.exception("處理語音轉譯時發生錯誤")
        await update.message.reply_text(f"❌ 語音處理失敗，錯誤原因：`{str(e)}`")
    finally:
        # 確保刪除下載的暫存語音檔，防止資源洩漏
        if os.path.exists(temp_filename):
            try:
                await asyncio.to_thread(os.remove, temp_filename)
            except Exception as e:
                logger.warning(f"清理語音暫存檔失敗: {e}")
        try:
            await status_message.delete()
        except Exception:
            pass

async def save_voice_note_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """點擊按鈕將暫存的語音筆記儲存至資料庫。"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    temp_data = context.user_data.get('temp_voice_note')

    if not temp_data:
        await query.message.reply_text("❌ 找不到暫存的語音資料，可能已過期，請重新發送語音！")
        return

    # 非同步儲存至資料庫
    await asyncio.to_thread(
        add_voice_note,
        user_id=user_id,
        file_id=temp_data['file_id'],
        transcription=temp_data['transcription'],
        summary=temp_data['summary'],
        duration=temp_data['duration']
    )

    context.user_data.pop('temp_voice_note', None)
    
    # 移除原訊息底部的儲存按鈕，防止重複點擊
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("💾 <b>語音筆記已成功儲存！</b>\n您可以透過 `/voicenotes` 指令來查看。", parse_mode="HTML")

async def discard_voice_note_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """點擊按鈕捨棄暫存的語音資訊，不儲存。"""
    query = update.callback_query
    await query.answer()

    # 清理暫存
    context.user_data.pop('temp_voice_note', None)
    
    # 移除原訊息底部的按鈕，並編輯原訊息標記已捨棄
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("🚫 <b>語音筆記已捨棄，未儲存。</b>", parse_mode="HTML")

def format_voice_notes_message(notes: list) -> tuple:
    """將語音筆記清單格式化為 HTML 訊息與控制鍵盤。"""
    text = "🎙️ <b>您的個人語音筆記清單：</b>\n\n"
    keyboard = []
    
    for idx, (note_id, file_id, transcription, summary, duration, created_at) in enumerate(notes, 1):
        short_summary = summary[:25] + "..." if len(summary) > 25 else summary
        escaped_summary = html.escape(short_summary)
        
        # 顯示格式： 數字. 摘要 (時長, 時間)
        text += f"<b>{idx}.</b> {escaped_summary} <i>({duration}s, {created_at[5:16]})</i>\n"
        
        # 每一筆語音筆記提供一排按鈕：📄詳細 🔊重播 🗑️刪除
        row = [
            InlineKeyboardButton(f"📄 {idx}", callback_data=f"vdet_{note_id}"),
            InlineKeyboardButton(f"🔊 {idx}", callback_data=f"vplay_{note_id}"),
            InlineKeyboardButton(f"🗑️ {idx}", callback_data=f"vdel_{note_id}")
        ]
        keyboard.append(row)
        
    text += "\n💡 按鈕說明：\n📄 查看轉譯原文 | 🔊 重新發送語音 | 🗑️ 刪除筆記"
    return text, InlineKeyboardMarkup(keyboard)

async def list_voice_notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """處理 /voicenotes 指令，列出所有語音筆記。"""
    user_id = update.effective_user.id
    notes = await asyncio.to_thread(get_voice_notes, user_id)
    
    if not notes:
        await update.message.reply_text(
            "🎙️ <b>您目前沒有任何語音筆記！</b>\n\n直接對我<b>發送語音訊息</b>，即可開始體驗語音轉譯與摘要功能。",
            parse_mode="HTML"
        )
        return
        
    text, reply_markup = format_voice_notes_message(notes)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)

async def view_voice_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """查看特定語音筆記的詳細轉譯原文。"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    note_id = int(query.data.split("_")[1])

    note = await asyncio.to_thread(get_voice_note_by_id, user_id, note_id)
    if not note:
        await query.message.reply_text("❌ 找不到該筆語音筆記。")
        return

    _, file_id, transcription, summary, duration, created_at = note

    detail_msg = (
        f"🎙️ <b>語音筆記詳細內容</b>\n"
        f"📅 建立時間：{created_at}\n"
        f"⏱️ 語音長度：{duration} 秒\n\n"
        f"💡 <b>核心摘要：</b>\n{html.escape(summary)}\n\n"
        f"📝 <b>轉譯全文：</b>\n<i>{html.escape(transcription)}</i>"
    )

    await query.message.reply_text(detail_msg, parse_mode="HTML")

async def play_voice_note_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """利用 Telegram 的 file_id 重新傳送該語音給使用者進行重播。"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    note_id = int(query.data.split("_")[1])

    note = await asyncio.to_thread(get_voice_note_by_id, user_id, note_id)
    if not note:
        await query.message.reply_text("❌ 找不到該筆語音筆記。")
        return

    _, file_id, transcription, summary, duration, created_at = note

    try:
        await context.bot.send_voice(
            chat_id=update.effective_chat.id,
            voice=file_id,
            caption=f"🔊 播放語音筆記 <i>({created_at[5:16]})</i>",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.exception("重新發送語音時發生錯誤")
        await query.message.reply_text(f"❌ 播放失敗，錯誤原因：{str(e)}")

async def delete_voice_note_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """點擊刪除語音筆記按鈕，原地刷新列表。"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    note_id = int(query.data.split("_")[1])

    success = await asyncio.to_thread(delete_voice_note, user_id, note_id)

    if success:
        notes = await asyncio.to_thread(get_voice_notes, user_id)
        if not notes:
            await query.edit_message_text(
                "🎙️ <b>您目前沒有任何語音筆記！</b>\n\n直接對我<b>發送語音訊息</b>，即可開始體驗語音轉譯與摘要功能。",
                parse_mode="HTML"
            )
        else:
            text, reply_markup = format_voice_notes_message(notes)
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await query.message.reply_text("❌ 刪除語音筆記失敗，該筆記可能已被刪除。")


# --- 圖片修改與生成 (重構為 asyncio.to_thread 防阻塞) ---

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.user_data.get('state')
    if state == 'waiting_for_edit_prompt':
        uploaded_path = context.user_data.get('uploaded_img_path')
        if uploaded_path and os.path.exists(uploaded_path):
            try:
                await asyncio.to_thread(os.remove, uploaded_path)
            except Exception:
                pass
        context.user_data.pop('state', None)
        context.user_data.pop('uploaded_img_path', None)
        await update.message.reply_text("🚫 已取消圖片修改操作。")
    else:
        await update.message.reply_text("目前沒有進行中的圖片修改操作。")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # 預先清理此使用者殘留的舊暫存檔，防堵儲存空間洩漏
    old_path = context.user_data.get('uploaded_img_path')
    if old_path and os.path.exists(old_path):
        try:
            await asyncio.to_thread(os.remove, old_path)
        except Exception as e:
            logger.warning(f"清理舊暫存檔失敗: {e}")

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
    if not client:
        await update.message.reply_text("❌ 伺服器未設定 GEMINI_API_KEY，無法使用修改功能。")
        context.user_data.pop('state', None)
        return

    uploaded_path = context.user_data.get('uploaded_img_path')
    if not uploaded_path or not os.path.exists(uploaded_path):
        await update.message.reply_text("❌ 找不到上傳的圖片快取，請重新上傳！")
        context.user_data.pop('state', None)
        return
        
    status_message = await update.message.reply_text("⏳ 正在使用 Gemini 3.5 Flash 深度分析原圖與修改指令...")
    try:
        # 將 Pillow 與 API 耗時操作放入執行緒
        img = await asyncio.to_thread(Image.open, uploaded_path)
        prompt = (
            f"Here is an image uploaded by the user, and they want to modify it with this instruction: \"{user_instruction}\".\n\n"
            f"Tasks:\n"
            f"1. Analyze the original image's main subjects, composition, and style.\n"
            f"2. Incorporate the user's modification request seamlessly.\n"
            f"3. Generate a highly detailed, descriptive English prompt for an Image Generation model (Imagen 3) to generate the final modified image. "
            f"The prompt must preserve the style, mood, and main subject features of the original image.\n"
            f"4. Output ONLY the English prompt. Do not include explanations, introduction, or markdown wrapping."
        )
        
        response = await asyncio.to_thread(client.models.generate_content, model=GEMINI_MODEL, contents=[img, prompt])
        detailed_prompt = response.text.strip()
        
        await status_message.edit_text(f"🎨 圖像分析完成！正在使用 {IMAGEN_MODEL} 生成修改後的圖片...")
        
        if IMAGEN_MODEL.startswith("gemini-"):
            response_img = await asyncio.to_thread(
                client.models.generate_content,
                model=IMAGEN_MODEL,
                contents=detailed_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio="1:1"
                    )
                )
            )
            if not response_img.candidates or not response_img.candidates[0].content.parts:
                raise Exception(f"{IMAGEN_MODEL} 沒有回傳任何內容。")
            
            image_bytes = None
            for part in response_img.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    image_bytes = part.inline_data.data
                    break
            
            if not image_bytes:
                raise Exception("在 API 回傳內容中找不到修改後生成的圖片資料。")
        else:
            response_img = await asyncio.to_thread(
                client.models.generate_images,
                model=IMAGEN_MODEL,
                prompt=detailed_prompt,
                config=dict(number_of_images=1, output_mime_type="image/jpeg", aspect_ratio="1:1")
            )
            if not response_img.generated_images:
                raise Exception(f"{IMAGEN_MODEL} 沒有回傳任何圖片。")
            image_bytes = response_img.generated_images[0].image.image_bytes
            
        await status_message.edit_text("📤 圖片修改完成，正在上傳...")
        await update.message.reply_photo(
            photo=io.BytesIO(image_bytes),
            caption=(
                f"✨ **圖片修改完成！**\n\n"
                f"📝 修改指令：{user_instruction}\n"
                f"🤖 模型：{IMAGEN_MODEL}"
            ),
            read_timeout=60,
            write_timeout=60
        )
        
    except Exception as e:
        logger.exception("圖片修改過程中發生錯誤")
        await update.message.reply_text(f"❌ 圖片修改失敗，原因：`{str(e)}`")
    finally:
        # 嚴格確保暫存檔案被刪除
        if uploaded_path and os.path.exists(uploaded_path):
            try:
                await asyncio.to_thread(os.remove, uploaded_path)
            except Exception:
                pass
        context.user_data.pop('state', None)
        context.user_data.pop('uploaded_img_path', None)
        try:
            await status_message.delete()
        except Exception:
            pass

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
    filename = None
    try:
        prompt = (
            f"請針對主題『{topic}』設計一份具有學術或商業價值的簡報大綱與詳細頁面內容。\n"
            f"簡報頁數請規劃在 5 至 8 頁之間。\n"
            f"請務必包含：\n"
            f"1. 首頁 (版面必須設為 'title_slide')。\n"
            f"2. 其他頁面，請根據內容自由調配為標準條列式 ('bullets') 或左右雙欄對比式 ('two_columns')。\n"
            f"3. 內容請以使用者提問的語言 (繁體中文) 回覆，結構必須符合 PPTOutline JSON 格式。"
        )

        response = await asyncio.to_thread(
            client.models.generate_content,
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

        # 簡報排版與繪製放入執行緒
        prs = await asyncio.to_thread(create_presentation, outline, theme)
        
        os.makedirs("outputs", exist_ok=True)
        filtered_topic = "".join(c for c in topic if c.isalnum() or c in (" ", "_", "-")).strip()[:20]
        safe_topic = filtered_topic.replace(" ", "_") if filtered_topic else "presentation"
        filename = f"outputs/{safe_topic}_{theme}_{int(time.time())}.pptx"
        
        await asyncio.to_thread(prs.save, filename)

        await status_message.edit_text("📤 簡報排版完成，正在發送檔案...")
        with open(filename, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"{topic}_{theme}.pptx",
                caption=f"✅ 成功為您生成簡報！\n\n主題：{topic}\n風格主題：{theme.upper()}\n總頁數：{len(outline.slides)} 頁",
                read_timeout=60,
                write_timeout=60
            )
        try:
            await status_message.delete()
        except Exception:
            pass

    except Exception as e:
        logger.exception("生成 PPT 時發生錯誤")
        try:
            await status_message.edit_text(f"❌ 簡報生成失敗，錯誤訊息：\n`{str(e)}`")
        except Exception:
            await update.message.reply_text(f"❌ 簡報生成失敗，錯誤訊息：\n`{str(e)}`")
    finally:
        # 使用 try...finally 機制確保簡報暫存檔一定被刪除
        if filename and os.path.exists(filename):
            try:
                await asyncio.to_thread(os.remove, filename)
            except Exception as e:
                logger.warning(f"刪除臨時簡報檔案失敗: {e}")

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

    logger.info(f"收到生圖請求 - 比例: {aspect_ratio}, 描述: {prompt_text}")
    status_message = await update.message.reply_text(f"⏳ 正在使用 {IMAGEN_MODEL} 生成圖片，請稍候...")
    try:
        if IMAGEN_MODEL.startswith("gemini-"):
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=IMAGEN_MODEL,
                contents=prompt_text,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect_ratio
                    )
                )
            )
            if not response.candidates or not response.candidates[0].content.parts:
                raise Exception(f"{IMAGEN_MODEL} 沒有回傳任何內容。")
            
            image_bytes = None
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    image_bytes = part.inline_data.data
                    break
            
            if not image_bytes:
                raise Exception("在 API 回傳內容中找不到生成的圖片資料。")
        else:
            response = await asyncio.to_thread(
                client.models.generate_images,
                model=IMAGEN_MODEL,
                prompt=prompt_text,
                config=dict(number_of_images=1, output_mime_type="image/jpeg", aspect_ratio=aspect_ratio)
            )

            if not response.generated_images:
                raise Exception(f"{IMAGEN_MODEL} 沒有回傳任何圖片。")
            image_bytes = response.generated_images[0].image.image_bytes

        await status_message.edit_text("📤 圖片生成成功，正在上傳...")
        await update.message.reply_photo(
            photo=io.BytesIO(image_bytes),
            caption=(
                f"🎨 **AI 圖片生成完成！**\n\n"
                f"📝 描述：{prompt_text}\n"
                f"📐 比例：{aspect_ratio}\n"
                f"🤖 模型：{IMAGEN_MODEL}"
            ),
            read_timeout=60,
            write_timeout=60
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
    
    # 隨手文字筆記功能
    application.add_handler(CommandHandler("addnote", add_note_command))
    application.add_handler(CommandHandler("notes", list_notes_command))
    application.add_handler(CallbackQueryHandler(delete_note_callback, pattern="^delnote_\\d+$"))
    
    # 語音筆記功能 (Lab 6)
    application.add_handler(CommandHandler("voicenotes", list_voice_notes_command))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(CallbackQueryHandler(save_voice_note_callback, pattern="^save_voice_note$"))
    application.add_handler(CallbackQueryHandler(discard_voice_note_callback, pattern="^discard_voice_note$"))
    application.add_handler(CallbackQueryHandler(view_voice_detail_callback, pattern="^vdet_\\d+$"))
    application.add_handler(CallbackQueryHandler(play_voice_note_callback, pattern="^vplay_\\d+$"))
    application.add_handler(CallbackQueryHandler(delete_voice_note_callback, pattern="^vdel_\\d+$"))
    
    # 簡報與圖片生成
    application.add_handler(CommandHandler("ppt", generate_ppt))
    application.add_handler(CommandHandler("draw", generate_image))
    
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("機器人 (Lab 6 - 最終整合版) 已啟動，正在接聽訊息...")
    application.run_polling()

if __name__ == "__main__":
    main()
