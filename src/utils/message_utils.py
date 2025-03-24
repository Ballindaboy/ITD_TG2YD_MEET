"""
Модуль для работы с сообщениями в приложении.
Содержит функции для форматирования и отправки сообщений пользователям.
"""

import logging
from typing import List, Optional, Union, Dict, Any

from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError

from src.utils.error_utils import safe_execute_async

logger = logging.getLogger(__name__)

# Константы для сообщений
DEFAULT_ERROR_MESSAGE = "⚠️ Произошла ошибка при выполнении операции. Пожалуйста, попробуйте позже."
DEFAULT_SUCCESS_MESSAGE = "✅ Операция успешно выполнена."
DEFAULT_WAITING_MESSAGE = "⏳ Пожалуйста, подождите..."

async def send_message(
    bot: Bot, 
    chat_id: int, 
    text: str, 
    parse_mode: Optional[str] = ParseMode.HTML,
    reply_markup: Optional[Union[InlineKeyboardMarkup, ReplyKeyboardMarkup]] = None,
    disable_web_page_preview: bool = True
) -> Optional[Message]:
    """
    Отправляет сообщение пользователю с обработкой ошибок.
    
    Args:
        bot: Экземпляр бота Telegram
        chat_id: ID чата для отправки сообщения
        text: Текст сообщения
        parse_mode: Режим форматирования текста
        reply_markup: Клавиатура для ответа
        disable_web_page_preview: Отключить предпросмотр веб-страниц
        
    Returns:
        Объект сообщения или None в случае ошибки
    """
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview
        )
    except TelegramError as e:
        logger.error(f"Ошибка при отправке сообщения пользователю {chat_id}: {e}")
        return None

async def edit_message(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    parse_mode: Optional[str] = ParseMode.HTML,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    disable_web_page_preview: bool = True
) -> Optional[Message]:
    """
    Редактирует сообщение с обработкой ошибок.
    
    Args:
        bot: Экземпляр бота Telegram
        chat_id: ID чата
        message_id: ID сообщения для редактирования
        text: Новый текст сообщения
        parse_mode: Режим форматирования текста
        reply_markup: Новая клавиатура
        disable_web_page_preview: Отключить предпросмотр веб-страниц
        
    Returns:
        Обновленный объект сообщения или None в случае ошибки
    """
    try:
        return await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview
        )
    except TelegramError as e:
        logger.error(f"Ошибка при редактировании сообщения {message_id} в чате {chat_id}: {e}")
        return None

async def delete_message(bot: Bot, chat_id: int, message_id: int) -> bool:
    """
    Удаляет сообщение с обработкой ошибок.
    
    Args:
        bot: Экземпляр бота Telegram
        chat_id: ID чата
        message_id: ID сообщения для удаления
        
    Returns:
        True если успешно, иначе False
    """
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except TelegramError as e:
        logger.error(f"Ошибка при удалении сообщения {message_id} в чате {chat_id}: {e}")
        return False

def create_button_row(buttons: List[Dict[str, str]]) -> List[InlineKeyboardButton]:
    """
    Создает ряд кнопок для инлайн-клавиатуры.
    
    Args:
        buttons: Список словарей с ключами 'text' и 'callback_data'
        
    Returns:
        Список объектов InlineKeyboardButton
    """
    return [InlineKeyboardButton(btn['text'], callback_data=btn['callback_data']) for btn in buttons]

def create_keyboard(buttons: List[List[Dict[str, str]]]) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру из списка рядов кнопок.
    
    Args:
        buttons: Список списков словарей с ключами 'text' и 'callback_data'
        
    Returns:
        Объект InlineKeyboardMarkup
    """
    keyboard = []
    for row in buttons:
        keyboard.append(create_button_row(row))
    return InlineKeyboardMarkup(keyboard)

def create_reply_keyboard(buttons: List[List[str]], resize_keyboard: bool = True, one_time_keyboard: bool = False) -> ReplyKeyboardMarkup:
    """
    Создает клавиатуру ответа.
    
    Args:
        buttons: Список списков строк (каждый внутренний список - ряд кнопок)
        resize_keyboard: Подогнать размер клавиатуры под количество кнопок
        one_time_keyboard: Скрывать клавиатуру после использования
        
    Returns:
        Объект ReplyKeyboardMarkup
    """
    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=resize_keyboard,
        one_time_keyboard=one_time_keyboard
    )

def format_folder_list(folders: List[str], current_path: str = "") -> str:
    """
    Форматирует список папок для отображения пользователю.
    
    Args:
        folders: Список имен папок
        current_path: Текущий путь
        
    Returns:
        Отформатированный текст со списком папок
    """
    if not folders:
        return "📂 <b>Папки не найдены</b>"
    
    header = f"📂 <b>Текущая папка:</b> {current_path or '/'}"
    folder_list = "\n".join([f"  • {folder}" for folder in folders])
    
    return f"{header}\n\n<b>Доступные папки:</b>\n{folder_list}"

def format_file_list(files: List[str]) -> str:
    """
    Форматирует список файлов для отображения пользователю.
    
    Args:
        files: Список имен файлов
        
    Returns:
        Отформатированный текст со списком файлов
    """
    if not files:
        return "📄 <b>Файлы не найдены</b>"
    
    header = "📄 <b>Доступные файлы:</b>"
    file_list = "\n".join([f"  • {file}" for file in files])
    
    return f"{header}\n{file_list}"

def format_user_list(users: List[Dict[str, Any]]) -> str:
    """
    Форматирует список пользователей для отображения.
    
    Args:
        users: Список словарей с информацией о пользователях
        
    Returns:
        Отформатированный текст со списком пользователей
    """
    if not users:
        return "👥 <b>Пользователи не найдены</b>"
    
    header = "👥 <b>Список пользователей:</b>"
    user_list = "\n".join([
        f"  • {user.get('first_name', '')} {user.get('last_name', '')} (@{user.get('username', 'нет username')})"
        for user in users
    ])
    
    return f"{header}\n{user_list}"

async def edit_or_send_message(update: Update, context: Any, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> Optional[Message]:
    """
    Редактирует сообщение, если это колбэк, или отправляет новое.
    
    Args:
        update: Объект обновления Telegram
        context: Контекст обработчика
        text: Текст сообщения
        reply_markup: Клавиатура для ответа
        
    Returns:
        Обновленный объект сообщения или None в случае ошибки
    """
    if update.callback_query:
        await update.callback_query.answer()
        return await safe_execute_async(
            edit_message,
            context.bot,
            update.effective_chat.id,
            update.callback_query.message.message_id,
            text,
            reply_markup=reply_markup
        )
    else:
        return await safe_execute_async(
            send_message,
            context.bot,
            update.effective_chat.id,
            text,
            reply_markup=reply_markup
        ) 