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
    status_message = await update.message.reply_text("🔄 Начинаю обработку видео...")
    
    try:
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        # Скачиваем файл
        await status_message.edit_text("📥 Скачиваю видео из Telegram...")
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
                f"☁️ Загружаю видео на Яндекс.Диск ({file_size_mb} МБ)...\n"
                f"Это большой файл и загрузка может занять продолжительное время. Я буду информировать вас о прогрессе."
            )
        else:
            await status_message.edit_text(
                f"☁️ Загружаю видео на Яндекс.Диск ({file_size_mb} МБ)...\n"
                f"Это может занять несколько минут."
            )
        
        # Добавляем информацию о прогрессе с более частыми обновлениями
        last_progress = 0
        last_update_time = 0
        import time
        
        def progress_callback(progress):
            nonlocal last_progress, last_update_time
            current_time = time.time()
            
            # Логируем более подробно
            logger.info(f"Прогресс загрузки видео: {progress}%")
            
            # Обновляем статус если прогресс изменился на 10% или прошло 5 секунд с последнего обновления
            if (progress - last_progress >= 10 or current_time - last_update_time >= 5) and progress > 0:
                last_progress = progress
                last_update_time = current_time
                
                # Формируем индикатор прогресса
                progress_bar = "■" * int(progress / 10) + "□" * (10 - int(progress / 10))
                
                context.application.create_task(
                    status_message.edit_text(
                        f"☁️ Загрузка видео: {progress}% завершено\n"
                        f"[{progress_bar}]\n"
                        f"Пожалуйста, не закрывайте приложение во время загрузки."
                    )
                )
        
        # Загружаем на Яндекс.Диск с увеличенным таймаутом для видео
        logger.debug(f"Начинаем загрузку видео на Яндекс.Диск: {yandex_path}")
        
        try:
            # Используем увеличенный таймаут для видео
            yadisk_helper.upload_file(tmp_path, yandex_path, progress_callback)
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
            f"✅ Видео успешно сохранено как\n{session.file_prefix}.{extension}\n\n"
            "Хотите добавить подпись к видео? Если да, отправьте текст подписи, иначе отправьте любое другое сообщение."
        )
        
        # Устанавливаем состояние ожидания подписи
        state_manager.set_data(user_id, "awaiting_caption", True)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка при обработке видео: {error_msg}", exc_info=True)
        
        # Определяем тип ошибки для более дружественного сообщения
        user_message = f"❌ Произошла ошибка при обработке видео."
        
        if "timeout" in error_msg.lower():
            user_message += "\n⏱ Превышено время ожидания при загрузке. Возможно, видео слишком большое или проблемы с сетью."
        elif "connection" in error_msg.lower():
            user_message += "\n🌐 Проблема с подключением к Яндекс.Диску. Проверьте интернет-соединение."
        elif "существует" in error_msg.lower() or "exists" in error_msg.lower():
            user_message += "\n🔄 Файл с таким именем уже существует, и перезапись не удалась."
        elif "permission" in error_msg.lower() or "доступ" in error_msg.lower():
            user_message += "\n🔒 Нет прав доступа к указанной папке на Яндекс.Диске."
        elif "size" in error_msg.lower() or "размер" in error_msg.lower():
            user_message += "\n📏 Файл слишком большой для загрузки. Попробуйте сжать видео перед отправкой."
        else:
            user_message += f"\n⚠️ Детали: {error_msg[:100]}..." if len(error_msg) > 100 else f"\n⚠️ Детали: {error_msg}"
        
        user_message += "\n\nПопробуйте повторить операцию позже или обратитесь к администратору."
        
        await status_message.edit_text(user_message)
        
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass 