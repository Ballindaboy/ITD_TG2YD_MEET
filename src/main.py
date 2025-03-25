import logging
import os
import signal
import atexit
import time
import sys
import argparse
from contextlib import suppress

# Сторонние библиотеки
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler,
    ConversationHandler, 
    MessageHandler, 
    filters
)
from telegram.error import TelegramError, NetworkError

# Внутренние модули
from config.config import validate_config, TELEGRAM_TOKEN, DATA_DIR, ADMIN_IDS
from config.logging_config import configure_logging
from src.handlers.command_handler import (
    start, help_command, new_meeting, handle_category, navigate_folders,
    switch_meeting, current_meeting, cancel, create_folder,
    handle_session_callback, end_session_and_show_summary, reopen_session, 
    confirm_reopen_session, cancel_reopen_session,
    CHOOSE_FOLDER, NAVIGATE_SUBFOLDERS, CREATE_FOLDER, folder_selected_callback
)
from src.handlers.file_handler import handle_message, handle_text, handle_file
from src.handlers.media_handlers.voice_handler import process_transcription, process_transcription_edit
from src.handlers.media_handlers.photo_handler import handle_photo
from src.handlers.media_handlers.video_handler import handle_video
from src.handlers.media_handlers.document_handler import handle_document
from src.handlers.media_handlers.voice_handler import handle_voice
from src.handlers.admin_handler import (
    admin, admin_menu_handler, handle_folder_path, handle_folder_permissions,
    handle_remove_folder, handle_add_user, add_user_first_name, add_user_last_name, 
    handle_remove_user, handle_select_users, handle_select_folder, cancel as admin_cancel,
    ADMIN_MENU, ADD_FOLDER, REMOVE_FOLDER, ADD_USER, REMOVE_USER,
    FOLDER_PATH, USER_ID, FOLDER_PERMISSIONS, SELECT_FOLDER, SELECT_USERS,
    BROWSE_FOLDERS, SELECT_SUBFOLDER, CREATE_SUBFOLDER, browse_folders,
    select_subfolder, create_subfolder, ADMIN_USER_FIRST_NAME, ADMIN_USER_LAST_NAME,
    ADMIN_ADD_USER
)
from src.utils.session_utils import SESSION_TIMEOUT
from src.utils.error_utils import handle_error
from src.utils.yadisk_helper import YaDiskHelper
from src.utils.folder_navigation import FolderNavigator

# Настройка логирования
configure_logging()
logger = logging.getLogger(__name__)

# Путь к файлу блокировки
LOCK_FILE = os.path.join(DATA_DIR, 'bot.lock')

# Глобальный объект YaDiskHelper
yadisk_helper = None

# Глобальный объект FolderNavigator
folder_navigator = None

def cleanup():
    """Очистка ресурсов при выходе"""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
            logger.info(f"Файл блокировки {LOCK_FILE} удален.")
    except Exception as e:
        logger.error(f"Ошибка при удалении файла блокировки: {e}")

def signal_handler(signum, frame):
    """Обработчик сигналов"""
    logger.info(f"Получен сигнал {signum}, завершение работы...")
    cleanup()
    sys.exit(0)

async def global_error_handler(update: Update, context) -> None:
    """Глобальный обработчик ошибок для приложения"""
    error = context.error

    # Логирование ошибки
    logger.error(f"Ошибка в обработчике: {context.error}", exc_info=True)
    
    # Обработка сетевых ошибок
    if isinstance(error, NetworkError):
        logger.warning(f"Ошибка сети: {error}")
        await handle_error(update, error, context.bot)
        return
    
    # Обработка ошибок Telegram API
    if isinstance(error, TelegramError):
        logger.error(f"Ошибка Telegram API: {error}")
        await handle_error(update, error, context.bot)
        return
    
    # Обработка всех остальных ошибок
    await handle_error(update, error, context.bot)

