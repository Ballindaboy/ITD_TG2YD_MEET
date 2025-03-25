import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CallbackContext
from src.utils.state_manager import state_manager, SessionState
from src.utils.yadisk_helper import YaDiskHelper
from src.utils.admin_utils import load_allowed_folders, get_allowed_folders_for_user, is_folder_allowed_for_user, get_user_data
import os
from datetime import datetime
from src.utils.folder_navigation import FolderNavigator

logger = logging.getLogger(__name__)
disk_helper = YaDiskHelper()

# Определение стадий диалога
CHOOSE_FOLDER, NAVIGATE_SUBFOLDERS, CREATE_FOLDER = range(3)

# Обработчик выбора папки через FolderNavigator
async def folder_selected_callback(update, context, selected_path):
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} выбрал папку: {selected_path}")
    
    # Вызываем handle_selected_folder без возврата его значения
    await handle_selected_folder(update, context, selected_path)
    # Возвращаем True, чтобы указать FolderNavigator, что обработка прошла успешно
    return True

# Создаем экземпляр навигатора по папкам
folder_navigator = FolderNavigator(
    yadisk_helper=disk_helper,
    title="Выберите папку для встречи:",
    add_current_folder_button=False,
    create_folder_button=False,
    extra_buttons=["❌ Отмена"]
)

# Устанавливаем callback для навигатора
folder_navigator.folder_selected_callback = folder_selected_callback

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
                if not disk_helper.disk.exists(selected_folder):
                    # Создаем папку, если она не существует
                    disk_helper.disk.mkdir(selected_folder)
                    logger.info(f"Создана папка '{selected_folder}'")
                
                # Получаем список подпапок
                try:
                    items = list(disk_helper.disk.listdir(selected_folder))
                    logger.info(f"Найдено {len(items)} элементов в директории {selected_folder}")
                    
                    # Явно проверяем элементы на тип
                    folders = []
                    for item in items:
                        if hasattr(item, 'type') and item.type == "dir":
                            folders.append(item)
                            logger.debug(f"Добавлена папка: {item.name}, Путь: {item.path}")
                        else:
                            logger.debug(f"Пропущен элемент: {item.name}, Тип: {getattr(item, 'type', 'неизвестен')}")
                    
                    logger.info(f"Из них {len(folders)} папок")
                    
                    # Сохраняем список подпапок
                    state_manager.set_data(user_id, "folders", folders)
                    
                    # Формируем клавиатуру
                    keyboard = []
                    message = f"📂 Подпапки в '{selected_folder}':\n\n"
                    
                    # Ограничиваем количество папок в одном сообщении
                    MAX_FOLDERS_PER_MESSAGE = 20
                    
                    # Добавляем существующие папки
                    if folders:
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
                    else:
                        message = f"📂 В папке '{selected_folder}' нет подпапок.\n\n"
                    
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
    
    logger.debug(f"Пользователь {user_id} выбрал '{text}' в папке '{selected_folder}'")
    
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
                
                logger.info(f"Пользователь выбрал подпапку: {folder_path}")
                
                # Проверяем, есть ли подпапки в выбранной папке
                try:
                    items = list(disk_helper.disk.listdir(folder_path))
                    logger.debug(f"Найдено {len(items)} элементов в {folder_path}")
                    
                    # Ищем папки среди элементов
                    subfolders = []
                    for item in items:
                        if hasattr(item, 'type') and item.type == "dir":
                            subfolders.append(item)
                    
                    logger.debug(f"Найдено {len(subfolders)} подпапок в {folder_path}")
                    
                    if subfolders:
                        # Если есть подпапки, предлагаем выбрать из них
                        state_manager.set_data(user_id, "selected_folder", folder_path)
                        state_manager.set_data(user_id, "folders", subfolders)
                        
                        # Формируем клавиатуру
                        keyboard = []
                        message = f"📂 Подпапки в '{folder_path}':\n\n"
                        
                        # Ограничиваем количество папок в одном сообщении
                        MAX_FOLDERS_PER_MESSAGE = 20
                        
                        # Формируем клавиатуру
                        for i, subfolder in enumerate(subfolders, 1):
                            keyboard.append([f"{i}. {subfolder.name}"])
                            
                            # Добавляем папку в сообщение только если не превышаем лимит
                            if i <= MAX_FOLDERS_PER_MESSAGE:
                                message += f"{i}. 📁 {subfolder.name}\n"
                        
                        # Если папок больше, чем MAX_FOLDERS_PER_MESSAGE, добавляем уведомление
                        if len(subfolders) > MAX_FOLDERS_PER_MESSAGE:
                            message += f"\n... и еще {len(subfolders) - MAX_FOLDERS_PER_MESSAGE} папок.\n"
                            message += "Выберите номер папки из клавиатуры ниже.\n"
                        
                        # Добавляем опции
                        keyboard.append(["📝 Использовать текущую папку"])
                        keyboard.append(["📁 Создать подпапку"])
                        keyboard.append(["❌ Отмена"])
                        
                        await update.message.reply_text(
                            message,
                            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
                        )
                        
                        return NAVIGATE_SUBFOLDERS
                    else:
                        # Если подпапок нет, предлагаем создать новую или использовать текущую
                        keyboard = [
                            ["📝 Использовать текущую папку"],
                            ["📁 Создать подпапку"], 
                            ["❌ Отмена"]
                        ]
                        
                        await update.message.reply_text(
                            f"📂 В папке '{folder_path}' нет подпапок.\n\n"
                            "Вы можете создать новую подпапку или использовать текущую папку.",
                            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
                        )
                        
                        # Сохраняем выбранную папку
                        state_manager.set_data(user_id, "selected_folder", folder_path)
                        
                        return NAVIGATE_SUBFOLDERS
                        
                except Exception as e:
                    logger.error(f"Ошибка при получении подпапок: {str(e)}", exc_info=True)
                    # Если возникла ошибка, предлагаем создать сессию в выбранной папке
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
        if disk_helper.disk.exists(new_folder_path):
            await update.message.reply_text(
                f"❌ Папка '{text}' уже существует",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Создаем папку
        disk_helper.disk.mkdir(new_folder_path)
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
        disk_helper.create_text_file(session.txt_file_path, f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {start_msg}")
        
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
        # Используем job_queue для планирования задачи, если он доступен
        if hasattr(context, 'job_queue') and context.job_queue is not None:
            context.job_queue.run_once(
                lambda context: check_session_activity(context, user_id),
                600,  # 10 минут в секундах
                data=user_id,
                name=f"session_timeout_{user_id}"
            )
            logger.info(f"Запланирована проверка активности сессии для пользователя {user_id}")
        else:
            logger.warning(f"job_queue недоступен для планирования проверки активности сессии пользователя {user_id}")
        
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
        if hasattr(context, 'job_queue') and context.job_queue is not None:
            context.job_queue.run_once(
                lambda context: check_session_activity(context, user_id),
                600,  # 10 минут в секундах
                data=user_id,
                name=f"session_timeout_{user_id}"
            )
            logger.info(f"Запланирована проверка активности сессии для пользователя {user_id}")
        else:
            logger.warning(f"job_queue недоступен для планирования проверки активности сессии пользователя {user_id}")
            await query.edit_message_text(
                text="✅ Встреча продлена еще на 10 минут.\n⚠️ Автоматическое напоминание об окончании недоступно."
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
        content = disk_helper.get_file_content(session.txt_file_path)
        # Добавляем завершающую запись
        content += f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {end_msg}"
        # Обновляем файл
        disk_helper.update_text_file(session.txt_file_path, content)
    except Exception as e:
        logger.error(f"Ошибка при обновлении файла встречи: {e}")
    
    # Сохраняем информацию о завершенной сессии для возможности возврата
    state_manager.set_data(user_id, "last_session_txt_file", session.txt_file_path)
    state_manager.set_data(user_id, "last_session_folder", session.folder_path)
    state_manager.set_data(user_id, "last_session_folder_name", session.folder_name)
    state_manager.set_data(user_id, "last_session_root_folder", session.root_folder)
    state_manager.set_data(user_id, "last_session_summary", summary)
    
    # Логируем сохраненные данные
    logger.info(f"Сохранены данные о завершенной сессии для пользователя {user_id}. Путь к файлу: {session.txt_file_path}")
    
    # Создаем клавиатуру для возврата в сессию
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Вернуться в сессию", callback_data="reopen_session")]
    ])
    
    # Логируем создание кнопки
    logger.info(f"Создана кнопка для возврата в сессию с callback_data='reopen_session'")
    
    # Показываем сводку и предлагаем вернуться в сессию
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
    if hasattr(context, 'job_queue') and context.job_queue is not None:
        current_jobs = context.job_queue.get_jobs_by_name(f"session_timeout_{user_id}")
        for job in current_jobs:
            job.schedule_removal()
        logger.info(f"Отменены запланированные проверки активности для пользователя {user_id}")
    else:
        logger.warning(f"job_queue недоступен для отмены проверок активности для пользователя {user_id}")

async def reopen_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает нажатие на кнопку "Вернуться в сессию"
    после завершения сессии, восстанавливая предыдущую сессию
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Логируем полученные данные для отладки
    logger.info(f"Обработка callback для кнопки 'Вернуться в сессию'. User ID: {user_id}, callback_data: {query.data}")
    
    # Получаем данные о текущей активной сессии пользователя (если есть)
    current_session = state_manager.get_session(user_id)
    
    # Если у пользователя есть активная сессия, спрашиваем подтверждение о закрытии
    if current_session:
        # Создаем клавиатуру для подтверждения
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да, закрыть текущую и открыть предыдущую", callback_data="confirm_reopen")],
            [InlineKeyboardButton("❌ Нет, остаться в текущей", callback_data="cancel_reopen")]
        ])
        
        await query.edit_message_text(
            text="⚠️ У вас уже есть активная сессия. Вы уверены, что хотите закрыть её и вернуться к предыдущей?",
            reply_markup=keyboard
        )
        return
    
    # Если нет активной сессии, восстанавливаем сохраненную
    await reopen_saved_session(update, context)

