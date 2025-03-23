import os
import logging
import tempfile
from telegram import Update
from telegram.ext import ContextTypes
from src.utils.yadisk_helper import YaDiskHelper
from src.utils.state_manager import state_manager
from src.handlers.media_handlers.common import download_telegram_file

logger = logging.getLogger(__name__)
yadisk_helper = YaDiskHelper()

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id, file_name, session) -> None:
    """Обработчик видео, с улучшенной обработкой для больших файлов"""
    user_id = update.effective_user.id
    
    # Сообщаем о начале обработки
    status_message = await update.message.reply_text("🎬 Обрабатываю видео...")
    
    try:
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        # Скачиваем файл
        await status_message.edit_text("🎬 Скачиваю видео из Telegram...")
        await download_telegram_file(context, file_id, tmp_path)
        
        # Узнаем расширение файла
        extension = "mp4"
        if "." in file_name:
            extension = file_name.split(".")[-1]
        
        # Путь для сохранения на Яндекс.Диске
        yandex_path = session.get_media_path(extension)
        
        # Определяем размер файла
        file_size = os.path.getsize(tmp_path)
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        # Специальное сообщение для больших видео
        if file_size > 10 * 1024 * 1024:  # Больше 10МБ
            await status_message.edit_text(
                f"🎬 Загружаю видео на Яндекс.Диск ({file_size_mb} МБ)...\n"
                f"Это может занять несколько минут. Пожалуйста, подождите."
            )
        else:
            await status_message.edit_text(f"🎬 Загружаю видео ({file_size_mb} МБ)...")
        
        # Добавляем информацию о прогрессе
        last_progress = 0
        
        def progress_callback(progress):
            nonlocal last_progress
            logger.info(f"Прогресс загрузки видео: {progress}%")
            
            # Обновляем статус только если прогресс значительно изменился
            if progress - last_progress >= 20 and progress > 0:
                last_progress = progress
                context.application.create_task(
                    status_message.edit_text(f"🎬 Загрузка видео: {progress}% завершено...")
                )
        
        # Загружаем на Яндекс.Диск с увеличенным таймаутом для видео
        logger.debug(f"Начинаем загрузку видео на Яндекс.Диск: {yandex_path}")
        
        # Используем увеличенный таймаут для видео
        yadisk_helper.upload_file(tmp_path, yandex_path, progress_callback)
        
        # Удаляем временный файл
        os.unlink(tmp_path)
        
        # Спрашиваем о подписи
        await status_message.edit_text(
            f"🎬 Видео сохранено как\n{session.file_prefix}.{extension}\n\n"
            "Хотите добавить подпись к видео?"
        )
        
        # Устанавливаем состояние ожидания подписи
        state_manager.set_data(user_id, "awaiting_caption", True)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке видео: {str(e)}", exc_info=True)
        await status_message.edit_text(
            f"❌ Произошла ошибка при обработке видео: {str(e)}\n"
            "Возможно, файл слишком большой для загрузки. Попробуйте сжать видео перед отправкой."
        )
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass 