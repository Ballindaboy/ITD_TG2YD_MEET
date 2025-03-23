import logging
import sys
import os
import atexit
import signal
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
from telegram import Update
from telegram.error import NetworkError, TelegramError
from telegram.ext import ContextTypes, CallbackContext
from config.config import TELEGRAM_TOKEN, LOG_LEVEL, LOG_FORMAT, validate_config
from src.handlers.command_handler import (
    start, help_command, new_meeting, handle_category, navigate_folders,
    switch_meeting, current_meeting, cancel, create_folder,
    CHOOSE_CATEGORY, NAVIGATE_FOLDERS, CREATE_FOLDER
)
from src.handlers.file_handler import handle_message

# Путь к файлу блокировки
LOCK_FILE = "/tmp/itd_meeting_bot.lock"

# Настройка логирования
logging.basicConfig(
    format=LOG_FORMAT, 
    level=LOG_LEVEL,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# Функция для удаления файла блокировки при завершении
def cleanup_lock():
    """Удаляет файл блокировки при завершении программы"""
    try:
        if os.path.exists(LOCK_FILE):
            os.unlink(LOCK_FILE)
            logger.info("Файл блокировки удален")
    except Exception as e:
        logger.error(f"Ошибка при удалении файла блокировки: {e}")

# Обработчик сигналов завершения
def signal_handler(sig, frame):
    """Обрабатывает сигналы завершения"""
    logger.info(f"Получен сигнал {sig}, завершение работы...")
    cleanup_lock()
    sys.exit(0)

# Регистрация обработчиков сигналов
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Регистрация функции очистки при выходе
atexit.register(cleanup_lock)

# Обработчик ошибок
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает ошибки бота глобально"""
    if isinstance(context.error, NetworkError):
        logger.warning(f"Ошибка сети: {context.error}")
        # Пытаемся уведомить пользователя, если update доступен
        if isinstance(update, Update) and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ Произошла ошибка сети. Пожалуйста, повторите действие через несколько минут."
                )
            except:
                pass
    elif isinstance(context.error, TelegramError):
        logger.error(f"Ошибка Telegram API: {context.error}")
        if isinstance(update, Update) and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ Произошла ошибка при обработке запроса. Пожалуйста, повторите позже."
                )
            except:
                pass
    else:
        # Для всех остальных ошибок
        logger.error(f"Необработанная ошибка: {context.error}", exc_info=True)
        if isinstance(update, Update) and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ Произошла непредвиденная ошибка. Пожалуйста, сообщите администратору."
                )
            except:
                pass

def main() -> None:
    """Запуск бота"""
    try:
        # Проверка наличия файла блокировки
        if os.path.exists(LOCK_FILE):
            # Проверяем, работает ли процесс, создавший файл блокировки
            try:
                with open(LOCK_FILE, 'r') as lock_file:
                    pid = int(lock_file.read().strip())
                
                # Проверяем, существует ли процесс с таким PID
                os.kill(pid, 0)  # Не отправляет сигнал, но проверяет существование процесса
                
                logger.error(f"Бот уже запущен (PID: {pid}). Завершение работы.")
                sys.exit(1)
            except (ProcessLookupError, ValueError):
                # Процесс не существует или файл блокировки поврежден
                logger.warning("Найден недействительный файл блокировки. Перезапись...")
        
        # Создаем файл блокировки
        with open(LOCK_FILE, 'w') as lock_file:
            lock_file.write(str(os.getpid()))
        
        logger.info(f"Создан файл блокировки (PID: {os.getpid()})")
        
        # Проверка конфигурации
        validate_config()
        
        logger.info("Запуск бота")
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Регистрация обработчика ошибок
        application.add_error_handler(error_handler)
        
        # Регистрация обработчиков команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("switch", switch_meeting))
        application.add_handler(CommandHandler("current", current_meeting))
        
        # Обработчик создания новой встречи
        new_meeting_handler = ConversationHandler(
            entry_points=[CommandHandler("new", new_meeting)],
            states={
                CHOOSE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category)],
                NAVIGATE_FOLDERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, navigate_folders)],
                CREATE_FOLDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_folder)]
            },
            fallbacks=[CommandHandler("cancel", cancel)]
        )
        application.add_handler(new_meeting_handler)
        
        # Обработчик всех остальных сообщений (текст и файлы)
        application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
        
        logger.info("Бот запущен и готов к работе")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {str(e)}", exc_info=True)
        exit(1)

if __name__ == "__main__":
    main() 