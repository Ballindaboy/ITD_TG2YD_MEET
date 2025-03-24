"""
Модуль для централизованной обработки ошибок.
Содержит функции для логирования и обработки исключений, возникающих при работе бота.
"""

import logging
import functools
import traceback
from typing import Callable, Any, Optional, TypeVar, Awaitable

from telegram import Bot, Update
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

# Тип для функции-обработчика
HandlerType = TypeVar('HandlerType', bound=Callable[..., Any])

async def handle_error(update: Optional[Update], error: Exception, bot: Optional[Bot] = None) -> None:
    """
    Обрабатывает исключение, логирует его и уведомляет пользователя.
    
    Args:
        update: Объект update, может быть None если ошибка не связана с конкретным обновлением
        error: Исключение, которое нужно обработать
        bot: Объект бота для отправки уведомлений, если не None
    """
    # Логирование ошибки
    logger.error(f"Ошибка: {error}", exc_info=True)
    error_traceback = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    logger.debug(f"Трассировка: {error_traceback}")
    
    # Если обновление существует и есть бот для отправки уведомления
    if update and bot:
        user_id = update.effective_user.id if update.effective_user else None
        chat_id = update.effective_chat.id if update.effective_chat else None
        
        if chat_id:
            try:
                # Сообщение об ошибке для пользователя
                error_message = "Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже."
                
                # Для более информативных ошибок можно добавить специфичные сообщения
                if isinstance(error, TelegramError):
                    if "Message to delete not found" in str(error):
                        # Игнорируем ошибки удаления несуществующих сообщений
                        return
                    elif "Message is not modified" in str(error):
                        # Игнорируем ошибки о неизмененных сообщениях
                        return
                    elif "Forbidden" in str(error):
                        error_message = "У бота недостаточно прав для выполнения этого действия."
                    elif "Unauthorized" in str(error):
                        error_message = "Ошибка авторизации. Пожалуйста, перезапустите бота командой /start."
                    elif "Bad Request" in str(error) and "chat not found" in str(error).lower():
                        error_message = "Чат не найден. Возможно, вы заблокировали бота."
                    
                await bot.send_message(chat_id=chat_id, text=error_message)
                
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления об ошибке: {e}")

def catch_errors(func: HandlerType) -> HandlerType:
    """
    Декоратор для обработки исключений в функциях-обработчиках.
    
    Args:
        func: Функция-обработчик, которую нужно обернуть в обработчик исключений.
        
    Returns:
        Обернутая функция с обработкой исключений.
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            await handle_error(update, e, context.bot)
    
    return wrapper

async def safe_execute(func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Optional[Any]:
    """
    Безопасно выполняет асинхронную функцию, перехватывая исключения.
    
    Args:
        func: Асинхронная функция для выполнения
        *args: Позиционные аргументы для func
        **kwargs: Именованные аргументы для func
        
    Returns:
        Результат выполнения функции или None в случае ошибки
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Ошибка при выполнении {func.__name__}: {e}", exc_info=True)
        return None

def safe_sync_execute(func: Callable[..., Any], *args, **kwargs) -> Optional[Any]:
    """
    Безопасно выполняет синхронную функцию, перехватывая исключения.
    
    Args:
        func: Синхронная функция для выполнения
        *args: Позиционные аргументы для func
        **kwargs: Именованные аргументы для func
        
    Returns:
        Результат выполнения функции или None в случае ошибки
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Ошибка при выполнении {func.__name__}: {e}", exc_info=True)
        return None 