def main() -> None:
    """Основная функция для запуска бота"""
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Telegram бот для работы с Яндекс.Диском')
    parser.add_argument('--offline', action='store_true', help='Запустить бота в офлайн-режиме без Яндекс.Диска')
    args = parser.parse_args()
    
    # Проверяем, не запущен ли уже бот
    if os.path.exists(LOCK_FILE):
        logger.warning(f"Файл блокировки {LOCK_FILE} существует. Возможно, бот уже запущен.")
        try:
            # Проверяем, существует ли процесс
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            try:
                # Проверяем, активен ли процесс
                os.kill(pid, 0)
                logger.error("Выход, т.к. бот уже запущен.")
                return
            except OSError:
                # Процесс не существует, удаляем файл блокировки
                logger.warning(f"Процесс с PID {pid} не существует, удаляем файл блокировки.")
                os.remove(LOCK_FILE)
        except Exception as e:
            # Удаляем файл блокировки в случае ошибки
            logger.warning(f"Ошибка при проверке процесса: {e}. Удаляем файл блокировки.")
            try:
                os.remove(LOCK_FILE)
            except:
                logger.error(f"Не удалось удалить файл блокировки {LOCK_FILE}.")
                return

    # Создаем файл блокировки
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    
    # Инициализируем глобальный объект YaDiskHelper
    global yadisk_helper
    yadisk_helper = YaDiskHelper(skip_connection_check=True)
    
    # Инициализируем глобальный объект FolderNavigator
    global folder_navigator
    folder_navigator = FolderNavigator(
        yadisk_helper=yadisk_helper,
        folder_selected_callback=folder_selected_callback
    )
    
    # Если указан флаг офлайн-режима, принудительно переключаем
    if args.offline:
        logger.warning("Запуск в принудительном ОФЛАЙН-режиме. Яндекс.Диск не будет использоваться.")
        yadisk_helper.set_offline_mode(True)
    else:
        # Проверяем соединение с Яндекс.Диском
        connection_ok = yadisk_helper.test_connection(timeout=15.0)
        if not connection_ok:
            logger.warning("Не удалось установить соединение с Яндекс.Диском. Бот будет работать в офлайн-режиме.")
        else:
            logger.info("Соединение с Яндекс.Диском установлено успешно.")
    
    # Получаем токен бота
    token = TELEGRAM_TOKEN
    
    # Устанавливаем сессионное время жизни
    session_lifetime = SESSION_TIMEOUT.total_seconds()
    
    # Регистрация обработчиков сигналов и функции очистки
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(cleanup)
    
    try:
        # Проверка конфигурации
        validate_config()
        
        # Настройка приложения Telegram
        application = Application.builder().token(token).build()
        
        # Регистрация глобального обработчика ошибок
        application.add_error_handler(global_error_handler)
        
        # Регистрация обработчиков команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("end", end_session_and_show_summary))
        application.add_handler(CommandHandler("current", current_meeting))
        
        # Регистрация конверсации для навигации по папкам
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("new", new_meeting)],
            states={
                CHOOSE_FOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category)],
                NAVIGATE_SUBFOLDERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, navigate_folders)],
                CREATE_FOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_folder)]
            },
            fallbacks=[CommandHandler("cancel", cancel)]
        )
        
        # Отдельный обработчик для команды /switch для переключения между папками
        application.add_handler(CommandHandler("switch", switch_meeting))
        
        # Регистрируем обработчик для выбора папки через FolderNavigator
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, 
                lambda update, context: folder_navigator.handle_folder_selection(update, context)
            )
        )
        
        # Регистрация обработчиков для кнопок "Вернуться в сессию"
        application.add_handler(CallbackQueryHandler(reopen_session, pattern="reopen_session"))
        application.add_handler(CallbackQueryHandler(confirm_reopen_session, pattern="confirm_reopen"))
        application.add_handler(CallbackQueryHandler(cancel_reopen_session, pattern="cancel_reopen"))
        
        # Добавляем обработчик для текстовых сообщений, которые попадают в файл встречи
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        
        # Добавляем обработчик для голосовых сообщений
        application.add_handler(MessageHandler(filters.VOICE, handle_voice))
        
        # Обработчики исправленной транскрипции голосовых сообщений
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            process_transcription_edit, 
            block=False
        ))
        
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            process_transcription, 
            block=False
        ))
        
        # Обработчики медиафайлов
        application.add_handler(MessageHandler(filters.PHOTO, lambda update, context: handle_file(update, context, handle_photo)))
        application.add_handler(MessageHandler(filters.AUDIO, lambda update, context: handle_file(update, context, handle_voice)))
        application.add_handler(MessageHandler(filters.VIDEO, lambda update, context: handle_file(update, context, handle_video)))
        application.add_handler(MessageHandler(filters.Document.ALL, lambda update, context: handle_file(update, context, handle_document)))
        
        # Настройка параметров сессий
        # Устанавливаем время жизни сессии в секундах (по умолчанию 30 минут)
        session_timeout_seconds = int(session_lifetime)
        application.bot_data["session_timeout"] = session_timeout_seconds
        logger.info(f"Время жизни сессии установлено: {session_timeout_seconds} секунд")
        
        # Запуск бота
        logger.info("Бот запущен и готов к работе")
        application.run_polling()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)
        cleanup()
        sys.exit(1)

if __name__ == "__main__":
    main() 