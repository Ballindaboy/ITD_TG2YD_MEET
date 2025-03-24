import logging
import os
import yadisk
import tempfile
import time
from config.config import YANDEX_DISK_TOKEN
import re

logger = logging.getLogger(__name__)

class YaDiskHelper:
    def __init__(self):
        self.disk = yadisk.YaDisk(token=YANDEX_DISK_TOKEN)
        self._check_connection()
    
    def _check_connection(self):
        """Проверяет подключение к Яндекс.Диску"""
        try:
            if not self.disk.check_token():
                raise ValueError("Неправильный токен Яндекс.Диска!")
        except Exception as e:
            if "timeout" in str(e).lower():
                logger.warning("Превышено время ожидания при проверке токена Яндекс.Диска. Продолжаем работу с предположением, что токен валиден.")
            else:
                logger.error(f"Ошибка при проверке токена Яндекс.Диска: {str(e)}")
                raise
    
    def ensure_folder_exists(self, path):
        """Проверяет существование папки и создает ее при необходимости"""
        if not self.disk.exists(path):
            logger.info(f"Создаем директорию: {path}")
            # Создаем каждый уровень папок
            parts = path.strip('/').split('/')
            current_path = ""
            for part in parts:
                if part:
                    current_path = f"{current_path}/{part}"
                    if not self.disk.exists(current_path):
                        self.disk.mkdir(current_path)
            return True
        return False
    
    def search_folder(self, parent_path: str, query: str):
        """Ищет папки в указанном пути по запросу"""
        result = []
        
        try:
            # Проверяем существование родительской папки
            if not self.disk.exists(parent_path):
                logger.warning(f"Папка {parent_path} не существует")
                return []
            
            # Получаем список всех папок в указанной директории
            items = self.disk.listdir(parent_path)
            for item in items:
                if item.type == "dir" and query.lower() in item.name.lower():
                    result.append(item)
            
            return result
        except Exception as e:
            logger.error(f"Ошибка при поиске папки: {str(e)}", exc_info=True)
            return []
    
    def create_folder(self, parent_path: str, folder_name: str):
        """Создает новую папку в указанном пути"""
        # Удаляем недопустимые символы из имени папки
        safe_folder_name = re.sub(r'[\\/*?:"<>|]', '', folder_name).strip()
        if not safe_folder_name:
            raise ValueError("Имя папки содержит только недопустимые символы")
        
        folder_path = f"{parent_path}/{safe_folder_name}"
        
        try:
            # Проверяем существование родительской папки
            if not self.disk.exists(parent_path):
                self.ensure_folder_exists(parent_path)
            
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
        retry_count = 0
        max_retries = 3
        retry_delay = 2  # секунды
        
        # Проверяем существование файла перед загрузкой для предотвращения перезаписи
        if not overwrite and self.disk.exists(remote_path):
            # Меняем путь, добавляя дополнительную уникальность через временную метку
            base_path, ext = os.path.splitext(remote_path)
            remote_path = f"{base_path}_{int(time.time()*1000000)}{ext}"
            logger.warning(f"Обнаружен существующий файл, генерируем новое имя: {remote_path}")
        
        while retry_count < max_retries:
            try:
                logger.debug(f"Загрузка файла: {remote_path}")
                
                # Проверяем существование родительской папки
                parent_path = os.path.dirname(remote_path)
                if not self.disk.exists(parent_path):
                    self.ensure_folder_exists(parent_path)
                
                # Определяем размер файла для настройки таймаута
                file_size = os.path.getsize(local_path)
                
                # Устанавливаем таймаут в зависимости от размера файла
                # 1МБ = 1048576 байт
                timeout = 60.0  # увеличенный базовый таймаут в секундах
                
                # Увеличиваем таймаут для больших файлов
                if file_size > 20 * 1048576:  # Более 20МБ
                    timeout = 180.0  # 3 минуты
                elif file_size > 5 * 1048576:  # Более 5МБ
                    timeout = 120.0   # 2 минуты
                
                # Проверяем расширение для видео файлов
                if any(ext in remote_path.lower() for ext in ['.mp4', '.mov', '.avi', '.mkv']):
                    timeout = max(timeout, 300.0)  # минимум 5 минут для видео
                
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
                retry_count += 1
                error_msg = str(e).lower()
                
                if retry_count < max_retries and ("timeout" in error_msg or "connection" in error_msg):
                    logger.warning(f"Попытка {retry_count}/{max_retries}: Ошибка при загрузке файла: {str(e)}. Повторная попытка через {retry_delay} сек.")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Увеличиваем время ожидания для следующей попытки
                else:
                    logger.error(f"Ошибка при загрузке файла после {retry_count} попыток: {str(e)}", exc_info=True)
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
            # Проверяем существование родительской папки
            parent_path = os.path.dirname(path)
            if not self.disk.exists(parent_path):
                self.ensure_folder_exists(parent_path)
                
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
        retry_count = 0
        max_retries = 3
        retry_delay = 2  # секунды
        
        while retry_count < max_retries:
            try:
                existing_content = ""
                
                # Проверяем существование файла
                if self.disk.exists(path):
                    try:
                        # Скачиваем существующий файл
                        tmp_path = self._create_temp_file()
                        self.disk.download(path, tmp_path)
                        
                        # Читаем содержимое
                        with open(tmp_path, 'r', encoding='utf-8') as f:
                            existing_content = f.read()
                        
                        # Удаляем временный файл после чтения
                        os.unlink(tmp_path)
                        tmp_path = None
                    except Exception as e:
                        logger.warning(f"Не удалось прочитать существующий файл: {str(e)}")
                        if tmp_path and os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                            tmp_path = None
                
                # Создаем новый временный файл с объединенным содержимым
                new_content = existing_content
                if new_content and not new_content.endswith("\n"):
                    new_content += "\n"
                new_content += content
                
                tmp_path = self._create_temp_file(new_content)
                
                # В случае ошибки при записи, создаем новый файл с другим именем
                if self.disk.exists(path) and retry_count > 0:
                    # Генерируем новое имя файла с временной меткой
                    dir_path = os.path.dirname(path)
                    base_name = os.path.basename(path)
                    name, ext = os.path.splitext(base_name)
                    timestamp = int(time.time() * 1000000)
                    new_path = f"{dir_path}/{name}_{timestamp}{ext}"
                    logger.warning(f"Создание нового файла вместо обновления: {new_path}")
                    path = new_path
                
                # Загружаем на Яндекс.Диск без перезаписи при первой попытке, с перезаписью при повторе
                overwrite_flag = retry_count > 0
                logger.info(f"Запись в файл {path} (перезапись: {overwrite_flag})")
                self.disk.upload(tmp_path, path, overwrite=overwrite_flag, timeout=60.0)
                
                return True
            except Exception as e:
                retry_count += 1
                error_msg = str(e).lower()
                
                if retry_count < max_retries and ("timeout" in error_msg or "connection" in error_msg or "resource already exists" in error_msg):
                    logger.warning(f"Попытка {retry_count}/{max_retries}: Ошибка при добавлении текста в файл: {str(e)}. Повторная попытка через {retry_delay} сек.")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Увеличиваем время ожидания для следующей попытки
                else:
                    logger.error(f"Ошибка при добавлении текста в файл после {retry_count} попыток: {str(e)}", exc_info=True)
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