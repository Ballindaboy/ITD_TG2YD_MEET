"""
Модуль для централизованной обработки ошибок в приложении.
Содержит функции для обработки различных типов ошибок и логирования.
"""

import logging
import traceback
from typing import Optional, Any, Callable, Awaitable
from functools import wraps
from telegram import Update, Bot
from telegram.error import NetworkError, TelegramError, BadRequest

logger = logging.getLogger(__name__)

async def notify_user(bot: Bot, chat_id: int, message: str) -> None:
    """
    Безопасно отправляет сообщение пользователю
    
    Args:
        bot: Экземпляр бота Telegram
        chat_id: ID чата для отправки сообщения
        message: Сообщение для отправки
    """
    try:
        await bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение пользователю {chat_id}: {e}")

async def handle_error(update: Optional[Update], error: Exception, bot: Optional[Bot] = None) -> None:
    """
    Обрабатывает различные типы ошибок и уведомляет пользователя при необходимости
    
    Args:
        update: Объект Update, может быть None
        error: Исключение, которое нужно обработать
        bot: Экземпляр бота для отправки сообщений, может быть None
    """
    chat_id = None
    if update and update.effective_chat:
        chat_id = update.effective_chat.id
    
    if isinstance(error, NetworkError):
        logger.warning(f"Ошибка сети: {error}")
        if chat_id and bot:
            await notify_user(
                bot, 
                chat_id, 
                "⚠️ Произошла ошибка сети. Пожалуйста, повторите действие через несколько минут."
            )
    
    elif isinstance(error, BadRequest):
        logger.error(f"Неверный запрос к Telegram API: {error}")
        if chat_id and bot:
            await notify_user(
                bot, 
                chat_id, 
                "⚠️ Ошибка в запросе. Пожалуйста, повторите действие корректно."
            )
    
    elif isinstance(error, TelegramError):
        logger.error(f"Ошибка Telegram API: {error}")
        if chat_id and bot:
            await notify_user(
                bot, 
                chat_id, 
                "⚠️ Произошла ошибка при обработке запроса. Пожалуйста, повторите позже."
            )
    
    else:
        # Для всех остальных ошибок
        logger.error(f"Необработанная ошибка: {error}", exc_info=True)
        if chat_id and bot:
            await notify_user(
                bot, 
                chat_id, 
                "⚠️ Произошла непредвиденная ошибка. Пожалуйста, сообщите администратору."
            )

def catch_errors(func: Callable) -> Callable:
    """
    Декоратор для обработки ошибок в функциях-обработчиках
    
    Args:
        func: Функция, которую нужно обернуть
        
    Returns:
        Обернутая функция с обработкой ошибок
    """
    @wraps(func)
    async def wrapper(update: Update, context: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            logger.error(f"Ошибка в функции {func.__name__}: {e}", exc_info=True)
            await handle_error(update, e, context.bot)
            # Возвращаем None, чтобы не прерывать выполнение обработчиков
            return None
    
    return wrapper

def safe_execute(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """
    Безопасно выполняет функцию, перехватывая все исключения
    
    Args:
        func: Функция для выполнения
        args: Позиционные аргументы для функции
        kwargs: Именованные аргументы для функции
        
    Returns:
        Результат выполнения функции или None в случае ошибки
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Ошибка при выполнении функции {func.__name__}: {e}")
        logger.debug(f"Трассировка: {traceback.format_exc()}")
        return None

async def safe_execute_async(func: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
    """
    Безопасно выполняет асинхронную функцию, перехватывая все исключения
    
    Args:
        func: Асинхронная функция для выполнения
        args: Позиционные аргументы для функции
        kwargs: Именованные аргументы для функции
        
    Returns:
        Результат выполнения функции или None в случае ошибки
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Ошибка при выполнении асинхронной функции {func.__name__}: {e}")
        logger.debug(f"Трассировка: {traceback.format_exc()}")
        return None 