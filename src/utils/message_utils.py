"""
Модуль для работы с сообщениями и интерфейсом пользователя.
Содержит функции для отправки, редактирования и удаления сообщений, а также создания кнопок и клавиатур.
"""

import logging
from typing import List, Optional, Dict, Any, Tuple, Union, Callable

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, 
    ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, Message, Bot
)
from telegram.error import TelegramError

from src.utils.error_utils import safe_execute

logger = logging.getLogger(__name__)

# Константы для кнопок
BUTTON_BACK = "⬅️ Назад"
BUTTON_HOME = "🏠 Главное меню"
BUTTON_CANCEL = "❌ Отмена"
BUTTON_ADD = "✅ Добавить"
BUTTON_REMOVE = "❌ Удалить"
BUTTON_CONFIRM = "✅ Подтвердить"
BUTTON_SKIP = "⏭️ Пропустить"
BUTTON_UP = "⬆️ Вверх"
BUTTON_CREATE = "🆕 Создать папку"
BUTTON_ADD_FOLDER = "✅ Добавить эту папку"

async def send_message(
    bot: Bot, 
    chat_id: int, 
    text: str, 
    reply_markup: Optional[Union[InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove]] = None,
    parse_mode: Optional[str] = None,
    reply_to_message_id: Optional[int] = None,
    disable_web_page_preview: bool = True
) -> Optional[Message]:
    """
    Безопасно отправляет сообщение пользователю.
    
    Args:
        bot: Объект Bot
        chat_id: ID чата для отправки
        text: Текст сообщения
        reply_markup: Объект разметки для клавиатуры
        parse_mode: Режим парсинга текста (None, HTML, Markdown)
        reply_to_message_id: ID сообщения, на которое нужно ответить
        disable_web_page_preview: Отключить предпросмотр ссылок
        
    Returns:
        Объект сообщения или None в случае ошибки
    """
    try:
        return await bot.send_message(
            chat_id=chat_id, 
            text=text, 
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            reply_to_message_id=reply_to_message_id,
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
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = None,
    disable_web_page_preview: bool = True
) -> Optional[Message]:
    """
    Безопасно редактирует сообщение.
    
    Args:
        bot: Объект Bot
        chat_id: ID чата
        message_id: ID сообщения для редактирования
        text: Новый текст сообщения
        reply_markup: Новый объект разметки для клавиатуры
        parse_mode: Режим парсинга текста
        disable_web_page_preview: Отключить предпросмотр ссылок
        
    Returns:
        Объект сообщения или None в случае ошибки
    """
    try:
        return await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview
        )
    except TelegramError as e:
        # Игнорируем ошибку, если сообщение не изменилось
        if "Message is not modified" not in str(e):
            logger.error(f"Ошибка при редактировании сообщения {message_id} для пользователя {chat_id}: {e}")
        return None

async def delete_message(bot: Bot, chat_id: int, message_id: int) -> bool:
    """
    Безопасно удаляет сообщение.
    
    Args:
        bot: Объект Bot
        chat_id: ID чата
        message_id: ID сообщения для удаления
        
    Returns:
        True если удаление успешно, иначе False
    """
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except TelegramError as e:
        # Игнорируем ошибку, если сообщение уже удалено
        if "Message to delete not found" not in str(e):
            logger.error(f"Ошибка при удалении сообщения {message_id} для пользователя {chat_id}: {e}")
        return False

def create_buttons(buttons: List[Tuple[str, str]], cols: int = 2) -> List[List[InlineKeyboardButton]]:
    """
    Создает список кнопок для InlineKeyboardMarkup с указанным количеством столбцов.
    
    Args:
        buttons: Список кортежей (текст_кнопки, callback_data)
        cols: Количество столбцов в клавиатуре
        
    Returns:
        Список списков кнопок для использования в InlineKeyboardMarkup
    """
    return [
        [InlineKeyboardButton(text, callback_data=data) for text, data in buttons[i:i+cols]]
        for i in range(0, len(buttons), cols)
    ]

def create_keyboard(buttons: List[str], cols: int = 2, one_time: bool = False, resize: bool = True) -> ReplyKeyboardMarkup:
    """
    Создает объект клавиатуры ReplyKeyboardMarkup с указанным количеством столбцов.
    
    Args:
        buttons: Список текстов кнопок
        cols: Количество столбцов в клавиатуре
        one_time: Скрывать клавиатуру после нажатия
        resize: Автоматический ресайз клавиатуры
        
    Returns:
        Объект ReplyKeyboardMarkup для отправки с сообщением
    """
    keyboard = [
        [KeyboardButton(buttons[i + j]) for j in range(cols) if i + j < len(buttons)]
        for i in range(0, len(buttons), cols)
    ]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=one_time, resize_keyboard=resize)

def format_folder_list(folders: List[str], current_path: str = "") -> str:
    """
    Форматирует список папок для отображения пользователю.
    
    Args:
        folders: Список папок для отображения
        current_path: Текущий путь (если есть)
        
    Returns:
        Отформатированный текст для отображения списка папок
    """
    if not folders:
        return "Папки не найдены."
    
    path_text = f"📁 Текущий путь: {current_path}\n\n" if current_path else ""
    
    if len(folders) > 20:
        # Если папок больше 20, показываем первые 20 и сообщаем о количестве остальных
        folders_text = "\n".join([f"📁 {folder}" for folder in folders[:20]])
        folders_text += f"\n\n...и еще {len(folders) - 20} папок"
    else:
        folders_text = "\n".join([f"📁 {folder}" for folder in folders])
    
    return f"{path_text}Доступные папки:\n{folders_text}"

def format_file_list(files: List[Dict[str, Any]]) -> str:
    """
    Форматирует список файлов для отображения пользователю.
    
    Args:
        files: Список словарей с информацией о файлах
        
    Returns:
        Отформатированный текст для отображения списка файлов
    """
    if not files:
        return "Файлы не найдены."
    
    files_text = ""
    for i, file in enumerate(files, 1):
        file_type = file.get('type', 'Файл')
        file_name = file.get('name', 'Без имени')
        file_caption = file.get('caption', '')
        caption_text = f" - {file_caption}" if file_caption else ""
        
        if file_type == 'photo':
            files_text += f"{i}. 📷 {file_name}{caption_text}\n"
        elif file_type == 'document':
            files_text += f"{i}. 📄 {file_name}{caption_text}\n"
        elif file_type == 'audio':
            files_text += f"{i}. 🎵 {file_name}{caption_text}\n"
        elif file_type == 'video':
            files_text += f"{i}. 📹 {file_name}{caption_text}\n"
        else:
            files_text += f"{i}. 📦 {file_name}{caption_text}\n"
    
    return f"Загруженные файлы:\n{files_text}"

def format_user_list(users: List[Dict[str, Any]]) -> str:
    """
    Форматирует список пользователей для отображения.
    
    Args:
        users: Список словарей с информацией о пользователях
        
    Returns:
        Отформатированный текст для отображения списка пользователей
    """
    if not users:
        return "Пользователи не найдены."
    
    users_text = ""
    for i, user in enumerate(users, 1):
        user_id = user.get('id', '???')
        username = user.get('username', 'Нет имени пользователя')
        first_name = user.get('first_name', '')
        last_name = user.get('last_name', '')
        
        # Формируем имя пользователя для отображения
        display_name = f"@{username}" if username else "No username"
        if first_name:
            display_name = first_name
            if last_name:
                display_name += f" {last_name}"
                
        users_text += f"{i}. {display_name} (ID: {user_id})\n"
    
    return f"Пользователи:\n{users_text}" 