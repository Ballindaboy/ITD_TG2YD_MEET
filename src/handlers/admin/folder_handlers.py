"""
Модуль для обработки команд, связанных с управлением папками
в административном интерфейсе бота.
"""

import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from src.utils.admin_utils import (
    add_allowed_folder, remove_allowed_folder, list_allowed_folders
)
from src.utils.folder_navigation import FolderNavigator
from src.utils.yadisk_helper import YaDiskHelper
from src.utils.config_constants import (
    BUTTON_BACK, BUTTON_CANCEL, BUTTON_ADD_FOLDER, BUTTON_CREATE_FOLDER, BUTTON_RETURN_TO_ROOT,
    FOLDER_PERMISSIONS_PROMPT, FOLDER_ADDED_SUCCESS, FOLDER_ADDED_EXISTS
)

# Импортируем состояния из admin_handler
from src.handlers.admin.states import (
    ADMIN_MENU, FOLDER_PATH, FOLDER_PERMISSIONS, BROWSE_FOLDERS, 
    SELECT_SUBFOLDER, CREATE_SUBFOLDER
)

logger = logging.getLogger(__name__)
yadisk_helper = YaDiskHelper()

# Создаем экземпляр навигатора по папкам
folder_navigator = FolderNavigator(
    yadisk_helper=yadisk_helper,
    title="Выберите папку для добавления в список разрешенных:",
    add_current_folder_button=True,
    create_folder_button=True,
    extra_buttons=[BUTTON_CANCEL]
)

# Функция для возврата в админское меню
async def back_to_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вспомогательная функция для возврата в административное меню"""
    from src.handlers.admin.menu_handler import admin  # Импортируем здесь, чтобы избежать циклических импортов
    return await admin(update, context)

async def browse_folders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик навигации по папкам Яндекс.Диска"""
    # Обрабатываем сообщение с помощью навигатора папок
    success, selected_path, action_type = await folder_navigator.handle_message(update, context)
    
    # Если сообщение успешно обработано
    if success:
        # Действие в зависимости от типа
        if action_type == "back":
            return await back_to_admin_menu(update, context)
        
        elif action_type == "cancel":
            await update.message.reply_text(
                "❌ Операция отменена",
                reply_markup=ReplyKeyboardRemove()
            )
            return await back_to_admin_menu(update, context)
        
        elif action_type == "add_folder":
            # Добавляем текущую папку в список разрешенных
            success, message = add_allowed_folder(selected_path)
            
            if success:
                await update.message.reply_text(
                    f"✅ {message}\n\n" + FOLDER_PERMISSIONS_PROMPT,
                    reply_markup=ReplyKeyboardMarkup([["Да", "Нет"]], one_time_keyboard=True, resize_keyboard=True)
                )
                context.user_data["current_folder"] = selected_path
                return FOLDER_PERMISSIONS
            else:
                await update.message.reply_text(
                    f"❌ {message}",
                    reply_markup=ReplyKeyboardMarkup([[BUTTON_BACK]], one_time_keyboard=True, resize_keyboard=True)
                )
                return ADMIN_MENU
        
        elif action_type == "create_folder":
            # Переходим в состояние создания папки
            return CREATE_SUBFOLDER
        
        elif action_type == "navigate":
            # Продолжаем навигацию по папкам
            return BROWSE_FOLDERS
        
        # По умолчанию возвращаемся в меню навигации
        return BROWSE_FOLDERS
    
    # Если сообщение не обработано, продолжаем навигацию
    return BROWSE_FOLDERS

