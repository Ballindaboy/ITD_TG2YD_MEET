import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from config.config import is_admin
from src.utils.admin_utils import (
    add_allowed_folder, remove_allowed_folder, list_allowed_folders,
    add_allowed_user, remove_allowed_user, list_allowed_users,
    update_folder_permissions, add_user_to_folder, remove_user_from_folder,
    load_allowed_users, load_allowed_folders
)
from src.utils.state_manager import state_manager
from src.utils.yadisk_helper import YaDiskHelper
import os

# Определение состояний для диалогов
ADMIN_MENU = 0
ADD_FOLDER = 1
REMOVE_FOLDER = 2
ADD_USER = 3
REMOVE_USER = 4
FOLDER_PATH = 5
USER_ID = 6
FOLDER_PERMISSIONS = 7
SELECT_FOLDER = 8
SELECT_USERS = 9
BROWSE_FOLDERS = 10
SELECT_SUBFOLDER = 11
CREATE_SUBFOLDER = 12

logger = logging.getLogger(__name__)
yadisk_helper = YaDiskHelper()

def normalize_path(path):
    """Нормализует путь для Яндекс.Диска"""
    path = path.replace("disk:", "")
    path = path.replace("//", "/")
    path = path.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return path

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
        ["🔐 Управление правами", "📋 Список папок"],
        ["👥 Список пользователей", "🔙 Выход"]
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
        # Инициализируем текущий путь для навигации
        context.user_data["current_path"] = "/"
        
        # Получаем список папок в корне
        try:
            items = list(yadisk_helper.disk.listdir("/"))
            folders = [item for item in items if item.type == "dir"]
            
            if not folders:
                await update.message.reply_text(
                    "📂 В корневой директории нет папок. Хотите создать новую?",
                    reply_markup=ReplyKeyboardMarkup([
                        ["📁 Создать новую папку"], 
                        ["🔙 Назад"]
                    ], one_time_keyboard=True, resize_keyboard=True)
                )
                context.user_data["current_path"] = "/"
                return CREATE_SUBFOLDER
            
            # Сохраняем список папок
            context.user_data["folders"] = folders
            
            # Формируем клавиатуру
            keyboard = []
            message = "📂 Выберите папку для добавления в список разрешенных:\n\n"
            
            # Ограничиваем количество папок в одном сообщении
            MAX_FOLDERS_PER_MESSAGE = 20
            
            for i, folder in enumerate(folders, 1):
                folder_name = folder.name
                keyboard.append([f"{i}. {folder_name}"])
                
                if i <= MAX_FOLDERS_PER_MESSAGE:
                    message += f"{i}. 📁 {folder_name}\n"
            
            if len(folders) > MAX_FOLDERS_PER_MESSAGE:
                message += f"\n... и еще {len(folders) - MAX_FOLDERS_PER_MESSAGE} папок.\n"
                message += "Выберите номер папки из клавиатуры ниже.\n"
            
            keyboard.append(["📁 Создать новую папку"])
            keyboard.append(["🔙 Назад"])
            
            await update.message.reply_text(
                message,
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            )
            
            return BROWSE_FOLDERS
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка папок: {str(e)}", exc_info=True)
            await update.message.reply_text(
                f"❌ Произошла ошибка при получении списка папок: {str(e)}",
                reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
            )
            return ADMIN_MENU
    
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
    
    elif text == "🔐 Управление правами":
        folders = load_allowed_folders()
        
        if not folders:
            await update.message.reply_text(
                "❌ Список разрешенных папок пуст. Сначала добавьте папки."
            )
            return await admin(update, context)
        
        # Создаем клавиатуру с папками
        keyboard = [[folder['path']] for folder in folders]
        keyboard.append(["🔙 Назад"])
        
        await update.message.reply_text(
            "Выберите папку для управления правами доступа:",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        
        return SELECT_FOLDER
    
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

async def browse_folders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик навигации по папкам Яндекс.Диска"""
    user_id = update.effective_user.id
    text = update.message.text
    current_path = context.user_data.get("current_path", "/")
    
    if text == "🔙 Назад":
        return await admin(update, context)
    
    if text == "📁 Создать новую папку":
        await update.message.reply_text(
            f"📁 Введите название новой папки в директории '{current_path}':",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
        return CREATE_SUBFOLDER
    
    # Получаем выбранную папку
    if text[0].isdigit():
        folder_idx = int(text.split(".")[0]) - 1
        folders = context.user_data.get("folders", [])
        
        if 0 <= folder_idx < len(folders):
            selected_folder = folders[folder_idx]
            selected_path = normalize_path(selected_folder.path)
            
            logger.info(f"Администратор выбрал папку: {selected_path}")
            
            # Сохраняем выбранную папку
            context.user_data["current_path"] = selected_path
            
            # Получаем подпапки
            try:
                items = list(yadisk_helper.disk.listdir(selected_path))
                subfolders = [item for item in items if item.type == "dir"]
                
                if not subfolders:
                    # Если подпапок нет, предлагаем добавить эту папку
                    await update.message.reply_text(
                        f"📂 Папка '{selected_path}' не содержит подпапок.\n\n"
                        "Вы хотите добавить эту папку в список разрешенных?",
                        reply_markup=ReplyKeyboardMarkup([
                            ["✅ Добавить эту папку"], 
                            ["📁 Создать подпапку"],
                            ["🔙 К выбору папок"],
                            ["❌ Отмена"]
                        ], one_time_keyboard=True, resize_keyboard=True)
                    )
                    return SELECT_SUBFOLDER
                
                # Сохраняем подпапки
                context.user_data["folders"] = subfolders
                
                # Формируем клавиатуру с подпапками
                keyboard = []
                message = f"📂 Подпапки в '{selected_path}':\n\n"
                
                # Ограничиваем количество папок в одном сообщении
                MAX_FOLDERS_PER_MESSAGE = 20
                
                for i, folder in enumerate(subfolders, 1):
                    folder_name = folder.name
                    keyboard.append([f"{i}. {folder_name}"])
                    
                    if i <= MAX_FOLDERS_PER_MESSAGE:
                        message += f"{i}. 📁 {folder_name}\n"
                
                if len(subfolders) > MAX_FOLDERS_PER_MESSAGE:
                    message += f"\n... и еще {len(subfolders) - MAX_FOLDERS_PER_MESSAGE} папок.\n"
                    message += "Выберите номер папки из клавиатуры ниже.\n"
                
                keyboard.append(["✅ Добавить эту папку"])
                keyboard.append(["📁 Создать подпапку"])
                keyboard.append(["🔙 К выбору папок"])
                keyboard.append(["❌ Отмена"])
                
                await update.message.reply_text(
                    message,
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
                )
                
                return BROWSE_FOLDERS
                
            except Exception as e:
                logger.error(f"Ошибка при получении списка подпапок: {str(e)}", exc_info=True)
                await update.message.reply_text(
                    f"❌ Произошла ошибка при получении списка подпапок: {str(e)}",
                    reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
                )
                return ADMIN_MENU
        else:
            await update.message.reply_text(
                "❌ Неверный номер папки",
                reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
            )
            return BROWSE_FOLDERS
    
    # Если дошли сюда, значит формат ввода неверный
    await update.message.reply_text(
        "❌ Пожалуйста, выберите папку из предложенного списка",
        reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
    )
    return BROWSE_FOLDERS

async def select_subfolder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора подпапки или добавления текущей папки"""
    text = update.message.text
    current_path = context.user_data.get("current_path", "/")
    
    if text == "❌ Отмена":
        await update.message.reply_text(
            "❌ Операция отменена",
            reply_markup=ReplyKeyboardRemove()
        )
        return await admin(update, context)
    
    if text == "🔙 К выбору папок":
        # Возвращаемся к корневому выбору папок
        context.user_data["current_path"] = "/"
        
        try:
            items = list(yadisk_helper.disk.listdir("/"))
            folders = [item for item in items if item.type == "dir"]
            context.user_data["folders"] = folders
            
            keyboard = []
            
            for i, folder in enumerate(folders, 1):
                keyboard.append([f"{i}. {folder.name}"])
            
            keyboard.append(["📁 Создать новую папку"])
            keyboard.append(["🔙 Назад"])
            
            await update.message.reply_text(
                "📂 Выберите папку для добавления в список разрешенных:",
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            )
            
            return BROWSE_FOLDERS
        except Exception as e:
            logger.error(f"Ошибка при возврате к выбору папок: {str(e)}", exc_info=True)
            return await admin(update, context)
    
    if text == "📁 Создать подпапку":
        await update.message.reply_text(
            f"📁 Введите название новой подпапки в '{current_path}':",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
        return CREATE_SUBFOLDER
    
    if text == "✅ Добавить эту папку":
        # Добавляем текущую папку в список разрешенных
        success, message = add_allowed_folder(current_path)
        
        if success:
            await update.message.reply_text(
                f"✅ {message}\n\n"
                "Хотите добавить пользователей с доступом к этой папке?",
                reply_markup=ReplyKeyboardMarkup([["Да", "Нет"]], one_time_keyboard=True, resize_keyboard=True)
            )
            context.user_data["current_folder"] = current_path
            return FOLDER_PERMISSIONS
        else:
            await update.message.reply_text(
                f"❌ {message}",
                reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
            )
            return ADMIN_MENU
    
    # Если формат ввода неверный
    await update.message.reply_text(
        "❌ Пожалуйста, выберите действие из предложенного списка",
        reply_markup=ReplyKeyboardMarkup([["🔙 К выбору папок"], ["❌ Отмена"]], one_time_keyboard=True, resize_keyboard=True)
    )
    return SELECT_SUBFOLDER

async def create_subfolder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Создает новую подпапку в текущем пути"""
    text = update.message.text
    current_path = context.user_data.get("current_path", "/")
    
    if text == "🔙 Назад":
        return await browse_folders(update, context)
    
    # Проверяем название папки
    if not text or text.isspace():
        await update.message.reply_text(
            "❌ Название папки не может быть пустым",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
        return CREATE_SUBFOLDER
    
    # Создаем путь к новой папке
    new_folder_path = f"{current_path}/{text}"
    
    try:
        # Проверяем, существует ли уже такая папка
        if yadisk_helper.disk.exists(new_folder_path):
            await update.message.reply_text(
                f"❌ Папка '{text}' уже существует",
                reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
            )
            return CREATE_SUBFOLDER
        
        # Создаем папку
        yadisk_helper.disk.mkdir(new_folder_path)
        logger.info(f"Создана папка '{new_folder_path}'")
        
        # Спрашиваем, добавить ли созданную папку в список разрешенных
        await update.message.reply_text(
            f"✅ Папка '{text}' успешно создана в '{current_path}'.\n\n"
            "Добавить эту папку в список разрешенных?",
            reply_markup=ReplyKeyboardMarkup([
                ["✅ Добавить в разрешенные"], 
                ["🔙 Вернуться к навигации"],
                ["❌ Отмена"]
            ], one_time_keyboard=True, resize_keyboard=True)
        )
        
        # Обновляем текущий путь
        context.user_data["current_path"] = new_folder_path
        return SELECT_SUBFOLDER
        
    except Exception as e:
        logger.error(f"Ошибка при создании папки: {str(e)}", exc_info=True)
        await update.message.reply_text(
            f"❌ Произошла ошибка при создании папки: {str(e)}",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
        return ADMIN_MENU

async def handle_folder_path(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода пути папки при добавлении"""
    text = update.message.text
    
    if text == "🔙 Назад":
        return await admin(update, context)
    
    # Добавляем папку в список разрешенных (без привязки к категории)
    success, message = add_allowed_folder(text)
    
    if success:
        await update.message.reply_text(
            f"✅ {message}\n\n"
            "Хотите добавить пользователей с доступом к этой папке?",
            reply_markup=ReplyKeyboardMarkup([["Да", "Нет"]], one_time_keyboard=True, resize_keyboard=True)
        )
        context.user_data["current_folder"] = text
        return FOLDER_PERMISSIONS
    else:
        await update.message.reply_text(
            f"❌ {message}\n\n"
            "Попробуйте еще раз или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
        return FOLDER_PATH

async def handle_folder_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора настройки прав доступа к папке"""
    text = update.message.text
    
    if text == "Нет":
        return await admin(update, context)
    
    if text == "Да":
        users = load_allowed_users()
        folder_path = context.user_data.get("current_folder")
        
        if not users:
            await update.message.reply_text(
                "❌ Список разрешенных пользователей пуст. Сначала добавьте пользователей.",
                reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
            )
            return ADMIN_MENU
        
        # Создаем клавиатуру с пользователями и опцией "Все пользователи"
        keyboard = []
        for user in users:
            name = user.get('username') or user.get('first_name') or f"ID: {user['id']}"
            keyboard.append([f"{name} [{user['id']}]"])
        
        keyboard.append(["✅ Сохранить"])
        keyboard.append(["🔙 Назад"])
        
        await update.message.reply_text(
            f"Выберите пользователей с доступом к папке '{folder_path}'.\n"
            "Нажимайте на пользователей для выбора/отмены выбора.\n"
            "По умолчанию, если не выбран ни один пользователь, папка доступна всем.",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
        )
        
        # Инициализируем список выбранных пользователей
        context.user_data["selected_users"] = []
        
        return SELECT_USERS
    
    await update.message.reply_text(
        "❌ Пожалуйста, выберите 'Да' или 'Нет'.",
        reply_markup=ReplyKeyboardMarkup([["Да", "Нет"]], one_time_keyboard=True, resize_keyboard=True)
    )
    
    return FOLDER_PERMISSIONS

async def handle_select_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора пользователей для доступа к папке"""
    text = update.message.text
    
    if text == "🔙 Назад":
        return await admin(update, context)
    
    if text == "✅ Сохранить":
        folder_path = context.user_data.get("current_folder")
        selected_users = context.user_data.get("selected_users", [])
        
        # Обновляем права доступа к папке
        success, message = update_folder_permissions(folder_path, selected_users)
        
        if success:
            await update.message.reply_text(
                f"✅ {message}",
                reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
            )
        else:
            await update.message.reply_text(
                f"❌ {message}",
                reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
            )
        
        return await admin(update, context)
    
    # Извлекаем ID пользователя из текста (формат "name [id]")
    try:
        user_id = int(text.split('[')[-1].split(']')[0])
        
        selected_users = context.user_data.get("selected_users", [])
        
        # Переключаем выбор пользователя
        if user_id in selected_users:
            selected_users.remove(user_id)
            await update.message.reply_text(f"❌ Пользователь удален из списка доступа")
        else:
            selected_users.append(user_id)
            await update.message.reply_text(f"✅ Пользователь добавлен в список доступа")
        
        context.user_data["selected_users"] = selected_users
        
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Неверный формат. Пожалуйста, выберите пользователя из списка.")
    
    return SELECT_USERS

async def handle_select_folder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора папки для управления правами"""
    text = update.message.text
    
    if text == "🔙 Назад":
        return await admin(update, context)
    
    # Проверяем существование папки
    folders = load_allowed_folders()
    folder_exists = False
    current_users = []
    
    for folder in folders:
        if folder['path'] == text:
            folder_exists = True
            current_users = folder.get('allowed_users', [])
            break
    
    if not folder_exists:
        await update.message.reply_text(
            "❌ Папка не найдена.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
        return await admin(update, context)
    
    # Сохраняем выбранную папку и текущих пользователей
    context.user_data["current_folder"] = text
    context.user_data["selected_users"] = current_users
    
    # Получаем список пользователей
    users = load_allowed_users()
    
    # Создаем клавиатуру с пользователями и выделяем уже выбранных
    keyboard = []
    for user in users:
        name = user.get('username') or user.get('first_name') or f"ID: {user['id']}"
        prefix = "✅ " if user['id'] in current_users else ""
        keyboard.append([f"{prefix}{name} [{user['id']}]"])
    
    keyboard.append(["✅ Сохранить"])
    keyboard.append(["🔙 Назад"])
    
    await update.message.reply_text(
        f"Управление правами доступа к папке '{text}'.\n\n"
        f"{'✅ В данный момент папка доступна только выбранным пользователям' if current_users else '⚠️ В данный момент папка доступна всем пользователям'}.\n\n"
        "Нажимайте на пользователей для выбора/отмены выбора.\n"
        "Если не выбран ни один пользователь, папка будет доступна всем.",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
    )
    
    return SELECT_USERS

async def handle_remove_folder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик удаления папки"""
    text = update.message.text
    
    if text == "🔙 Назад":
        return await admin(update, context)
    
    # Удаляем папку из списка разрешенных
    success, message = remove_allowed_folder(text)
    
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
    
    try:
        user_id = int(text.strip())
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. ID пользователя должен быть числом.\n\n"
            "Попробуйте еще раз или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], one_time_keyboard=True, resize_keyboard=True)
        )
        return ADD_USER
    
    # Пробуем получить информацию о пользователе из чата (если доступно)
    username = None
    first_name = None
    last_name = None
    
    chat_member = await update.effective_chat.get_member(user_id=user_id)
    if chat_member:
        username = chat_member.user.username
        first_name = chat_member.user.first_name
        last_name = chat_member.user.last_name
    
    # Добавляем пользователя в список разрешенных
    success, message = add_allowed_user(user_id, username, first_name, last_name)
    
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
    
    try:
        user_id = int(text.strip())
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. ID пользователя должен быть числом.\n\n"
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
    """Отменяет всю операцию"""
    await update.message.reply_text(
        "Операция отменена.",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Очищаем пользовательские данные
    context.user_data.clear()
    
    return ConversationHandler.END 