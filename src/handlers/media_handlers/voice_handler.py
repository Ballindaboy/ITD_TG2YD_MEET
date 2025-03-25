import os
import logging
import tempfile
import time
from telegram import Update
from telegram.ext import ContextTypes
from src.utils.yadisk_helper import YaDiskHelper
from src.utils.state_manager import state_manager
from src.handlers.media_handlers.common import download_telegram_file
from src.utils.speech_recognition import transcribe_audio
from datetime import datetime

logger = logging.getLogger(__name__)
yadisk_helper = YaDiskHelper()

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает голосовое сообщение
    """
    user_id = update.effective_user.id
    user_session = state_manager.get_session(user_id)
    
    if not user_session:
        logging.warning(f"Пользователь {user_id} отправил голосовое сообщение без активной сессии")
        await update.message.reply_text("❌ У вас нет активной сессии. Начните новую с помощью /start")
        return
    
    try:
        # Получаем информацию о голосовом сообщении
        voice = update.message.voice
        file_id = voice.file_id
        
        # Скачиваем голосовое сообщение
        voice_file = await context.bot.get_file(file_id)
        
        # Создаем временный файл для голосового сообщения
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_voice:
            await voice_file.download_to_drive(temp_voice.name)
            temp_voice_path = temp_voice.name
        
        # Уведомляем пользователя о начале обработки
        processing_message = await update.message.reply_text("🔄 Обрабатываю голосовое сообщение...")
        
        # Транскрибируем голосовое сообщение
        transcription = transcribe_audio(temp_voice_path)
        
        # Получаем имя пользователя
        user_name = state_manager.get_user_data(user_id, "user_name", "Пользователь")
        
        # Сохраняем транскрипцию в файл сессии
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        voice_message = f"[{timestamp}] {user_name} [АУДИО]: {transcription}\n"
        
        disk_helper = YaDiskHelper()
        disk_helper.append_to_file(user_session["session_file"], voice_message)
        
        # Удаляем временный файл
        os.unlink(temp_voice_path)
        
        # Обновляем сообщение о статусе
        await processing_message.edit_text(f"✅ Голосовое сообщение обработано:\n\n{transcription}")
        
    except Exception as e:
        logging.error(f"Ошибка при обработке голосового сообщения: {e}")
        await update.message.reply_text(f"❌ Произошла ошибка при обработке голосового сообщения: {e}")

async def process_transcription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает расшифровку голосового сообщения, введенную пользователем"""
    user_id = update.effective_user.id
    transcription = update.message.text
    session = state_manager.get_session(user_id)
    
    if not session:
        return
        
    try:
        # Добавляем расшифровку в файл встречи
        yadisk_helper.append_to_text_file(
            session.txt_file_path, 
            f"Расшифровка голосового сообщения: {transcription}"
        )
        await update.message.reply_text("✍️ Добавил расшифровку в отчёт.")
    except Exception as e:
        logger.error(f"Ошибка при добавлении расшифровки: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")
    
    # Сбрасываем состояние ожидания
    state_manager.set_data(user_id, "awaiting_transcription", False)

async def process_transcription_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает исправленную расшифровку голосового сообщения"""
    user_id = update.effective_user.id
    improved_transcription = update.message.text
    session = state_manager.get_session(user_id)
    
    if not session:
        return
        
    try:
        # Обновляем расшифровку в файле встречи
        # Сначала добавляем примечание, что расшифровка была отредактирована
        yadisk_helper.append_to_text_file(
            session.txt_file_path, 
            f"Исправленная расшифровка голосового сообщения: {improved_transcription}"
        )
        await update.message.reply_text("✏️ Обновил расшифровку в отчёте.")
    except Exception as e:
        logger.error(f"Ошибка при обновлении расшифровки: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")
    
    # Сбрасываем состояние ожидания редактирования
    state_manager.set_data(user_id, "awaiting_transcription_edit", False) 