async def create_subfolder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Создает новую подпапку в текущем пути"""
    text = update.message.text
    
    if text == BUTTON_BACK:
        # Возвращаемся к навигации по папкам
        current_path = context.user_data.get("current_path", "/")
        await folder_navigator.show_folders(update, context, current_path)
        return BROWSE_FOLDERS
    
    # Создаем новую папку с помощью навигатора
    success, new_folder_path = await folder_navigator.create_folder(update, context, text)
    
    if success:
        # Спрашиваем, добавить ли созданную папку в список разрешенных
        await update.message.reply_text(
            "Добавить эту папку в список разрешенных?",
            reply_markup=ReplyKeyboardMarkup([
                [BUTTON_ADD_FOLDER], 
                [BUTTON_RETURN_TO_ROOT],
                [BUTTON_CANCEL]
            ], one_time_keyboard=True, resize_keyboard=True)
        )
        
        # Обновляем текущий путь
        context.user_data["current_path"] = new_folder_path
        return SELECT_SUBFOLDER
        
    # Если произошла ошибка при создании папки, продолжаем ожидать ввод
    return CREATE_SUBFOLDER

async def select_subfolder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора подпапки или добавления текущей папки"""
    text = update.message.text
    current_path = context.user_data.get("current_path", "/")
    
    if text == BUTTON_CANCEL:
        await update.message.reply_text(
            "❌ Операция отменена",
            reply_markup=ReplyKeyboardRemove()
        )
        return await back_to_admin_menu(update, context)
    
    if text == BUTTON_RETURN_TO_ROOT:
        # Возвращаемся к корневому выбору папок
        await folder_navigator.show_folders(update, context, "/")
        return BROWSE_FOLDERS
    
    if text == BUTTON_CREATE_FOLDER:
        await update.message.reply_text(
            f"📁 Введите название новой папки в '{current_path}':",
            reply_markup=ReplyKeyboardMarkup([[BUTTON_BACK]], one_time_keyboard=True, resize_keyboard=True)
        )
        return CREATE_SUBFOLDER
    
    if text == BUTTON_ADD_FOLDER or text == "✅ Добавить в разрешенные":
        # Добавляем текущую папку в список разрешенных
        success, message = add_allowed_folder(current_path)
        
        if success:
            await update.message.reply_text(
                f"✅ {message}\n\n" + FOLDER_PERMISSIONS_PROMPT,
                reply_markup=ReplyKeyboardMarkup([["Да", "Нет"]], one_time_keyboard=True, resize_keyboard=True)
            )
            context.user_data["current_folder"] = current_path
            return FOLDER_PERMISSIONS
        else:
            await update.message.reply_text(
                f"❌ {message}",
                reply_markup=ReplyKeyboardMarkup([[BUTTON_BACK]], one_time_keyboard=True, resize_keyboard=True)
            )
            return ADMIN_MENU
    
    # Если формат ввода неверный
    await update.message.reply_text(
        "❌ Пожалуйста, выберите действие из предложенного списка",
        reply_markup=ReplyKeyboardMarkup([[BUTTON_RETURN_TO_ROOT], [BUTTON_CANCEL]], one_time_keyboard=True, resize_keyboard=True)
    )
    return SELECT_SUBFOLDER

async def handle_folder_path(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода пути папки при добавлении"""
    text = update.message.text
    
    if text == BUTTON_BACK:
        return await back_to_admin_menu(update, context)
    
    # Добавляем папку в список разрешенных (без привязки к категории)
    success, message = add_allowed_folder(text)
    
    if success:
        await update.message.reply_text(
            f"✅ {message}\n\n" + FOLDER_PERMISSIONS_PROMPT,
            reply_markup=ReplyKeyboardMarkup([["Да", "Нет"]], one_time_keyboard=True, resize_keyboard=True)
        )
        context.user_data["current_folder"] = text
        return FOLDER_PERMISSIONS
    else:
        await update.message.reply_text(
            f"❌ {message}\n\n"
            "Попробуйте еще раз или нажмите '🔙 Назад' для возврата в меню.",
            reply_markup=ReplyKeyboardMarkup([[BUTTON_BACK]], one_time_keyboard=True, resize_keyboard=True)
        )
        return FOLDER_PATH

async def handle_remove_folder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик удаления папки из списка разрешенных"""
    text = update.message.text
    
    if text == BUTTON_BACK:
        return await back_to_admin_menu(update, context)
    
    # Удаляем папку из списка разрешенных
    success, message = remove_allowed_folder(text)
    
    await update.message.reply_text(
        f"{'✅' if success else '❌'} {message}",
        reply_markup=ReplyKeyboardMarkup([[BUTTON_BACK]], one_time_keyboard=True, resize_keyboard=True)
    )
    
    return REMOVE_FOLDER 