async def confirm_reopen_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает подтверждение закрытия текущей сессии и открытия предыдущей
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} подтвердил закрытие текущей сессии и возврат к предыдущей")
    
    # Закрываем текущую сессию
    current_session = state_manager.get_session(user_id)
    if current_session:
        # Добавляем запись о принудительном закрытии сессии
        end_msg = f"Сессия была закрыта для возврата к предыдущей сессии"
        current_session.add_message(end_msg)
        
        try:
            # Обновляем файл на Яндекс.Диске
            content = disk_helper.get_file_content(current_session.txt_file_path)
            content += f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {end_msg}"
            disk_helper.update_text_file(current_session.txt_file_path, content)
        except Exception as e:
            logger.error(f"Ошибка при обновлении файла текущей сессии: {e}")
        
        # Очищаем текущую сессию
        state_manager.clear_session(user_id)
    
    # Восстанавливаем предыдущую сессию
    await reopen_saved_session(update, context)

async def cancel_reopen_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает отмену возврата к предыдущей сессии
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} отменил возврат к предыдущей сессии")
    
    await query.edit_message_text(
        text="✅ Вы остались в текущей сессии. Продолжайте работу как обычно."
    )

async def reopen_saved_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Вспомогательная функция для восстановления сохраненной сессии
    """
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Получаем данные о сохраненной сессии
    txt_file_path = state_manager.get_data(user_id, "last_session_txt_file")
    folder_path = state_manager.get_data(user_id, "last_session_folder")
    folder_name = state_manager.get_data(user_id, "last_session_folder_name")
    root_folder = state_manager.get_data(user_id, "last_session_root_folder")
    
    if not all([txt_file_path, folder_path, folder_name, root_folder]):
        logger.error(f"Не найдены все необходимые данные для восстановления сессии: {txt_file_path}, {folder_path}, {folder_name}, {root_folder}")
        await query.edit_message_text(
            text="❌ Не удалось восстановить сессию. Отсутствуют необходимые данные."
        )
        return
    
    try:
        # Создаем новую сессию на основе сохраненных данных
        session = SessionState(root_folder, folder_path, folder_name, user_id)
        
        # Устанавливаем правильный путь к файлу (используем существующий, а не создаем новый)
        session.txt_file_path = txt_file_path
        
        # Добавляем запись о возобновлении сессии
        reopen_msg = f"Сессия была возобновлена в папке: {folder_path}"
        session.add_message(reopen_msg)
        
        # Обновляем файл на Яндекс.Диске
        try:
            content = disk_helper.get_file_content(txt_file_path)
            content += f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {reopen_msg}"
            disk_helper.update_text_file(txt_file_path, content)
        except Exception as e:
            logger.error(f"Ошибка при обновлении файла возобновленной сессии: {e}")
        
        # Сохраняем сессию в менеджере состояний
        state_manager.set_session(user_id, session)
        
        # Уведомляем пользователя об успешном восстановлении сессии
        await query.edit_message_text(
            text=f"✅ Сессия в папке {folder_path} успешно восстановлена.\n\nМожете продолжать работу как обычно."
        )
        
        logger.info(f"Сессия успешно восстановлена для пользователя {user_id}. Папка: {folder_path}")
        
    except Exception as e:
        logger.error(f"Ошибка при восстановлении сессии: {str(e)}", exc_info=True)
        await query.edit_message_text(
            text=f"❌ Произошла ошибка при восстановлении сессии: {str(e)}"
        )

async def switch_meeting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Переключает между встречами
    """
    user_id = update.effective_user.id
    user_session = state_manager.get_session(user_id)
    
    # Если есть активная сессия, завершаем ее перед переключением
    if user_session:
        await end_session_and_show_summary(update, context)
    
    # Запрашиваем выбор папки
    return await choose_folder(update, context)

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

