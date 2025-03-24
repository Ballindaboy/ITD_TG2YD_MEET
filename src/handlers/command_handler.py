import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CallbackContext
from src.utils.state_manager import state_manager
from src.utils.yadisk_helper import YaDiskHelper
from src.utils.admin_utils import load_allowed_folders, get_allowed_folders_for_user, is_folder_allowed_for_user, get_user_data
import os
from datetime import datetime

logger = logging.getLogger(__name__)
yadisk_helper = YaDiskHelper()

# Определение стадий диалога
CHOOSE_FOLDER, NAVIGATE_SUBFOLDERS, CREATE_FOLDER = range(3)

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
    
    # Получаем список разрешенных папок для этого пользователя
    allowed_folders = get_allowed_folders_for_user(user_id)
    
    if not allowed_folders:
        await update.message.reply_text(
            "❌ У вас нет доступа ни к одной папке. Обратитесь к администратору.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Создаем клавиатуру для выбора папки
    keyboard = []
    for i, folder in enumerate(allowed_folders, 1):
        keyboard.append([f"{i}. {folder}"])
    
    keyboard.append(["❌ Отмена"])
    
    await update.message.reply_text(
        "👋 Выберите папку для встречи:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    
    # Сохраняем список разрешенных папок в состоянии пользователя
    state_manager.set_data(user_id, "allowed_folders", allowed_folders)
    
    return CHOOSE_FOLDER

async def handle_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор папки"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if text == "❌ Отмена":
        await update.message.reply_text(
            "❌ Создание встречи отменено",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Получаем выбранную папку
    if text[0].isdigit():
        folder_idx = int(text.split(".")[0]) - 1
        allowed_folders = state_manager.get_data(user_id, "allowed_folders")
        
        if 0 <= folder_idx < len(allowed_folders):
            selected_folder = allowed_folders[folder_idx]
            
            logger.info(f"Пользователь {user_id} выбрал папку: {selected_folder}")
            
            # Сохраняем выбранную папку
            state_manager.set_data(user_id, "selected_folder", selected_folder)
            
            # Получаем список подпапок или создаем сессию сразу
            try:
                # Проверяем существование директории
                if not yadisk_helper.disk.exists(selected_folder):
                    # Создаем папку, если она не существует
                    yadisk_helper.disk.mkdir(selected_folder)
                    logger.info(f"Создана папка '{selected_folder}'")
                
                # Получаем список подпапок
                items = list(yadisk_helper.disk.listdir(selected_folder))
                logger.info(f"Найдено {len(items)} элементов в директории")
                
                folders = [item for item in items if item.type == "dir"]
                logger.info(f"Из них {len(folders)} папок")
                
                if not folders:
                    # Если подпапок нет, создаем сессию прямо в выбранной папке
                    return await start_session(update, context, selected_folder, selected_folder)
                
                # Сохраняем список подпапок
                state_manager.set_data(user_id, "folders", folders)
                
                # Формируем клавиатуру
                keyboard = []
                message = f"📂 Подпапки в '{selected_folder}':\n\n"
                
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
                
                # Добавляем опцию создания сессии в текущей папке
                keyboard.append(["📝 Использовать текущую папку"])
                keyboard.append(["📁 Создать подпапку"])
                keyboard.append(["❌ Отмена"])
                
                await update.message.reply_text(
                    message,
                    reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
                )
                
                return NAVIGATE_SUBFOLDERS
                
            except Exception as e:
                logger.error(f"Ошибка при получении списка папок: {str(e)}", exc_info=True)
                await update.message.reply_text(
                    f"❌ Произошла ошибка при получении списка папок: {str(e)}",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
        else:
            await update.message.reply_text(
                "❌ Неверный номер папки",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ Пожалуйста, выберите папку из предложенного списка",
            reply_markup=ReplyKeyboardRemove()
        )
        return CHOOSE_FOLDER

async def navigate_folders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает выбор подпапки"""
    user_id = update.effective_user.id
    text = update.message.text
    selected_folder = state_manager.get_data(user_id, "selected_folder")
    
    if text == "❌ Отмена":
        await update.message.reply_text(
            "❌ Создание встречи отменено",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    if text == "📁 Создать подпапку":
        await update.message.reply_text(
            "📁 Введите название новой подпапки:",
            reply_markup=ReplyKeyboardRemove()
        )
        return CREATE_FOLDER
    
    if text == "📝 Использовать текущую папку":
        # Создаем сессию в выбранной папке
        return await start_session(update, context, selected_folder, selected_folder)
    
    try:
        # Проверяем, выбрал ли пользователь папку из списка
        if text[0].isdigit():
            folder_idx = int(text.split(".")[0]) - 1
            folders = state_manager.get_data(user_id, "folders")
            
            if 0 <= folder_idx < len(folders):
                selected_subfolder = folders[folder_idx]
                folder_path = normalize_path(selected_subfolder.path)
                folder_name = selected_subfolder.name
                
                # Создаем сессию в выбранной подпапке
                return await start_session(update, context, selected_folder, folder_path)
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

async def create_folder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Создает новую подпапку"""
    user_id = update.effective_user.id
    text = update.message.text
    selected_folder = state_manager.get_data(user_id, "selected_folder")
    
    # Проверяем название папки
    if not text or text.isspace():
        await update.message.reply_text(
            "❌ Название папки не может быть пустым",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Создаем путь к новой папке
    new_folder_path = f"{selected_folder}/{text}"
    
    try:
        # Проверяем, существует ли уже такая папка
        if yadisk_helper.disk.exists(new_folder_path):
            await update.message.reply_text(
                f"❌ Папка '{text}' уже существует",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Создаем папку
        yadisk_helper.disk.mkdir(new_folder_path)
        logger.info(f"Создана папка '{new_folder_path}'")
        
        # Создаем сессию в новой папке
        return await start_session(update, context, selected_folder, new_folder_path)
        
    except Exception as e:
        logger.error(f"Ошибка при создании папки: {str(e)}", exc_info=True)
        await update.message.reply_text(
            f"❌ Произошла ошибка при создании папки: {str(e)}",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def start_session(update: Update, context: ContextTypes.DEFAULT_TYPE, root_folder: str, folder_path: str) -> int:
    """Начинает сессию встречи"""
    from src.utils.state_manager import SessionState
    
    user_id = update.effective_user.id
    
    # Нормализуем пути к папкам
    root_folder = normalize_path(root_folder)
    folder_path = normalize_path(folder_path)
    folder_name = os.path.basename(folder_path)
    
    # Получаем данные пользователя для добавления в историю
    user_data = get_user_data(user_id)
    user_full_name = None
    if user_data:
        first_name = user_data.get('first_name', '')
        last_name = user_data.get('last_name', '')
        if first_name or last_name:
            user_full_name = f"{first_name} {last_name}".strip()
    
    try:
        # Создаем сессию
        session = SessionState(root_folder, folder_path, folder_name, user_id)
        state_manager.set_session(user_id, session)
        
        # Добавляем первое сообщение в историю
        start_msg = f"Начало встречи в папке: {folder_path}"
        session.add_message(start_msg, author=user_full_name)
        
        # Создаем текстовый файл для встречи
        yadisk_helper.create_text_file(session.txt_file_path, f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {start_msg}")
        
        # Уведомляем о создании встречи
        await update.message.reply_text(
            f"🆕 Создана новая встреча:\n"
            f"Папка: {folder_path}\n"
            f"Файл: {session.get_txt_filename()}\n\n"
            f"✍️ Можете отправлять текст, голос, фото или видео.\n"
            f"Для завершения встречи используйте /switch\n\n"
            f"⏱ Через 10 минут бездействия будет предложено завершить встречу.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Планируем запрос о закрытии сессии через 10 минут
        # Используем job_queue для планирования задачи
        context.job_queue.run_once(
            lambda context: check_session_activity(context, user_id),
            600,  # 10 минут в секундах
            data=user_id,
            name=f"session_timeout_{user_id}"
        )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка при создании сессии: {str(e)}", exc_info=True)
        await update.message.reply_text(
            f"❌ Произошла ошибка при создании сессии: {str(e)}",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def check_session_activity(context: CallbackContext, user_id: int) -> None:
    """
    Проверяет активность сессии и предлагает закрыть её при необходимости
    """
    # Получаем сессию пользователя
    session = state_manager.get_session(user_id)
    if not session:
        logger.info(f"Сессия для пользователя {user_id} уже закрыта")
        return
    
    # Создаем клавиатуру для ответа
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Завершить встречу", callback_data="end_session")],
        [InlineKeyboardButton("⏱ Продолжить еще 10 минут", callback_data="extend_session")]
    ])
    
    try:
        # Отправляем сообщение с предложением закрыть сессию
        await context.bot.send_message(
            chat_id=user_id,
            text="⏱ Прошло 10 минут с момента последней активности.\nХотите завершить текущую встречу?",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о неактивности: {e}")

async def handle_session_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает ответ на запрос о закрытии сессии
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data == "end_session":
        # Завершаем сессию и показываем сводку
        await end_session_and_show_summary(update, context)
    elif data == "extend_session":
        # Продлеваем сессию еще на 10 минут
        await query.edit_message_text(
            text="✅ Встреча продлена еще на 10 минут."
        )
        
        # Планируем новый запрос через 10 минут
        context.job_queue.run_once(
            lambda context: check_session_activity(context, user_id),
            600,  # 10 минут в секундах
            data=user_id,
            name=f"session_timeout_{user_id}"
        )

async def end_session_and_show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Завершает сессию и показывает итоговую сводку
    """
    user_id = update.effective_user.id
    session = state_manager.get_session(user_id)
    
    if not session:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text="❌ Нет активной встречи для завершения."
            )
        else:
            await update.message.reply_text(
                "❌ Нет активной встречи для завершения."
            )
        return
    
    # Получаем сводку по сессии
    summary = session.get_session_summary()
    
    # Добавляем финальную запись в текстовый файл
    end_msg = f"Завершение встречи в папке: {session.folder_path}"
    session.add_message(end_msg)
    
    # Обновляем файл на Яндекс.Диске
    try:
        # Загружаем текущее содержимое
        content = yadisk_helper.get_file_content(session.txt_file_path)
        # Добавляем завершающую запись
        content += f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {end_msg}"
        # Обновляем файл
        yadisk_helper.update_text_file(session.txt_file_path, content)
    except Exception as e:
        logger.error(f"Ошибка при обновлении файла встречи: {e}")
    
    # Создаем клавиатуру для добавления комментария
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Добавить комментарий", callback_data="add_final_comment")]
    ])
    
    # Показываем сводку и предлагаем добавить комментарий
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=f"✅ Встреча завершена\n\n{summary[:3900]}...",  # Ограничиваем размер сообщения
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            f"✅ Встреча завершена\n\n{summary[:3900]}...",  # Ограничиваем размер сообщения
            reply_markup=keyboard
        )
    
    # Очищаем сессию
    state_manager.clear_session(user_id)
    
    # Отменяем запланированные задачи для этого пользователя
    current_jobs = context.job_queue.get_jobs_by_name(f"session_timeout_{user_id}")
    for job in current_jobs:
        job.schedule_removal()

async def switch_meeting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /switch - переключение на другую встречу"""
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} хочет переключиться на другую встречу")
    
    # Проверяем, есть ли активная сессия
    session = state_manager.get_session(user_id)
    if session:
        # Завершаем текущую сессию и показываем сводку
        await end_session_and_show_summary(update, context)
    
    # Начинаем новую встречу
    return await new_meeting(update, context)

async def current_meeting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /current - показывает информацию о текущей встрече"""
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запросил информацию о текущей встрече")
    
    # Проверяем, есть ли активная сессия
    session = state_manager.get_session(user_id)
    if session:
        # Получаем данные пользователя
        user_data = get_user_data(user_id)
        user_info = ""
        if user_data:
            first_name = user_data.get('first_name', '')
            last_name = user_data.get('last_name', '')
            if first_name or last_name:
                user_info = f"👤 Участник: {first_name} {last_name}\n"
        
        # Считаем количество файлов и сообщений
        files_count = len(session.file_history)
        messages_count = len(session.message_history)
        
        await update.message.reply_text(
            f"📝 Текущая встреча:\n"
            f"📂 Папка: {session.folder_path}\n"
            f"📄 Файл: {session.get_txt_filename()}\n"
            f"⏱ Начало: {session.created_at}\n"
            f"{user_info}"
            f"📊 Сообщений: {messages_count}, Файлов: {files_count}\n\n"
            f"✍️ Можете отправлять текст, голос, фото или видео."
        )
    else:
        await update.message.reply_text(
            "❌ У вас нет активной встречи. Используйте /new, чтобы начать новую встречу."
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет создание встречи"""
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} отменил создание встречи")
    
    await update.message.reply_text(
        "❌ Создание встречи отменено",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return ConversationHandler.END 