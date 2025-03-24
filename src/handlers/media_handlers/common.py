import os
import logging
import tempfile
from telegram import Update
from telegram.ext import ContextTypes
from src.utils.yadisk_helper import YaDiskHelper
from src.utils.state_manager import state_manager

logger = logging.getLogger(__name__)
yadisk_helper = YaDiskHelper()

async def get_file_from_message(update: Update) -> tuple:
    """Получает файл из различных типов сообщений"""
    if update.message.document:
        return update.message.document.file_id, update.message.document.file_name, "document"
    elif update.message.photo:
        photo = update.message.photo[-1]
        return photo.file_id, f"photo_{photo.file_unique_id}.jpg", "photo"
    elif update.message.video:
        return update.message.video.file_id, update.message.video.file_name, "video"
    elif update.message.audio:
        return update.message.audio.file_id, update.message.audio.file_name, "audio"
    elif update.message.voice:
        return update.message.voice.file_id, f"voice_{update.message.voice.file_unique_id}.ogg", "voice"
    elif update.message.video_note:
        return update.message.video_note.file_id, f"video_note_{update.message.video_note.file_unique_id}.mp4", "video_note"
    elif update.message.sticker:
        return update.message.sticker.file_id, f"sticker_{update.message.sticker.file_unique_id}.webp", "sticker"
    return None, None, None

async def download_telegram_file(context, file_id, tmp_path):
    """Скачивает файл из Telegram во временную директорию"""
    file = await context.bot.get_file(file_id)
    await file.download_to_drive(tmp_path)
    logger.debug(f"Файл успешно скачан из Telegram в {tmp_path}")
    return file

async def process_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает подпись к файлу"""
    user_id = update.effective_user.id
    caption = update.message.text
    session = state_manager.get_session(user_id)
    
    if not session:
        return
    
    # Отправляем статусное сообщение    
    status_message = await update.message.reply_text("🔄 Добавляю подпись к файлу в отчет...")
        
    try:
        # Добавляем подпись в файл встречи
        yadisk_helper.append_to_text_file(
            session.txt_file_path, 
            f"Подпись к файлу: {caption}"
        )
        await status_message.edit_text("✅ Подпись успешно добавлена в отчёт.")
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка при добавлении подписи: {error_msg}", exc_info=True)
        
        user_message = "❌ Не удалось добавить подпись к файлу."
        if "timeout" in error_msg.lower():
            user_message += "\n⏱ Превышено время ожидания при загрузке."
        elif "connection" in error_msg.lower():
            user_message += "\n🌐 Проблема с подключением к Яндекс.Диску."
        else:
            user_message += f"\n⚠️ Детали: {error_msg[:100]}" if len(error_msg) > 100 else f"\n⚠️ Детали: {error_msg}"
            
        await status_message.edit_text(user_message)
    
    # Сбрасываем состояние ожидания
    state_manager.set_data(user_id, "awaiting_caption", False) 