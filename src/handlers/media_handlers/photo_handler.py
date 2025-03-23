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

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id, file_name, session) -> None:
    """Обработчик фотографий"""
    user_id = update.effective_user.id
    
    # Сообщаем о начале обработки
    status_message = await update.message.reply_text("🖼 Обрабатываю фото...")
    
    try:
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        # Скачиваем файл
        await download_telegram_file(context, file_id, tmp_path)
        
        # Путь для сохранения на Яндекс.Диске
        yandex_path = session.get_media_path("jpg")
        
        # Определяем размер файла
        file_size = os.path.getsize(tmp_path)
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        # Загружаем на Яндекс.Диск
        logger.debug(f"Начинаем загрузку фото: {yandex_path}")
        await status_message.edit_text(f"🖼 Загрузка фото ({file_size_mb} МБ)...")
        
        yadisk_helper.upload_file(tmp_path, yandex_path)
        
        # Удаляем временный файл
        os.unlink(tmp_path)
        
        # Спрашиваем о подписи
        await status_message.edit_text(
            f"🖼 Фото сохранено как\n{session.file_prefix}.jpg\n\n"
            "Хотите добавить подпись к фото?"
        )
        
        # Устанавливаем состояние ожидания подписи
        state_manager.set_data(user_id, "awaiting_caption", True)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {str(e)}", exc_info=True)
        await status_message.edit_text(f"❌ Произошла ошибка при обработке фото: {str(e)}")
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass 