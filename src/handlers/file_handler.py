import os
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from config.config import UPLOAD_DIR
from src.utils.yadisk_helper import YaDiskHelper
from src.utils.state_manager import state_manager
from src.handlers.media_handlers import (
    get_file_from_message, 
    handle_voice, 
    handle_photo, 
    handle_video,
    handle_document,
    process_transcription,
    process_transcription_edit,
    process_caption
)

logger = logging.getLogger(__name__)
yadisk_helper = YaDiskHelper()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые сообщения"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Если сообщение начинается с символа команды, игнорируем
    if text.startswith("/"):
        return
    
    # Обработка кнопки "Начать новую встречу"
    if text == "🆕 Начать новую встречу":
        from src.handlers.command_handler import new_meeting
        await new_meeting(update, context)
        return
    
    # Получаем текущую сессию пользователя
    session = state_manager.get_session(user_id)
    if not session:
        # Создаем клавиатуру с кнопкой новой встречи
        keyboard = [["🆕 Начать новую встречу"]]
        
        await update.message.reply_text(
            "❌ Нет активной встречи.",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        return
    
    # Добавляем текст в файл встречи
    try:
        logger.debug(f"Добавление текста в файл: {session.txt_file_path}")
        yadisk_helper.append_to_text_file(session.txt_file_path, text)
        await update.message.reply_text("📝 Добавлено в отчёт.")
    except Exception as e:
        logger.error(f"Ошибка при добавлении текста: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE, handler_func=None) -> None:
    """Обработчик получения файлов любого типа"""
    user_id = update.effective_user.id
    
    # Получаем текущую сессию пользователя
    session = state_manager.get_session(user_id)
    if not session:
        # Создаем клавиатуру с кнопкой новой встречи
        keyboard = [["🆕 Начать новую встречу"]]
        
        await update.message.reply_text(
            "❌ Нет активной встречи.",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        return
    
    # Получаем информацию о файле
    file_id, file_name, file_type = await get_file_from_message(update)
    
    if not file_id or not file_name:
        await update.message.reply_text("❌ Не могу обработать этот тип файла.")
        return
    
    logger.info(f"Получен файл от пользователя {user_id}: {file_name} (тип: {file_type})")
    
    # Если передан конкретный обработчик, используем его
    if handler_func:
        await handler_func(update, context, file_id, file_name, session)
        return
    
    # Иначе выбираем обработчик в зависимости от типа файла
    if file_type == "voice":
        await handle_voice(update, context, file_id, file_name, session)
    elif file_type == "photo":
        await handle_photo(update, context, file_id, file_name, session)
    elif file_type == "video":
        await handle_video(update, context, file_id, file_name, session)
    elif file_type == "audio":
        # Аудио файлы также обрабатываем через handle_voice
        await handle_voice(update, context, file_id, file_name, session)
    else:
        # Для остальных типов файлов используем обработчик документов
        await handle_document(update, context, file_id, file_name, session)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик всех сообщений"""
    user_id = update.effective_user.id
    
    # Проверяем, ожидаем ли мы расшифровку голосового сообщения
    if state_manager.get_data(user_id, "awaiting_transcription"):
        await process_transcription(update, context)
        return
    
    # Проверяем, ожидаем ли мы исправленную расшифровку голосового сообщения
    if state_manager.get_data(user_id, "awaiting_transcription_edit"):
        await process_transcription_edit(update, context)
        return
    
    # Проверяем, ожидаем ли мы подпись к файлу
    if state_manager.get_data(user_id, "awaiting_caption"):
        await process_caption(update, context)
        return
    
    # Если это текстовое сообщение - обрабатываем его первым, 
    # чтобы кнопка "Начать новую встречу" работала корректно
    if update.message.text:
        await handle_text(update, context)
        return
    
    # Проверяем наличие файла в сообщении
    if (update.message.document or update.message.photo or 
        update.message.video or update.message.audio or 
        update.message.voice or update.message.video_note or 
        update.message.sticker):
        await handle_file(update, context)
        return 