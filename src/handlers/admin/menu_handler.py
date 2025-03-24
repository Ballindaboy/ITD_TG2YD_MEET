"""
Модуль с обработчиками для административного меню бота.
"""

import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from config.config import is_admin
from src.utils.admin_utils import list_allowed_folders, list_allowed_users, load_allowed_folders
from src.utils.config_constants import (
    BUTTON_BACK, USER_EMPTY_LIST, ADMIN_WELCOME_MESSAGE
)

# Импортируем состояния из admin_handler
from src.handlers.admin.states import (
    ADMIN_MENU, ADD_FOLDER, REMOVE_FOLDER, ADD_USER, REMOVE_USER,
    BROWSE_FOLDERS, SELECT_FOLDER
)

logger = logging.getLogger(__name__)

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /admin - показывает административное меню"""
    user_id = update.effective_user.id
    
    # Проверяем, имеет ли пользователь права администратора
    if not is_admin(user_id):
        await update.message.reply_text(
            "⛔ У вас нет прав администратора."
        )
        return ConversationHandler.END
    
    # Формируем клавиатуру с действиями администратора
    keyboard = [
        ["📁 Добавить папку", "🗑 Удалить папку"],
        ["👤 Добавить пользователя", "❌ Удалить пользователя"],
        ["🔐 Управление правами"],
        ["📋 Список папок", "👥 Список пользователей"],
        ["🔙 Выход"]
    ]
    
    await update.message.reply_text(
        ADMIN_WELCOME_MESSAGE,
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    
    return ADMIN_MENU

async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора действия в административном меню"""
    text = update.message.text
    
    if text == "📁 Добавить папку":
        # Инициализируем навигатор и показываем корневые папки
        from src.handlers.admin.folder_handlers import folder_navigator
        await folder_navigator.show_folders(update, context, "/")
        return BROWSE_FOLDERS
    
    elif text == "🗑 Удалить папку":
        folders = list_allowed_folders()
        
        if folders == "Список разрешенных папок пуст":
            await update.message.reply_text(
                "❌ Список разрешенных папок пуст. Нечего удалять."
            )
            return await admin(update, context)
        
        await update.message.reply_text(
            f"{folders}\n\n"
            "Для удаления папки введите её полный путь.\n"
            "Например: Проект123\n\n"
            "Или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([[BUTTON_BACK]], one_time_keyboard=True, resize_keyboard=True)
        )
        
        return REMOVE_FOLDER
    
    elif text == "👤 Добавить пользователя":
        await update.message.reply_text(
            "Введите ID пользователя для добавления в список разрешенных.\n\n"
            "Где взять ID пользователя?\n"
            "1. Попросите пользователя отправить сообщение боту @userinfobot\n"
            "2. Бот ответит информацией с ID\n\n"
            "Или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([[BUTTON_BACK]], one_time_keyboard=True, resize_keyboard=True)
        )
        
        return ADD_USER
    
    elif text == "❌ Удалить пользователя":
        users = list_allowed_users()
        
        if users == "Список разрешенных пользователей пуст":
            await update.message.reply_text(
                USER_EMPTY_LIST
            )
            return await admin(update, context)
        
        await update.message.reply_text(
            f"{users}\n\n"
            "Введите ID пользователя, которого нужно удалить из списка разрешенных.\n\n"
            "Или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([[BUTTON_BACK]], one_time_keyboard=True, resize_keyboard=True)
        )
        
        return REMOVE_USER
    
    elif text == "🔐 Управление правами":
        folders = load_allowed_folders()
        
        if not folders:
            await update.message.reply_text(
                "❌ Список разрешенных папок пуст. Сначала добавьте папки."
            )
            return await admin(update, context)
        
        # Создаем клавиатуру с папками
        keyboard = [[folder['path']] for folder in folders]
        keyboard.append([BUTTON_BACK])
        
        await update.message.reply_text(
            "Выберите папку для управления правами доступа:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        
        return SELECT_FOLDER
    
    elif text == "📋 Список папок":
        folders = list_allowed_folders()
        
        await update.message.reply_text(
            folders,
            reply_markup=ReplyKeyboardMarkup([[BUTTON_BACK]], one_time_keyboard=True, resize_keyboard=True)
        )
        
        return ADMIN_MENU
    
    elif text == "👥 Список пользователей":
        users = list_allowed_users()
        
        await update.message.reply_text(
            users,
            reply_markup=ReplyKeyboardMarkup([[BUTTON_BACK]], one_time_keyboard=True, resize_keyboard=True)
        )
        
        return ADMIN_MENU
    
    elif text == "🔙 Выход":
        await update.message.reply_text(
            "✅ Выход из административного меню",
            reply_markup=ReplyKeyboardRemove()
        )
        
        return ConversationHandler.END
    
    else:
        await update.message.reply_text(
            "❌ Неизвестная команда. Пожалуйста, выберите действие из меню."
        )
        
        return await admin(update, context)

async def handle_select_folder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора папки для управления правами доступа"""
    text = update.message.text
    
    if text == BUTTON_BACK:
        return await admin(update, context)
    
    # Сохраняем выбранную папку
    context.user_data["current_folder"] = text
    
    # Отображаем меню управления правами доступа
    await update.message.reply_text(
        f"Управление правами доступа к папке '{text}'\n\n"
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(
            [["Управление правами"], [BUTTON_BACK]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    
    # Переходим к диалогу управления правами доступа
    from src.handlers.admin.states import FOLDER_PERMISSIONS
    return FOLDER_PERMISSIONS

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущее действие и выходит из административного режима"""
    await update.message.reply_text(
        "❌ Операция отменена.",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return ConversationHandler.END 