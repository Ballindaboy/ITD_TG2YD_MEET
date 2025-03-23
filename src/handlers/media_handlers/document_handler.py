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

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id, file_name, session) -> None:
    """Обработчик документов и прочих файлов"""
    user_id = update.effective_user.id
    
    # Сообщаем о начале обработки
    status_message = await update.message.reply_text(f"📄 Обрабатываю документ '{file_name}'...")
    
    try:
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        # Скачиваем файл
        await download_telegram_file(context, file_id, tmp_path)
        
        # Получаем расширение файла
        extension = "bin"
        if "." in file_name:
            extension = file_name.split(".")[-1]
        
        # Путь для сохранения на Яндекс.Диске
        yandex_path = session.get_media_path(extension)
        
        # Определяем размер файла
        file_size = os.path.getsize(tmp_path)
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        # Информируем о загрузке
        await status_message.edit_text(f"📄 Загружаю документ ({file_size_mb} МБ)...")
        
        # Добавляем информацию о прогрессе для больших файлов
        progress_callback = None
        if file_size > 5 * 1024 * 1024:  # Если файл больше 5МБ
            last_progress = 0
            
            def progress_callback(progress):
                nonlocal last_progress
                logger.info(f"Прогресс загрузки документа: {progress}%")
                
                # Обновляем статус только если прогресс значительно изменился
                if progress - last_progress >= 20 and progress > 0:
                    last_progress = progress
                    context.application.create_task(
                        status_message.edit_text(f"📄 Загрузка документа: {progress}% завершено...")
                    )
        
        # Загружаем на Яндекс.Диск
        logger.debug(f"Начинаем загрузку документа на Яндекс.Диск: {yandex_path}")
        yadisk_helper.upload_file(tmp_path, yandex_path, progress_callback)
        
        # Удаляем временный файл
        os.unlink(tmp_path)
        
        # Спрашиваем о подписи
        await status_message.edit_text(
            f"📄 Документ {file_name} сохранён как\n{session.file_prefix}.{extension}\n\n"
            "Хотите добавить подпись к документу?"
        )
        
        # Устанавливаем состояние ожидания подписи
        state_manager.set_data(user_id, "awaiting_caption", True)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке документа: {str(e)}", exc_info=True)
        await status_message.edit_text(f"❌ Произошла ошибка при обработке документа: {str(e)}")
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass 