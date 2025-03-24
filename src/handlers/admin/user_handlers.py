"""
Модуль для обработки команд, связанных с управлением пользователями
в административном интерфейсе бота.
"""

import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from src.utils.admin_utils import (
    add_allowed_user, remove_allowed_user, list_allowed_users,
    update_folder_permissions, add_user_to_folder, remove_user_from_folder,
    load_allowed_users
)
from src.utils.config_constants import (
    BUTTON_BACK, USER_ADDED_SUCCESS, USER_ADDED_EXISTS, USER_REMOVED_SUCCESS,
    USER_REMOVED_NOT_FOUND, USER_EMPTY_LIST
)

# Импортируем состояния из admin_handler
from src.handlers.admin.states import (
    ADMIN_MENU, ADD_USER, REMOVE_USER, FOLDER_PERMISSIONS, SELECT_USERS
)

logger = logging.getLogger(__name__)

# Функция для возврата в админское меню
async def back_to_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вспомогательная функция для возврата в административное меню"""
    from src.handlers.admin.menu_handler import admin  # Импортируем здесь, чтобы избежать циклических импортов
    return await admin(update, context)

async def handle_add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик добавления пользователя в список разрешенных"""
    text = update.message.text
    
    if text == BUTTON_BACK:
        return await back_to_admin_menu(update, context)
    
    try:
        # Проверяем, является ли введенный текст числом (ID пользователя)
        user_id = int(text)
        
        # Добавляем пользователя в список разрешенных
        success, message = add_allowed_user(user_id)
        
        await update.message.reply_text(
            f"{'✅' if success else '❌'} {message}",
            reply_markup=ReplyKeyboardMarkup([[BUTTON_BACK]], one_time_keyboard=True, resize_keyboard=True)
        )
        
        return ADD_USER
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID пользователя. ID должен быть числом.\n\n"
            "Попробуйте еще раз или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([[BUTTON_BACK]], one_time_keyboard=True, resize_keyboard=True)
        )
        return ADD_USER

async def handle_remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик удаления пользователя из списка разрешенных"""
    text = update.message.text
    
    if text == BUTTON_BACK:
        return await back_to_admin_menu(update, context)
    
    try:
        # Проверяем, является ли введенный текст числом (ID пользователя)
        user_id = int(text)
        
        # Удаляем пользователя из списка разрешенных
        success, message = remove_allowed_user(user_id)
        
        await update.message.reply_text(
            f"{'✅' if success else '❌'} {message}",
            reply_markup=ReplyKeyboardMarkup([[BUTTON_BACK]], one_time_keyboard=True, resize_keyboard=True)
        )
        
        return REMOVE_USER
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID пользователя. ID должен быть числом.\n\n"
            "Попробуйте еще раз или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([[BUTTON_BACK]], one_time_keyboard=True, resize_keyboard=True)
        )
        return REMOVE_USER

async def handle_folder_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик настройки прав доступа к папке"""
    text = update.message.text
    current_folder = context.user_data.get("current_folder", "")
    
    if text == "Нет" or text == BUTTON_BACK:
        return await back_to_admin_menu(update, context)
    
    if text == "Да" or text == "Управление правами":
        # Загружаем список разрешенных пользователей
        users = load_allowed_users()
        
        if not users:
            await update.message.reply_text(
                USER_EMPTY_LIST + "\n\n"
                "Сначала добавьте пользователей в список разрешенных.",
                reply_markup=ReplyKeyboardMarkup([[BUTTON_BACK]], one_time_keyboard=True, resize_keyboard=True)
            )
            return ADMIN_MENU
        
        # Получаем текущие права доступа к папке
        context.user_data["editing_folder_permissions"] = True
        
        # Формируем клавиатуру с пользователями
        keyboard = []
        
        for user in users:
            user_id = user["user_id"]
            username = user.get("username", "")
            first_name = user.get("first_name", "")
            last_name = user.get("last_name", "")
            
            # Создаем понятное отображение пользователя
            display_name = username or f"{first_name} {last_name}".strip() or str(user_id)
            
            # Формируем кнопку для выбора/отмены выбора пользователя
            has_access = context.user_data.get("selected_users", {}).get(str(user_id), False)
            prefix = "✅" if has_access else "⬜"
            
            keyboard.append([InlineKeyboardButton(f"{prefix} {display_name} ({user_id})", callback_data=f"user_{user_id}")])
        
        # Добавляем кнопку "Готово"
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="done")])
        
        await update.message.reply_text(
            f"Управление правами доступа к папке '{current_folder}'\n\n"
            "Нажимайте на пользователей для выбора/отмены выбора.\n"
            "Когда закончите, нажмите 'Готово'.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return SELECT_USERS
    
    # Если введено что-то другое
    await update.message.reply_text(
        "❓ Пожалуйста, выберите 'Да' или 'Нет'.",
        reply_markup=ReplyKeyboardMarkup([["Да", "Нет"]], one_time_keyboard=True, resize_keyboard=True)
    )
    
    return FOLDER_PERMISSIONS

async def handle_select_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора пользователей для доступа к папке"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "done":
        # Пользователь завершил выбор
        current_folder = context.user_data.get("current_folder", "")
        selected_users = context.user_data.get("selected_users", {})
        
        # Конвертируем словарь {user_id: True/False} в список ID выбранных пользователей
        user_ids = [int(user_id) for user_id, selected in selected_users.items() if selected]
        
        # Обновляем права доступа к папке
        success, message = update_folder_permissions(current_folder, user_ids)
        
        await query.edit_message_text(
            f"{'✅' if success else '❌'} {message}",
            reply_markup=None
        )
        
        # Очищаем временные данные
        if "selected_users" in context.user_data:
            del context.user_data["selected_users"]
        if "editing_folder_permissions" in context.user_data:
            del context.user_data["editing_folder_permissions"]
        
        # Возвращаемся в меню администратора
        return await back_to_admin_menu(update, context)
    
    if data.startswith("user_"):
        # Пользователь выбрал/отменил выбор пользователя
        user_id = data.split("_")[1]
        
        # Инициализируем словарь выбранных пользователей, если его нет
        if "selected_users" not in context.user_data:
            context.user_data["selected_users"] = {}
        
        # Инвертируем состояние выбора
        current_state = context.user_data["selected_users"].get(user_id, False)
        context.user_data["selected_users"][user_id] = not current_state
        
        # Обновляем клавиатуру
        # Загружаем список разрешенных пользователей
        users = load_allowed_users()
        
        # Формируем клавиатуру с пользователями
        keyboard = []
        
        for user in users:
            user_id_from_list = user["user_id"]
            username = user.get("username", "")
            first_name = user.get("first_name", "")
            last_name = user.get("last_name", "")
            
            # Создаем понятное отображение пользователя
            display_name = username or f"{first_name} {last_name}".strip() or str(user_id_from_list)
            
            # Формируем кнопку для выбора/отмены выбора пользователя
            has_access = context.user_data["selected_users"].get(str(user_id_from_list), False)
            prefix = "✅" if has_access else "⬜"
            
            keyboard.append([InlineKeyboardButton(f"{prefix} {display_name} ({user_id_from_list})", callback_data=f"user_{user_id_from_list}")])
        
        # Добавляем кнопку "Готово"
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="done")])
        
        # Обновляем сообщение с новой клавиатурой
        current_folder = context.user_data.get("current_folder", "")
        
        await query.edit_message_text(
            f"Управление правами доступа к папке '{current_folder}'\n\n"
            "Нажимайте на пользователей для выбора/отмены выбора.\n"
            "Когда закончите, нажмите 'Готово'.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return SELECT_USERS
    
    return SELECT_USERS 