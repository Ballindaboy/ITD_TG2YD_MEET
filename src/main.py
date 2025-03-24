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
from src.handlers.command_handler import start, help_command, new, cancel
from src.handlers.file_handler import file_received
from src.handlers.media_handlers.photo_handler import photo_received
from src.handlers.media_handlers.audio_handler import audio_received
from src.handlers.media_handlers.video_handler import video_received
from src.handlers.media_handlers.document_handler import document_received
from src.handlers.admin_handler import admin, add_folder, add_users, remove_folder, remove_users, cancel as admin_cancel
from src.handlers.admin.states import *
from src.handlers.admin.menu_handler import admin_menu, handle_category_choice
from src.handlers.admin.folder_handlers import browse_folders, select_subfolder, create_subfolder
from src.handlers.admin.user_handlers import add_users_to_folder, remove_users_from_folder
from src.utils.folder_navigation import BROWSE_FOLDERS, SELECT_SUBFOLDER, CREATE_SUBFOLDER
from src.utils.error_utils import handle_error

# Константы для состояний разговора
TITLE, DESCRIPTION, CATEGORY, DATE, TIME, LOCATION, RECEIVE_FILE, CONFIRMATION = range(8)

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
        
        # Обработчик команды для создания нового собрания
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("new", new)],
            states={
                TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: new(update, context, TITLE))],
                DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: new(update, context, DESCRIPTION))],
                CATEGORY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: new(update, context, CATEGORY)),
                    CallbackQueryHandler(lambda update, context: new(update, context, CATEGORY), pattern=r"^category_")
                ],
                DATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: new(update, context, DATE)),
                    CallbackQueryHandler(lambda update, context: new(update, context, DATE), pattern=r"^date_")
                ],
                TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: new(update, context, TIME))],
                LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: new(update, context, LOCATION))],
                RECEIVE_FILE: [
                    MessageHandler(filters.PHOTO, photo_received),
                    MessageHandler(filters.AUDIO, audio_received),
                    MessageHandler(filters.VIDEO, video_received),
                    MessageHandler(filters.Document.ALL, document_received),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, file_received),
                    CallbackQueryHandler(lambda update, context: new(update, context, CONFIRMATION), pattern=r"^confirm$")
                ],
                CONFIRMATION: [
                    CallbackQueryHandler(lambda update, context: new(update, context, CONFIRMATION), pattern=r"^confirm$"),
                    CallbackQueryHandler(lambda update, context: new(update, context, RECEIVE_FILE), pattern=r"^back$")
                ],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )
        application.add_handler(conv_handler)
        
        # Административные команды
        admin_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("admin", admin)],
            states={
                ADMIN_MENU: [
                    CallbackQueryHandler(handle_category_choice, pattern=r"^category_")
                ],
                ADMIN_ADD_FOLDER: [
                    CallbackQueryHandler(browse_folders, pattern=r"^browse_folders$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, add_folder),
                    CallbackQueryHandler(admin_menu, pattern=r"^back_to_menu$")
                ],
                ADMIN_ADD_USERS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, add_users),
                    CallbackQueryHandler(admin_menu, pattern=r"^back_to_menu$")
                ],
                ADMIN_REMOVE_FOLDER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, remove_folder),
                    CallbackQueryHandler(admin_menu, pattern=r"^back_to_menu$")
                ],
                ADMIN_REMOVE_USERS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, remove_users),
                    CallbackQueryHandler(admin_menu, pattern=r"^back_to_menu$")
                ],
                BROWSE_FOLDERS: [
                    CallbackQueryHandler(select_subfolder, pattern=r"^select_subfolder:"),
                    CallbackQueryHandler(create_subfolder, pattern=r"^create_subfolder$"),
                    CallbackQueryHandler(add_users_to_folder, pattern=r"^add_folder$"),
                    CallbackQueryHandler(browse_folders, pattern=r"^up$"),
                    CallbackQueryHandler(admin_menu, pattern=r"^back_to_menu$")
                ],
                SELECT_SUBFOLDER: [
                    CallbackQueryHandler(browse_folders, pattern=r"^back_to_folders$")
                ],
                CREATE_SUBFOLDER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, create_subfolder),
                    CallbackQueryHandler(browse_folders, pattern=r"^back_to_folders$")
                ],
                ADMIN_ADD_USERS_TO_FOLDER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, add_users_to_folder),
                    CallbackQueryHandler(browse_folders, pattern=r"^back_to_folders$")
                ],
                ADMIN_REMOVE_USERS_FROM_FOLDER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, remove_users_from_folder),
                    CallbackQueryHandler(browse_folders, pattern=r"^back_to_folders$")
                ]
            },
            fallbacks=[CommandHandler("cancel", admin_cancel)]
        )
        application.add_handler(admin_conv_handler)
        
        # Запуск бота
        logger.info("Бот запущен")
        application.run_polling(drop_pending_updates=True)
    
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        cleanup()

if __name__ == "__main__":
    # Настраиваем логирование
    configure_logging()
    
    import time
    main() 