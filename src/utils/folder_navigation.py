import logging
from typing import List, Dict, Any, Tuple, Optional, Callable
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from src.utils.yadisk_helper import YaDiskHelper
from src.utils.config_constants import (
    MAX_FOLDERS_PER_MESSAGE,
    BUTTON_BACK, BUTTON_CANCEL, BUTTON_ADD_FOLDER, BUTTON_CREATE_FOLDER, BUTTON_RETURN_TO_ROOT,
    FOLDER_LIST_TITLE, FOLDER_SUBFOLDERS_TITLE, FOLDER_NO_SUBFOLDERS,
    FOLDER_SELECTION_ERROR, FOLDER_INVALID_NUMBER, FOLDER_CREATION_PROMPT,
    FOLDER_CREATION_SUCCESS, FOLDER_CREATION_ERROR, FOLDER_EXISTS_ERROR
)

logger = logging.getLogger(__name__)

class FolderNavigator:
    """
    Класс для работы с навигацией по папкам Яндекс.Диска в Telegram боте.
    """
    def __init__(
        self, 
        yadisk_helper: YaDiskHelper,
        folder_selected_callback: Optional[Callable] = None,
        title: str = FOLDER_LIST_TITLE,
        add_current_folder_button: bool = True,
        create_folder_button: bool = True,
        extra_buttons: List[str] = None,
        max_folders_per_message: int = MAX_FOLDERS_PER_MESSAGE
    ):
        """
        Инициализация навигатора по папкам.
        
        Args:
            yadisk_helper: Экземпляр YaDiskHelper для работы с Яндекс.Диском
            folder_selected_callback: Функция обратного вызова при выборе папки
            title: Заголовок сообщения при отображении списка папок
            add_current_folder_button: Добавлять ли кнопку "Добавить эту папку"
            create_folder_button: Добавлять ли кнопку "Создать новую папку"
            extra_buttons: Дополнительные кнопки для добавления в клавиатуру
            max_folders_per_message: Максимальное количество папок в одном сообщении
        """
        self.yadisk_helper = yadisk_helper
        self.title = title
        self.add_current_folder_button = add_current_folder_button
        self.create_folder_button = create_folder_button
        self.extra_buttons = extra_buttons or []
        self.max_folders_per_message = max_folders_per_message
        self.folder_selected_callback = folder_selected_callback
    
    @staticmethod
    def normalize_path(path: str) -> str:
        """
        Нормализует путь для Яндекс.Диска
        
        Args:
            path: Путь для нормализации
            
        Returns:
            Нормализованный путь
        """
        path = path.replace("disk:", "")
        path = path.replace("//", "/")
        path = path.rstrip("/")
        if not path.startswith("/"):
            path = "/" + path
        return path
    
    async def get_folders(self, path: str) -> List[Any]:
        """
        Получает список папок по указанному пути
        
        Args:
            path: Путь к директории
            
        Returns:
            Список папок
        """
        try:
            items = list(self.yadisk_helper.disk.listdir(path))
            return [item for item in items if item.type == "dir"]
        except Exception as e:
            logger.error(f"Ошибка при получении списка папок: {str(e)}", exc_info=True)
            return []
    
    def build_keyboard(self, folders: List[Any], include_current_folder: bool = True) -> List[List[str]]:
        """
        Формирует клавиатуру для выбора папок
        
        Args:
            folders: Список папок
            include_current_folder: Включать ли кнопку добавления текущей папки
            
        Returns:
            Клавиатура для ReplyKeyboardMarkup
        """
        keyboard = []
        
        # Добавляем папки в клавиатуру
        for i, folder in enumerate(folders, 1):
            keyboard.append([f"{i}. {folder.name}"])
        
        # Добавляем дополнительные кнопки
        if include_current_folder and self.add_current_folder_button:
            keyboard.append([BUTTON_ADD_FOLDER])
        
        if self.create_folder_button:
            keyboard.append([BUTTON_CREATE_FOLDER])
        
        # Добавляем дополнительные кнопки
        for button in self.extra_buttons:
            keyboard.append([button])
        
        # Всегда добавляем кнопку "Назад"
        keyboard.append([BUTTON_BACK])
        
        return keyboard
    
    def format_folders_message(self, path: str, folders: List[Any]) -> str:
        """
        Форматирует сообщение со списком папок
        
        Args:
            path: Текущий путь
            folders: Список папок
            
        Returns:
            Отформатированное сообщение
        """
        message = f"{self.title}\n\n"
        
        if path != "/":
            message = FOLDER_SUBFOLDERS_TITLE.format(path=path)
        
        # Добавляем папки в сообщение
        for i, folder in enumerate(folders, 1):
            if i <= self.max_folders_per_message:
                message += f"{i}. 📁 {folder.name}\n"
        
        # Если папок больше, чем можно показать, добавляем информацию об этом
        if len(folders) > self.max_folders_per_message:
            message += f"\n... и еще {len(folders) - self.max_folders_per_message} папок.\n"
            message += "Выберите номер папки из клавиатуры ниже.\n"
        
        return message
    
    async def show_folders(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE, 
        path: str = "/"
    ) -> None:
        """
        Отображает список папок по указанному пути
        
        Args:
            update: Объект Update
            context: Контекст телеграм-бота
            path: Путь к директории
        """
        normalized_path = self.normalize_path(path)
        folders = await self.get_folders(normalized_path)
        
        if not folders:
            await update.message.reply_text(
                FOLDER_NO_SUBFOLDERS.format(path=normalized_path),
                reply_markup=ReplyKeyboardMarkup(
                    self.build_keyboard([], include_current_folder=True),
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
            )
            return
        
        # Сохраняем список папок и путь в контексте
        context.user_data["folders"] = folders
        context.user_data["current_path"] = normalized_path
        
        # Отправляем сообщение с папками
        await update.message.reply_text(
            self.format_folders_message(normalized_path, folders),
            reply_markup=ReplyKeyboardMarkup(
                self.build_keyboard(folders),
                one_time_keyboard=True,
                resize_keyboard=True
            )
        )
    
    async def handle_folder_selection(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ) -> Tuple[bool, Optional[str]]:
        """
        Обрабатывает выбор папки пользователем
        
        Args:
            update: Объект Update
            context: Контекст телеграм-бота
            
        Returns:
            Кортеж (успешно ли выбрана папка, выбранный путь или None)
        """
        text = update.message.text
        current_path = context.user_data.get("current_path", "/")
        
        # Проверяем, выбран ли номер папки
        if text[0].isdigit():
            folder_idx = int(text.split(".")[0]) - 1
            folders = context.user_data.get("folders", [])
            
            if 0 <= folder_idx < len(folders):
                selected_folder = folders[folder_idx]
                selected_path = self.normalize_path(selected_folder.path)
                
                logger.info(f"Выбрана папка: {selected_path}")
                
                # Сохраняем выбранную папку и вызываем callback, если он есть
                if self.folder_selected_callback:
                    await self.folder_selected_callback(update, context, selected_path)
                
                return True, selected_path
            else:
                await update.message.reply_text(
                    FOLDER_INVALID_NUMBER,
                    reply_markup=ReplyKeyboardMarkup(
                        [[BUTTON_BACK]], 
                        one_time_keyboard=True, 
                        resize_keyboard=True
                    )
                )
                return False, None
        
        # Если дошли сюда, значит формат ввода неверный
        return False, None
    
    async def create_folder(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE,
        folder_name: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Создает новую папку
        
        Args:
            update: Объект Update
            context: Контекст телеграм-бота
            folder_name: Имя новой папки
            
        Returns:
            Кортеж (успешно ли создана папка, путь к новой папке или None)
        """
        current_path = context.user_data.get("current_path", "/")
        
        # Проверяем название папки
        if not folder_name or folder_name.isspace():
            await update.message.reply_text(
                FOLDER_EMPTY_NAME_ERROR,
                reply_markup=ReplyKeyboardMarkup(
                    [[BUTTON_BACK]], 
                    one_time_keyboard=True, 
                    resize_keyboard=True
                )
            )
            return False, None
        
        try:
            # Проверяем, существует ли уже такая папка
            new_folder_path = f"{current_path}/{folder_name}"
            if self.yadisk_helper.disk.exists(new_folder_path):
                await update.message.reply_text(
                    FOLDER_EXISTS_ERROR.format(name=folder_name),
                    reply_markup=ReplyKeyboardMarkup(
                        [[BUTTON_BACK]], 
                        one_time_keyboard=True, 
                        resize_keyboard=True
                    )
                )
                return False, None
            
            # Создаем новую папку
            new_folder_path = self.yadisk_helper.create_folder(current_path, folder_name)
            logger.info(f"Создана папка '{new_folder_path}'")
            
            await update.message.reply_text(
                FOLDER_CREATION_SUCCESS.format(name=folder_name, path=current_path),
                reply_markup=ReplyKeyboardMarkup(
                    [[BUTTON_ADD_FOLDER], [BUTTON_BACK]],
                    one_time_keyboard=True,
                    resize_keyboard=True
                )
            )
            
            # Обновляем текущий путь
            context.user_data["current_path"] = new_folder_path
            
            return True, new_folder_path
        except Exception as e:
            logger.error(f"Ошибка при создании папки: {str(e)}", exc_info=True)
            await update.message.reply_text(
                FOLDER_CREATION_ERROR.format(error=str(e)),
                reply_markup=ReplyKeyboardMarkup(
                    [[BUTTON_BACK]], 
                    one_time_keyboard=True, 
                    resize_keyboard=True
                )
            )
            return False, None
            
    async def handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Обрабатывает сообщение от пользователя в контексте навигации по папкам.
        
        Args:
            update: Объект Update
            context: Контекст телеграм-бота
            
        Returns:
            Кортеж (успешно ли обработано сообщение, выбранный путь или None, тип действия)
        """
        text = update.message.text
        current_path = context.user_data.get("current_path", "/")
        
        # Обработка кнопки "Назад"
        if text == BUTTON_BACK:
            return True, None, "back"
        
        # Обработка кнопки "Отмена"
        if text == BUTTON_CANCEL:
            return True, None, "cancel"
        
        # Обработка кнопки "К выбору папок"
        if text == BUTTON_RETURN_TO_ROOT:
            await self.show_folders(update, context, "/")
            return True, "/", "root"
        
        # Обработка кнопки "Создать новую папку"
        if text == BUTTON_CREATE_FOLDER:
            await update.message.reply_text(
                FOLDER_CREATION_PROMPT.format(path=current_path),
                reply_markup=ReplyKeyboardMarkup(
                    [[BUTTON_BACK]], 
                    one_time_keyboard=True, 
                    resize_keyboard=True
                )
            )
            return True, current_path, "create_folder"
        
        # Обработка кнопки "Добавить эту папку"
        if text == BUTTON_ADD_FOLDER:
            return True, current_path, "add_folder"
        
        # Обработка выбора папки по номеру
        success, selected_path = await self.handle_folder_selection(update, context)
        if success and selected_path:
            # Загружаем подпапки выбранной папки
            await self.show_folders(update, context, selected_path)
            return True, selected_path, "navigate"
            
        # Если сообщение не распознано
        await update.message.reply_text(
            FOLDER_SELECTION_ERROR,
            reply_markup=ReplyKeyboardMarkup(
                [[BUTTON_BACK]], 
                one_time_keyboard=True, 
                resize_keyboard=True
            )
        )
        return False, None, None 