async def choose_folder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отображает список доступных папок для пользователя и запрашивает выбор
    """
    user_id = update.effective_user.id
    
    # Получаем список разрешенных папок для этого пользователя
    allowed_folders = get_allowed_folders_for_user(user_id)
    
    if not allowed_folders:
        await update.message.reply_text(
            "❌ У вас нет доступа ни к одной папке. Обратитесь к администратору.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Обрабатываем тип вызова (callback_query или обычное сообщение)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text="👋 Выберите папку для встречи:",
            reply_markup=None
        )
        
        # Создаем сообщение и вызываем show_folders с пользовательскими папками
        message = await update.effective_chat.send_message(
            text="Загрузка папок...",
            reply_markup=None
        )
        # Обновляем message в update для корректной работы folder_navigator
        update.message = message
    
    # Запускаем навигацию по виртуальным папкам, которые соответствуют разрешенным для пользователя папкам
    # Создаем виртуальные элементы для навигатора, имитирующие структуру папок
    class VirtualFolder:
        def __init__(self, path, name):
            self.path = path
            self.name = name
            self.type = "dir"
    
    virtual_folders = [VirtualFolder(folder, folder.split('/')[-1]) for folder in allowed_folders]
    
    # Сохраняем виртуальные папки в контексте пользователя
    context.user_data["folders"] = virtual_folders
    context.user_data["current_path"] = "/"
    
    # Формируем сообщение со списком папок
    message = folder_navigator.format_folders_message("/", virtual_folders)
    
    # Формируем клавиатуру
    keyboard = folder_navigator.build_keyboard(virtual_folders, include_current_folder=False)
    
    # Отправляем сообщение с папками
    await update.message.reply_text(
        message,
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    
    # Сохраняем allowed_folders для использования в обработчике
    state_manager.set_user_data(user_id, "allowed_folders", allowed_folders)
    
    return CHOOSE_FOLDER 

async def handle_selected_folder(update: Update, context: ContextTypes.DEFAULT_TYPE, folder_path: str) -> int:
    """
    Обрабатывает выбранную папку и создает сессию
    """
    user_id = update.effective_user.id
    
    # Получаем имя пользователя
    user_name = update.effective_user.first_name
    if update.effective_user.last_name:
        user_name += f" {update.effective_user.last_name}"
    state_manager.set_user_data(user_id, "user_name", user_name)
    
    # Извлекаем имя папки из пути
    folder_name = folder_path.split('/')[-1]
    
    # Получаем корневую папку (в данном случае это родительская папка)
    root_folder = "/".join(folder_path.split('/')[:-1])
    state_manager.set_user_data(user_id, "root_folder", root_folder)
    
    # Создаем новую сессию
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_file = f"{folder_path}/meeting_{timestamp}.txt"
    
    state_manager.create_session(user_id, {
        "folder_path": folder_path,
        "folder_name": folder_name,
        "session_file": session_file,
        "root_folder": root_folder,
        "state": SessionState.ACTIVE
    })
    
    logging.debug(f"Создана новая сессия для пользователя {user_id} в папке {folder_path}")
    
    try:
        # Создаем файл на Яндекс.Диске с начальной записью
        disk_helper = YaDiskHelper()
        timestamp_log = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        initial_content = f"[{timestamp_log}] Система [СИСТЕМА]: Начало встречи в папке: {folder_path}\n"
        disk_helper.create_text_file(session_file, initial_content)
        
        await update.message.reply_text(
            text=f"✅ Начата новая сессия в папке: {folder_name}\n\n"
                 f"📝 Отправляйте текстовые сообщения и голосовые заметки, они будут добавлены в файл встречи.\n"
                 f"📊 По окончании нажмите /end для завершения и получения отчёта.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        logging.debug(f"Пользователь {user_id} начал сессию в папке {folder_path}")
        
        return SessionState.ACTIVE
    except Exception as e:
        logging.error(f"Ошибка при создании сессии: {e}")
        await update.message.reply_text(
            text=f"❌ Произошла ошибка при создании сессии: {e}",
            reply_markup=None
        )
        state_manager.clear_session(user_id)
        return ConversationHandler.END 