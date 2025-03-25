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

logger = logging.getLogger(__name__)
yadisk_helper = YaDiskHelper()

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id, file_name, session) -> None:
    """Обработчик голосовых сообщений
    
    В этой версии аудио не сохраняется на Яндекс.Диск, а только расшифровывается и добавляется в текстовый файл.
    Это уменьшает расход трафика и места на диске, при этом сохраняя полезную информацию.
    """
    user_id = update.effective_user.id
    
    # Сообщаем о начале обработки
    status_message = await update.message.reply_text("🔉 Обрабатываю голосовое сообщение...")
    
    try:
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as tmp_file:
            tmp_path = tmp_file.name
        
        # Скачиваем файл
        await download_telegram_file(context, file_id, tmp_path)
        
        # Определяем размер файла для информации
        file_size = os.path.getsize(tmp_path)
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        # Уведомляем о процессе распознавания
        await status_message.edit_text(f"🔉 Получено голосовое сообщение ({file_size_mb} МБ). Распознаю речь...")
        
        # Производим транскрипцию аудио
        transcription = transcribe_audio(tmp_path)
        
        # Удаляем временный файл
        os.unlink(tmp_path)
        
        if transcription:
            # Добавляем расшифровку в файл встречи
            yadisk_helper.append_to_text_file(
                session.txt_file_path, 
                f"Расшифровка голосового сообщения: {transcription}"
            )
            
            # Показываем результат пользователю и предлагаем отредактировать при необходимости
            await status_message.edit_text(
                f"✅ Голосовое сообщение успешно расшифровано\n\n"
                f"📝 Автоматическая расшифровка:\n{transcription}\n\n"
                "Если расшифровка неточная, пришлите исправленный текст, и я обновлю отчёт:"
            )
            
            # Устанавливаем состояние ожидания возможного редактирования расшифровки
            state_manager.set_data(user_id, "awaiting_transcription_edit", True)
        else:
            # Если автоматическая расшифровка не удалась, просим пользователя ввести текст вручную
            await status_message.edit_text(
                "⚠️ Не удалось автоматически распознать текст.\n"
                "Напишите расшифровку текста голосового сообщения, и я добавлю её в отчёт:"
            )
            
            # Устанавливаем состояние ожидания расшифровки
            state_manager.set_data(user_id, "awaiting_transcription", True)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке голосового сообщения: {str(e)}", exc_info=True)
        await status_message.edit_text(f"❌ Произошла ошибка при обработке голосового сообщения: {str(e)}")
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass

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