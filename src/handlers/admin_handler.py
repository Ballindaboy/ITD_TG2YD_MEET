import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from config.config import is_admin, ROOT_DIRS
from src.utils.admin_utils import (
    add_allowed_folder, remove_allowed_folder, list_allowed_folders,
    add_allowed_user, remove_allowed_user, list_allowed_users
)
from src.utils.state_manager import state_manager

# Определение состояний для диалогов
ADMIN_MENU = 0
ADD_FOLDER = 1
REMOVE_FOLDER = 2
ADD_USER = 3
REMOVE_USER = 4
CHOOSE_CATEGORY = 5
FOLDER_PATH = 6
USER_ID = 7

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
    
    # Показываем административное меню
    keyboard = [
        ["📁 Добавить папку", "🗑 Удалить папку"],
        ["👤 Добавить пользователя", "❌ Удалить пользователя"],
        ["📋 Список папок", "👥 Список пользователей"],
        ["🔙 Выход"]
    ]
    
    await update.message.reply_text(
        "👨‍💼 Административное меню\n\n"
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    
    return ADMIN_MENU

async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора действия в административном меню"""
    text = update.message.text
    
    if text == "📁 Добавить папку":
        # Показываем клавиатуру с категориями
        keyboard = [
            ["1. Поставщики (TD.Equipment.Suppliers)"],
            ["2. Клиенты (TD.Equipment.Clients)"],
            ["3. Ценовые предложения (TD.Equipment.Offers)"],
            ["🔙 Назад"]
        ]
        
        await update.message.reply_text(
            "Выберите категорию для добавления папки:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        
        return CHOOSE_CATEGORY
    
    elif text == "🗑 Удалить папку":
        folders = list_allowed_folders()
        
        if folders == "Список разрешенных папок пуст":
            await update.message.reply_text(
                "❌ Список разрешенных папок пуст. Нечего удалять."
            )
            return await admin(update, context)
        
        await update.message.reply_text(
            f"{folders}\n\n"
            "Для удаления папки введите её полный путь и категорию в формате:\n"
            "<категория>:<путь>\n\n"
            "Например: suppliers:CompanyName\n\n"
            "Или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
        
        return REMOVE_FOLDER
    
    elif text == "👤 Добавить пользователя":
        await update.message.reply_text(
            "Введите ID пользователя для добавления в список разрешенных.\n\n"
            "Где взять ID пользователя?\n"
            "1. Попросите пользователя отправить сообщение боту @userinfobot\n"
            "2. Бот ответит информацией с ID\n\n"
            "Или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
        
        return ADD_USER
    
    elif text == "❌ Удалить пользователя":
        users = list_allowed_users()
        
        if users == "Список разрешенных пользователей пуст":
            await update.message.reply_text(
                "❌ Список разрешенных пользователей пуст. Нечего удалять."
            )
            return await admin(update, context)
        
        await update.message.reply_text(
            f"{users}\n\n"
            "Введите ID пользователя, которого нужно удалить из списка разрешенных.\n\n"
            "Или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
        
        return REMOVE_USER
    
    elif text == "📋 Список папок":
        folders = list_allowed_folders()
        
        await update.message.reply_text(
            folders,
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
        
        return ADMIN_MENU
    
    elif text == "👥 Список пользователей":
        users = list_allowed_users()
        
        await update.message.reply_text(
            users,
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
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

async def handle_category_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора категории при добавлении папки"""
    text = update.message.text
    
    if text == "🔙 Назад":
        return await admin(update, context)
    
    # Определяем категорию
    category = None
    if "1" in text or "Поставщик" in text or "Suppliers" in text:
        category = "suppliers"
        category_name = "Поставщики"
    elif "2" in text or "Клиент" in text or "Clients" in text:
        category = "clients"
        category_name = "Клиенты"
    elif "3" in text or "Ценов" in text or "Offers" in text:
        category = "offers"
        category_name = "Ценовые предложения"
    else:
        await update.message.reply_text(
            "❌ Пожалуйста, выберите категорию из предложенных вариантов."
        )
        return CHOOSE_CATEGORY
    
    # Сохраняем выбранную категорию
    context.user_data["admin_category"] = category
    context.user_data["admin_category_name"] = category_name
    
    await update.message.reply_text(
        f"Выбрана категория: {category_name}\n\n"
        "Введите имя папки, которую нужно добавить в список разрешенных.\n"
        "Например, если нужно добавить папку 'CompanyName' в категорию 'Поставщики',\n"
        "введите просто 'CompanyName' (без кавычек).\n\n"
        "Или нажмите '🔙 Назад' для возврата в меню.",
        reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
    )
    
    return FOLDER_PATH

async def handle_folder_path(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода пути папки при добавлении"""
    text = update.message.text
    
    if text == "🔙 Назад":
        return await admin(update, context)
    
    # Получаем сохраненную категорию
    category = context.user_data.get("admin_category")
    category_name = context.user_data.get("admin_category_name")
    
    if not category:
        await update.message.reply_text(
            "❌ Произошла ошибка. Категория не выбрана."
        )
        return await admin(update, context)
    
    # Добавляем папку в список разрешенных
    success, message = add_allowed_folder(text, category)
    
    if success:
        await update.message.reply_text(
            f"✅ {message}",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            f"❌ {message}\n\n"
            "Попробуйте еще раз или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
    
    # Возвращаемся к меню администратора
    return await admin(update, context)

async def handle_remove_folder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик удаления папки"""
    text = update.message.text
    
    if text == "🔙 Назад":
        return await admin(update, context)
    
    # Парсим ввод пользователя
    try:
        category, folder_path = text.split(":", 1)
        category = category.strip()
        folder_path = folder_path.strip()
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат. Пожалуйста, введите в формате: <категория>:<путь>\n"
            "Например: suppliers:CompanyName",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
        return REMOVE_FOLDER
    
    # Удаляем папку из списка разрешенных
    success, message = remove_allowed_folder(folder_path, category)
    
    if success:
        await update.message.reply_text(
            f"✅ {message}",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            f"❌ {message}\n\n"
            "Попробуйте еще раз или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
    
    # Возвращаемся к меню администратора
    return await admin(update, context)

async def handle_add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик добавления пользователя"""
    text = update.message.text
    
    if text == "🔙 Назад":
        return await admin(update, context)
    
    # Пробуем преобразовать ввод в число (ID пользователя)
    try:
        user_id = int(text)
    except ValueError:
        await update.message.reply_text(
            "❌ ID пользователя должен быть числом.\n\n"
            "Попробуйте еще раз или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
        return ADD_USER
    
    # Добавляем пользователя в список разрешенных
    success, message = add_allowed_user(user_id)
    
    if success:
        await update.message.reply_text(
            f"✅ {message}",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            f"❌ {message}\n\n"
            "Попробуйте еще раз или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
    
    # Возвращаемся к меню администратора
    return await admin(update, context)

async def handle_remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик удаления пользователя"""
    text = update.message.text
    
    if text == "🔙 Назад":
        return await admin(update, context)
    
    # Пробуем преобразовать ввод в число (ID пользователя)
    try:
        user_id = int(text)
    except ValueError:
        await update.message.reply_text(
            "❌ ID пользователя должен быть числом.\n\n"
            "Попробуйте еще раз или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
        return REMOVE_USER
    
    # Удаляем пользователя из списка разрешенных
    success, message = remove_allowed_user(user_id)
    
    if success:
        await update.message.reply_text(
            f"✅ {message}",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            f"❌ {message}\n\n"
            "Попробуйте еще раз или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
    
    # Возвращаемся к меню администратора
    return await admin(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет и завершает диалог"""
    await update.message.reply_text(
        "Административные действия отменены.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END 