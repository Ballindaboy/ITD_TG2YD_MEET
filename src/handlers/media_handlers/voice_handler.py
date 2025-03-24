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
    """Обработчик голосовых сообщений"""
    user_id = update.effective_user.id
    
    # Сообщаем о начале обработки
    status_message = await update.message.reply_text("🔄 Начинаю обработку голосового сообщения...")
    
    try:
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as tmp_file:
            tmp_path = tmp_file.name
        
        # Обновляем статус и скачиваем файл
        await status_message.edit_text("📥 Скачиваю голосовое сообщение...")
        await download_telegram_file(context, file_id, tmp_path)
        
        # Добавляем уникальный идентификатор к пути файла на Яндекс.Диске
        unique_id = int(time.time() * 1000) % 10000  # Миллисекунды модуль 10000 для уникальности
        modified_prefix = f"{session.file_prefix}_{unique_id}"
        yandex_path = f"{session.folder_path}/{modified_prefix}.ogg"
        
        # Определяем размер файла
        file_size = os.path.getsize(tmp_path)
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        # Загружаем на Яндекс.Диск с обновлением статуса
        logger.debug(f"Начинаем загрузку голосового сообщения: {yandex_path}")
        await status_message.edit_text(f"☁️ Загружаю голосовое сообщение ({file_size_mb} МБ) на Яндекс.Диск...\nЭто может занять несколько секунд.")
        
        try:
            yadisk_helper.upload_file(tmp_path, yandex_path)
        except Exception as e:
            if "уже существует" in str(e) or "already exists" in str(e):
                logger.warning(f"Файл {yandex_path} уже существует. Пробуем загрузить с перезаписью.")
                await status_message.edit_text(f"⚠️ Файл с таким именем уже существует. Перезаписываю...")
                yadisk_helper.upload_file(tmp_path, yandex_path, overwrite=True)
            else:
                raise
        
        # Автоматическая расшифровка голосового сообщения
        await status_message.edit_text("🎙 Распознаю речь...\nЭто может занять некоторое время.")
        
        # Производим транскрипцию аудио
        transcription = transcribe_audio(tmp_path)
        
        # Удаляем временный файл
        os.unlink(tmp_path)
        
        if transcription:
            # Обновляем статус
            await status_message.edit_text("📝 Добавляю расшифровку в отчет...")
            
            # Добавляем расшифровку в файл встречи
            yadisk_helper.append_to_text_file(
                session.txt_file_path, 
                f"Расшифровка голосового сообщения: {transcription}"
            )
            
            # Показываем результат пользователю и предлагаем отредактировать при необходимости
            await status_message.edit_text(
                f"✅ Голосовое сообщение успешно сохранено как\n{modified_prefix}.ogg\n\n"
                f"📝 Автоматическая расшифровка:\n{transcription}\n\n"
                "Если расшифровка неточная, пришлите исправленный текст, и я обновлю отчёт:"
            )
            
            # Устанавливаем состояние ожидания возможного редактирования расшифровки
            state_manager.set_data(user_id, "awaiting_transcription_edit", True)
        else:
            # Если автоматическая расшифровка не удалась, просим пользователя ввести текст вручную
            await status_message.edit_text(
                f"✅ Голосовое сообщение успешно сохранено как\n{modified_prefix}.ogg\n\n"
                "⚠️ Не удалось автоматически распознать текст.\n"
                "Напишите расшифровку текста голосового сообщения, и я добавлю её в отчёт:"
            )
            
            # Устанавливаем состояние ожидания расшифровки
            state_manager.set_data(user_id, "awaiting_transcription", True)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка при обработке голосового сообщения: {error_msg}", exc_info=True)
        
        # Определяем тип ошибки для более дружественного сообщения
        user_message = f"❌ Произошла ошибка при обработке голосового сообщения."
        
        if "timeout" in error_msg.lower():
            user_message += "\n⏱ Превышено время ожидания при загрузке. Возможно, проблемы с сетью или сервером Яндекс.Диска."
        elif "connection" in error_msg.lower():
            user_message += "\n🌐 Проблема с подключением к Яндекс.Диску. Проверьте интернет-соединение."
        elif "существует" in error_msg.lower() or "exists" in error_msg.lower():
            user_message += "\n🔄 Файл с таким именем уже существует, и перезапись не удалась."
        elif "permission" in error_msg.lower() or "доступ" in error_msg.lower():
            user_message += "\n🔒 Нет прав доступа к указанной папке на Яндекс.Диске."
        else:
            user_message += f"\n⚠️ Детали: {error_msg[:100]}..." if len(error_msg) > 100 else f"\n⚠️ Детали: {error_msg}"
        
        user_message += "\n\nПопробуйте повторить операцию позже или обратитесь к администратору."
        
        await status_message.edit_text(user_message)
        
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
    
    # Сообщаем о начале обработки    
    status_message = await update.message.reply_text("🔄 Добавляю расшифровку в отчет...")
        
    try:
        # Добавляем расшифровку в файл встречи
        yadisk_helper.append_to_text_file(
            session.txt_file_path, 
            f"Расшифровка голосового сообщения: {transcription}"
        )
        await status_message.edit_text("✅ Расшифровка успешно добавлена в отчёт.")
    except Exception as e:
        logger.error(f"Ошибка при добавлении расшифровки: {str(e)}", exc_info=True)
        await status_message.edit_text(f"❌ Не удалось добавить расшифровку: {str(e)[:100]}")
    
    # Сбрасываем состояние ожидания
    state_manager.set_data(user_id, "awaiting_transcription", False)

async def process_transcription_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает исправленную расшифровку голосового сообщения"""
    user_id = update.effective_user.id
    improved_transcription = update.message.text
    session = state_manager.get_session(user_id)
    
    if not session:
        return
    
    # Сообщаем о начале обработки    
    status_message = await update.message.reply_text("🔄 Обновляю расшифровку в отчете...")
        
    try:
        # Обновляем расшифровку в файле встречи
        # Сначала добавляем примечание, что расшифровка была отредактирована
        yadisk_helper.append_to_text_file(
            session.txt_file_path, 
            f"Исправленная расшифровка голосового сообщения: {improved_transcription}"
        )
        await status_message.edit_text("✅ Расшифровка успешно обновлена в отчёте.")
    except Exception as e:
        logger.error(f"Ошибка при обновлении расшифровки: {str(e)}", exc_info=True)
        await status_message.edit_text(f"❌ Не удалось обновить расшифровку: {str(e)[:100]}")
    
    # Сбрасываем состояние ожидания редактирования
    state_manager.set_data(user_id, "awaiting_transcription_edit", False) 