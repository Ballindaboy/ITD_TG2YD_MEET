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
from datetime import datetime

logger = logging.getLogger(__name__)
yadisk_helper = YaDiskHelper()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает текстовые сообщения"""
    user_id = update.effective_user.id
    
    try:
        # Проверяем, активен ли режим ожидания итогового комментария
        from src.handlers.command_handler import process_final_comment
        processed = await process_final_comment(update, context)
        if processed:
            return
            
        # Проверяем, активен ли режим ожидания расшифровки голосового сообщения
        awaiting_transcription = state_manager.get_data(user_id, "awaiting_transcription")
        if awaiting_transcription:
            from src.handlers.media_handlers.voice_handler import process_transcription
            await process_transcription(update, context)
            return
            
        # Проверяем, активен ли режим ожидания редактирования расшифровки
        awaiting_edit = state_manager.get_data(user_id, "awaiting_transcription_edit")
        if awaiting_edit:
            from src.handlers.media_handlers.voice_handler import process_transcription_edit
            await process_transcription_edit(update, context)
            return

        # Получаем текущую сессию
        session = state_manager.get_session(user_id)
        if not session:
            logger.warning(f"Пользователь {user_id} отправил текст, но нет активной сессии")
            await update.message.reply_text(
                "❌ У вас нет активной встречи. Используйте /new, чтобы начать встречу."
            )
            return

        # Получаем данные пользователя для добавления автора
        user_data = get_user_data(user_id)
        user_name = ""
        if user_data:
            first_name = user_data.get('first_name', '')
            last_name = user_data.get('last_name', '')
            user_name = f"{first_name} {last_name}".strip()

        # Добавляем сообщение в текстовый файл
        text = update.message.text
        
        # Добавляем запись в историю сессии
        session.add_message(text, author=user_name)
        
        # Форматируем текст для добавления в файл
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        author_prefix = f"[{user_name}] " if user_name else ""
        formatted_text = f"[{timestamp}] {author_prefix}{text}"
        
        # Добавляем сообщение в файл на Яндекс.Диске
        yadisk_helper.append_to_text_file(session.txt_file_path, formatted_text)
        
        # Отправляем подтверждение
        await update.message.reply_text(
            "✅ Текст добавлен в отчет"
        )
    except Exception as e:
        logger.error(f"Ошибка при обработке текста: {str(e)}", exc_info=True)
        await update.message.reply_text(
            f"❌ Произошла ошибка: {str(e)}"
        )

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
        logger.info(f"Обработка аудио файла через handle_voice: {file_name}")
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