import logging
import os
import signal
import atexit
import sys
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
from config.config import validate_config, TELEGRAM_TOKEN, DATA_DIR
from config.logging_config import configure_logging
from src.handlers.command_handler import (
    start, help_command, new_meeting, handle_category, navigate_folders,
    switch_meeting, current_meeting, cancel, create_folder,
    handle_session_callback, end_session_and_show_summary,
    CHOOSE_FOLDER, NAVIGATE_SUBFOLDERS, CREATE_FOLDER
)
from src.handlers.file_handler import handle_message, handle_text, handle_file
from src.handlers.media_handlers import (
    handle_photo, handle_video, handle_voice, 
    handle_document, process_transcription, process_transcription_edit
)
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
from src.utils.error_utils import handle_error
from src.utils.session_utils import SESSION_TIMEOUT

# Настройка логирования
logger = logging.getLogger(__name__)

# Путь к файлу блокировки
LOCK_FILE = os.path.join(DATA_DIR, 'bot.lock')

def cleanup():
    """Очистка ресурсов при завершении работы приложения"""
    logger.info("Завершение работы приложения")
    # Удаляем файл блокировки при выходе
    with suppress(FileNotFoundError):
        os.remove(LOCK_FILE)

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения работы"""
    logger.info(f"Получен сигнал {sig}, завершаем работу")
    cleanup()
    sys.exit(0)

async def error_handler(update: Update, context) -> None:
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
    # Проверка существования файла блокировки
    if os.path.exists(LOCK_FILE):
        logger.warning(f"Файл блокировки {LOCK_FILE} существует. Возможно, бот уже запущен.")
        lock_file_age = time.time() - os.path.getmtime(LOCK_FILE)
        if lock_file_age > 3600:  # Если файл старше часа, то, вероятно, он остался от предыдущего запуска
            logger.info(f"Файл блокировки старше часа ({lock_file_age:.1f} сек). Удаляем его.")
            os.remove(LOCK_FILE)
        else:
            logger.error("Выход, т.к. бот уже запущен.")
            return

    # Создание файла блокировки
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    
    # Регистрация обработчиков сигналов и функции очистки
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(cleanup)
    
    try:
        # Проверка конфигурации
        validate_config()
        
        # Настройка приложения Telegram
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Регистрация глобального обработчика ошибок
        application.add_error_handler(error_handler)
        
        # Команды для всех пользователей
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("switch", switch_meeting))
        application.add_handler(CommandHandler("current", current_meeting))
        
        # Обработчик колбэков от кнопок сессии
        application.add_handler(CallbackQueryHandler(handle_session_callback, pattern=r"^(end_session|extend_session|add_final_comment)$"))
        
        # Обработчик создания новой встречи
        new_meeting_handler = ConversationHandler(
            entry_points=[CommandHandler("new", new_meeting)],
            states={
                CHOOSE_FOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category)],
                NAVIGATE_SUBFOLDERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, navigate_folders)],
                CREATE_FOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_folder)]
            },
            fallbacks=[CommandHandler("cancel", cancel)]
        )
        application.add_handler(new_meeting_handler)
        
        # Обработчик административных команд
        admin_handler = ConversationHandler(
            entry_points=[CommandHandler("admin", admin)],
            states={
                ADMIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu_handler)],
                FOLDER_PATH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_folder_path)],
                FOLDER_PERMISSIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_folder_permissions)],
                SELECT_FOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_select_folder)],
                SELECT_USERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_select_users)],
                REMOVE_FOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_remove_folder)],
                ADD_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_user)],
                ADMIN_USER_FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user_first_name)],
                ADMIN_USER_LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user_last_name)],
                REMOVE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_remove_user)],
                BROWSE_FOLDERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, browse_folders)],
                SELECT_SUBFOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_subfolder)],
                CREATE_SUBFOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_subfolder)]
            },
            fallbacks=[CommandHandler("cancel", admin_cancel)]
        )
        application.add_handler(admin_handler)
        
        # Обработчики текстовых сообщений и файлов
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        application.add_handler(MessageHandler(filters.PHOTO, lambda update, context: handle_file(update, context, handle_photo)))
        application.add_handler(MessageHandler(filters.AUDIO, lambda update, context: handle_file(update, context, handle_voice)))
        application.add_handler(MessageHandler(filters.VIDEO, lambda update, context: handle_file(update, context, handle_video)))
        application.add_handler(MessageHandler(filters.Document.ALL, lambda update, context: handle_file(update, context, handle_document)))
        
        # Настройка параметров сессий
        # Устанавливаем время жизни сессии в секундах (по умолчанию 30 минут)
        session_timeout_seconds = int(SESSION_TIMEOUT.total_seconds())
        application.bot_data["session_timeout"] = session_timeout_seconds
        logger.info(f"Время жизни сессии установлено: {session_timeout_seconds} секунд")
        
        # Запуск бота
        logger.info("Бот запущен и готов к работе")
        application.run_polling(drop_pending_updates=True)
    
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        cleanup()

if __name__ == "__main__":
    # Настраиваем логирование
    configure_logging()
    
    import time
    main() 