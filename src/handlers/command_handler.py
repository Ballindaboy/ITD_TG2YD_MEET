import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from src.utils.state_manager import state_manager
from src.utils.yadisk_helper import YaDiskHelper
import os

logger = logging.getLogger(__name__)
yadisk_helper = YaDiskHelper()

# Определение стадий диалога
CHOOSE_CATEGORY, NAVIGATE_FOLDERS, CREATE_FOLDER = range(3)

# Пути к папкам категорий
CATEGORY_PATHS = {
    "suppliers": "/TD/TD.Equipment.Suppliers",
    "clients": "/TD/TD.Equipment.Clients",
    "offers": "/TD/TD.Equipment.Offers"
}

def normalize_path(path):
    """Нормализует путь для Яндекс.Диска"""
    path = path.replace("disk:", "")
    path = path.replace("//", "/")
    path = path.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return path

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    logger.info(f"Пользователь {update.effective_user.id} запустил бота")
    await update.message.reply_text(
        "👋 Привет! Я бот для регистрации встреч на выставке.\n\n"
        "Команды:\n"
        "/new - начать новую встречу\n"
        "/switch - переключиться на другую встречу\n"
        "/current - показать текущую встречу\n"
        "/help - справка"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    logger.info(f"Пользователь {update.effective_user.id} запросил помощь")
    await update.message.reply_text(
        "🔖 Помощь по командам:\n\n"
        "/new - начать новую встречу\n"
        "/switch - переключиться на другую встречу\n"
        "/current - показать текущую встречу\n"
        "/help - эта справка\n\n"
        "Во время встречи вы можете:\n"
        "- Отправлять текст - он добавится в отчет\n"
        "- Отправлять фото, видео, голосовые - они будут сохранены автоматически\n"
    )

async def new_meeting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает создание новой встречи"""
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} начинает новую встречу")
    
    # Создаем клавиатуру для выбора категории
    keyboard = [
        ["1. Поставщики (TD.Equipment.Suppliers)"],
        ["2. Клиенты (TD.Equipment.Clients)"],
        ["3. Ценовые предложения (TD.Equipment.Offers)"]
    ]
    
    await update.message.reply_text(
        "👋 Выберите категорию встречи:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    
    return CHOOSE_CATEGORY

async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор категории"""
    user_id = update.effective_user.id
    text = update.message.text
    
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
    
    logger.info(f"Пользователь {user_id} выбрал категорию: {category}")
    
    # Сохраняем выбранную категорию
    state_manager.set_data(user_id, "category", category)
    state_manager.set_data(user_id, "category_name", category_name)
    
    # Путь к выбранной категории
    current_path = CATEGORY_PATHS[category]
    state_manager.set_data(user_id, "current_path", current_path)
    
    # Получаем список папок в выбранной категории
    try:
        logger.info(f"Ищем папки в директории '{current_path}'")
        
        # Проверяем существование директории
        if not yadisk_helper.disk.exists(current_path):
            logger.error(f"Директория '{current_path}' не существует")
            await update.message.reply_text(
                f"❌ Директория '{current_path}' не существует.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        items = list(yadisk_helper.disk.listdir(current_path))
        logger.info(f"Найдено {len(items)} элементов в директории")
        
        folders = [item for item in items if item.type == "dir"]
        logger.info(f"Из них {len(folders)} папок")
        
        if not folders:
            await update.message.reply_text(
                f"📂 В категории {category_name} нет папок.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Сохраняем список папок
        state_manager.set_data(user_id, "folders", folders)
        
        # Формируем клавиатуру
        keyboard = []
        message = f"📂 Папки в категории {category_name}:\n\n"
        
        # Ограничиваем количество папок в одном сообщении
        MAX_FOLDERS_PER_MESSAGE = 20
        
        # Формируем клавиатуру
        for i, folder in enumerate(folders, 1):
            folder_name = folder.name
            keyboard.append([f"{i}. {folder_name}"])
            
            # Добавляем папку в сообщение только если не превышаем лимит
            if i <= MAX_FOLDERS_PER_MESSAGE:
                message += f"{i}. 📁 {folder_name}\n"
        
        # Если папок больше, чем MAX_FOLDERS_PER_MESSAGE, добавляем уведомление
        if len(folders) > MAX_FOLDERS_PER_MESSAGE:
            message += f"\n... и еще {len(folders) - MAX_FOLDERS_PER_MESSAGE} папок.\n"
            message += "Выберите номер папки из клавиатуры ниже.\n"
        
        keyboard.append(["📁 Создать папку"])
        keyboard.append(["❌ Отмена"])
        
        await update.message.reply_text(
            message,
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
        
        return NAVIGATE_FOLDERS
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка папок: {str(e)}", exc_info=True)
        await update.message.reply_text(
            f"❌ Произошла ошибка при получении списка папок: {str(e)}",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def navigate_folders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор папки"""
    user_id = update.effective_user.id
    text = update.message.text
    category = state_manager.get_data(user_id, "category")
    category_name = state_manager.get_data(user_id, "category_name")
    
    if text == "❌ Отмена":
        await update.message.reply_text(
            "❌ Создание встречи отменено",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    if text == "📁 Создать папку":
        await update.message.reply_text(
            "📁 Введите название новой папки:",
            reply_markup=ReplyKeyboardRemove()
        )
        return CREATE_FOLDER
    
    try:
        # Проверяем, выбрал ли пользователь папку из списка
        if text[0].isdigit():
            folder_idx = int(text.split(".")[0]) - 1
            folders = state_manager.get_data(user_id, "folders")
            
            if 0 <= folder_idx < len(folders):
                selected_folder = folders[folder_idx]
                folder_path = normalize_path(selected_folder.path)
                folder_name = selected_folder.name
                
                # Создаем сессию в выбранной папке
                return await start_session(update, context, category, folder_path, folder_name)
            else:
                await update.message.reply_text(
                    "❌ Неверный номер папки",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка при выборе папки: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при выборе папки",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def start_session(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str, folder_path: str, folder_name: str) -> int:
    """Начинает сессию встречи"""
    from src.utils.state_manager import SessionState
    
    user_id = update.effective_user.id
    
    try:
        # Создаем сессию
        session = SessionState(category, folder_path, folder_name)
        state_manager.set_session(user_id, session)
        
        # Создаем текстовый файл для встречи
        yadisk_helper.create_text_file(session.txt_file_path, "")
        
        await update.message.reply_text(
            f"🆕 Создана новая встреча:\n"
            f"Категория: {state_manager.get_data(user_id, 'category_name')}\n"
            f"Папка: {folder_name}\n"
            f"Файл: {session.get_txt_filename()}\n\n"
            f"✍️ Можете отправлять текст, голос, фото или видео.\n"
            f"Для завершения встречи используйте /switch",
            reply_markup=ReplyKeyboardRemove()
        )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка при создании сессии: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "❌ Произошла ошибка при создании сессии",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def switch_meeting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Переключается на другую встречу"""
    user_id = update.effective_user.id
    session = state_manager.get_session(user_id)
    
    if session:
        # Запоминаем данные о завершенной встрече для информационного сообщения
        completed_folder_name = session.folder_name
        
        # Завершаем текущую сессию
        state_manager.clear_session(user_id)
        
        # Создаем клавиатуру с кнопкой новой встречи
        keyboard = [["🆕 Начать новую встречу"]]
        
        await update.message.reply_text(
            "🔚 Встреча завершена.\n"
            f"Файлы сохранены в {completed_folder_name}.",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )
    else:
        # Создаем клавиатуру с кнопкой новой встречи
        keyboard = [["🆕 Начать новую встречу"]]
        
        await update.message.reply_text(
            "❌ Нет активной встречи.",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )

async def current_meeting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает информацию о текущей встрече"""
    user_id = update.effective_user.id
    session = state_manager.get_session(user_id)
    
    if session:
        category_name = ""
        if session.category == "suppliers":
            category_name = "Поставщики"
        elif session.category == "clients":
            category_name = "Клиенты"
        elif session.category == "offers":
            category_name = "Ценовые предложения"
            
        await update.message.reply_text(
            f"📋 Текущая встреча:\n"
            f"Категория: {category_name}\n"
            f"Папка: {session.folder_name}\n"
            f"Файл: {session.get_txt_filename()}"
        )
    else:
        # Создаем клавиатуру с кнопкой новой встречи
        keyboard = [["🆕 Начать новую встречу"]]
        
        await update.message.reply_text(
            "❌ Нет активной встречи.",
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущий диалог"""
    await update.message.reply_text(
        "❌ Операция отменена.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def create_folder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает создание новой папки"""
    user_id = update.effective_user.id
    folder_name = update.message.text.strip()
    category = state_manager.get_data(user_id, "category")
    current_path = state_manager.get_data(user_id, "current_path")
    
    try:
        # Проверяем длину имени папки
        if len(folder_name) < 2:
            await update.message.reply_text(
                "❌ Название папки должно содержать минимум 2 символа. Попробуйте снова:"
            )
            return CREATE_FOLDER
        
        # Создаем новую папку
        logger.info(f"Создание новой папки '{folder_name}' в пути '{current_path}'")
        
        # Получаем полный путь
        folder_path = f"{current_path}/{folder_name}"
        folder_path = normalize_path(folder_path)
        
        # Создаем папку на Яндекс.Диске
        if not yadisk_helper.disk.exists(folder_path):
            yadisk_helper.disk.mkdir(folder_path)
            logger.info(f"Папка создана: {folder_path}")
            
            await update.message.reply_text(
                f"✅ Папка '{folder_name}' успешно создана.\n"
                f"Теперь создаем встречу в этой папке."
            )
            
            # Создаем сессию в новой папке
            return await start_session(update, context, category, folder_path, folder_name)
        else:
            logger.warning(f"Папка уже существует: {folder_path}")
            await update.message.reply_text(
                f"⚠️ Папка с именем '{folder_name}' уже существует.\n"
                f"Создаем встречу в существующей папке."
            )
            return await start_session(update, context, category, folder_path, folder_name)
            
    except Exception as e:
        logger.error(f"Ошибка при создании папки: {str(e)}", exc_info=True)
        await update.message.reply_text(
            f"❌ Ошибка при создании папки: {str(e)}.\n"
            f"Пожалуйста, попробуйте снова или выберите существующую папку.",
            reply_markup=ReplyKeyboardRemove()
        )
        # Возвращаемся к выбору категории
        return await new_meeting(update, context) 