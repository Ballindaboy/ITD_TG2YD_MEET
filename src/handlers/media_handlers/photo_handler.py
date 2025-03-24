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
    status_message = await update.message.reply_text("🔄 Начинаю обработку фотографии...")
    
    try:
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        # Обновляем статус и скачиваем файл
        await status_message.edit_text("📥 Скачиваю фотографию...")
        await download_telegram_file(context, file_id, tmp_path)
        
        # Путь для сохранения на Яндекс.Диске
        yandex_path = session.get_media_path("jpg")
        
        # Определяем размер файла
        file_size = os.path.getsize(tmp_path)
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        # Загружаем на Яндекс.Диск
        logger.debug(f"Начинаем загрузку фото: {yandex_path}")
        await status_message.edit_text(f"☁️ Загружаю фотографию ({file_size_mb} МБ) на Яндекс.Диск...\nЭто может занять несколько секунд.")
        
        try:
            yadisk_helper.upload_file(tmp_path, yandex_path)
        except Exception as e:
            if "уже существует" in str(e) or "already exists" in str(e):
                logger.warning(f"Файл {yandex_path} уже существует. Пробуем загрузить с перезаписью.")
                await status_message.edit_text(f"⚠️ Файл с таким именем уже существует. Перезаписываю...")
                yadisk_helper.upload_file(tmp_path, yandex_path, overwrite=True)
            else:
                raise
        
        # Удаляем временный файл
        os.unlink(tmp_path)
        
        # Спрашиваем о подписи
        await status_message.edit_text(
            f"✅ Фотография успешно сохранена как\n{session.file_prefix}.jpg\n\n"
            "Хотите добавить подпись к фотографии? Если да, отправьте текст подписи, иначе отправьте любое другое сообщение."
        )
        
        # Устанавливаем состояние ожидания подписи
        state_manager.set_data(user_id, "awaiting_caption", True)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка при обработке фотографии: {error_msg}", exc_info=True)
        
        # Определяем тип ошибки для более дружественного сообщения
        user_message = f"❌ Произошла ошибка при обработке фотографии."
        
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