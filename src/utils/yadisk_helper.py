import logging
import os
import yadisk
import tempfile
from config.config import YANDEX_DISK_TOKEN, ROOT_DIRS
import re

logger = logging.getLogger(__name__)

class YaDiskHelper:
    def __init__(self):
        self.disk = yadisk.YaDisk(token=YANDEX_DISK_TOKEN)
        self._check_connection()
        self._ensure_root_dirs()
    
    def _check_connection(self):
        """Проверяет подключение к Яндекс.Диску"""
        if not self.disk.check_token():
            raise ValueError("Неправильный токен Яндекс.Диска!")
    
    def _ensure_root_dirs(self):
        """Проверяет и создает корневые директории"""
        for path in ROOT_DIRS.values():
            path = f"/{path}"
            if not self.disk.exists(path):
                logger.info(f"Создаем корневую директорию: {path}")
                self.disk.mkdir(path)
    
    def search_folder(self, category: str, query: str):
        """Ищет папки в категории по запросу"""
        if category not in ROOT_DIRS:
            raise ValueError(f"Неизвестная категория: {category}")
        
        root_path = f"/{ROOT_DIRS[category]}"
        result = []
        
        try:
            # Получаем список всех папок в корневой директории
            items = self.disk.listdir(root_path)
            for item in items:
                if item.type == "dir" and query.lower() in item.name.lower():
                    result.append(item)
            
            return result
        except Exception as e:
            logger.error(f"Ошибка при поиске папки: {str(e)}", exc_info=True)
            return []
    
    def create_folder(self, category: str, folder_name: str):
        """Создает новую папку в указанной категории"""
        if category not in ROOT_DIRS:
            raise ValueError(f"Неизвестная категория: {category}")
        
        # Удаляем недопустимые символы из имени папки
        safe_folder_name = re.sub(r'[\\/*?:"<>|]', '', folder_name).strip()
        if not safe_folder_name:
            raise ValueError("Имя папки содержит только недопустимые символы")
        
        folder_path = f"/{ROOT_DIRS[category]}/{safe_folder_name}"
        
        try:
            if not self.disk.exists(folder_path):
                logger.info(f"Создаем папку: {folder_path}")
                self.disk.mkdir(folder_path)
            else:
                logger.info(f"Папка уже существует: {folder_path}")
            
            return folder_path
        except Exception as e:
            logger.error(f"Ошибка при создании папки: {str(e)}", exc_info=True)
            raise ValueError(f"Не удалось создать папку: {str(e)}")
    
    def upload_file(self, local_path: str, remote_path: str, progress_callback=None, overwrite=False):
        """Загружает файл на Яндекс.Диск"""
        try:
            logger.debug(f"Загрузка файла: {remote_path}")
            
            # Определяем размер файла для настройки таймаута
            file_size = os.path.getsize(local_path)
            
            # Устанавливаем таймаут в зависимости от размера файла
            # 1МБ = 1048576 байт
            timeout = 30.0  # базовый таймаут в секундах
            
            # Увеличиваем таймаут для больших файлов
            if file_size > 20 * 1048576:  # Более 20МБ
                timeout = 120.0  # 2 минуты
            elif file_size > 5 * 1048576:  # Более 5МБ
                timeout = 60.0   # 1 минута
            
            # Проверяем расширение для видео файлов
            if any(ext in remote_path.lower() for ext in ['.mp4', '.mov', '.avi', '.mkv']):
                timeout = max(timeout, 180.0)  # минимум 3 минуты для видео
            
            logger.info(f"Установлен таймаут {timeout}с для файла размером {file_size} байт")
            
            self.disk.upload(
                local_path, 
                remote_path, 
                overwrite=overwrite, 
                progress_callback=progress_callback,
                timeout=timeout
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка при загрузке файла: {str(e)}", exc_info=True)
            raise
    
    def get_download_link(self, path: str) -> str:
        """Получает ссылку на скачивание файла"""
        return self.disk.get_download_link(path)
    
    def _create_temp_file(self, content=''):
        """Создает временный файл с заданным содержимым"""
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(content)
        return tmp_path
    
    def create_text_file(self, path: str, content: str = ""):
        """Создает текстовый файл по указанному пути"""
        try:
            tmp_path = self._create_temp_file(content)
            
            # Загружаем на Яндекс.Диск
            self.upload_file(tmp_path, path)
            
            # Удаляем временный файл
            os.unlink(tmp_path)
            return True
        except Exception as e:
            logger.error(f"Ошибка при создании текстового файла: {str(e)}", exc_info=True)
            raise
    
    def append_to_text_file(self, path: str, content: str):
        """Добавляет текст в существующий файл"""
        tmp_path = None
        try:
            tmp_path = self._create_temp_file()
            
            try:
                # Пытаемся скачать существующий файл
                self.disk.download(path, tmp_path)
                
                # Добавляем новый контент
                with open(tmp_path, 'a', encoding='utf-8') as f:
                    f.write("\n" + content)
            except:
                # Если файл не существует, создаем новый
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            # Загружаем обратно на Яндекс.Диск с перезаписью
            self.disk.upload(tmp_path, path, overwrite=True)
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении текста в файл: {str(e)}", exc_info=True)
            raise
        finally:
            # Удаляем временный файл в блоке finally для гарантированной очистки
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def rename_folder(self, old_path: str, new_name: str):
        """Переименовывает папку"""
        try:
            # Получаем родительскую директорию
            parent_dir = os.path.dirname(old_path)
            new_path = f"{parent_dir}/{new_name}"
            
            # Проверяем существование новой папки
            if self.disk.exists(new_path):
                raise ValueError(f"Папка с именем {new_name} уже существует")
            
            # Переименовываем
            self.disk.move(old_path, new_path)
            return new_path
        except Exception as e:
            logger.error(f"Ошибка при переименовании папки: {str(e)}", exc_info=True)
            raise 