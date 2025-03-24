import json
import logging
from config.config import DATA_DIR, FOLDERS_FILE, USERS_FILE
import os
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from datetime import datetime

logger = logging.getLogger(__name__)

# Пути к файлам данных
ALLOWED_FOLDERS_FILE = os.path.join(DATA_DIR, 'allowed_folders.json')
ALLOWED_USERS_FILE = os.path.join(DATA_DIR, 'allowed_users.json')

# Кеш данных для минимизации обращений к файловой системе
_allowed_folders_cache = None
_allowed_users_cache = None

def ensure_data_dir_exists():
    """Проверяет существование директории для данных и создает ее при необходимости."""
    os.makedirs(DATA_DIR, exist_ok=True)

def load_allowed_folders():
    """Загружает список разрешенных папок из файла"""
    try:
        with open(FOLDERS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка при загрузке разрешенных папок: {str(e)}")
        return []

def save_allowed_folders(folders):
    """Сохраняет список разрешенных папок в файл"""
    try:
        with open(FOLDERS_FILE, 'w') as f:
            json.dump(folders, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении разрешенных папок: {str(e)}")
        return False

def add_allowed_folder(folder_path, user_ids=None):
    """Добавляет папку в список разрешенных
    
    Args:
        folder_path: Путь к папке
        user_ids: Список ID пользователей, которым разрешен доступ (если None - всем)
    """
    folders = load_allowed_folders()
    
    # Проверяем, есть ли уже такая папка
    for folder in folders:
        if folder['path'] == folder_path:
            # Если папка существует, обновляем список пользователей
            if user_ids is not None:
                folder['allowed_users'] = user_ids
                if save_allowed_folders(folders):
                    return True, f"Обновлены права доступа для папки {folder_path}"
                else:
                    return False, "Ошибка при сохранении папок"
            return False, "Эта папка уже в списке разрешенных"
    
    # Добавляем новую папку
    new_folder = {
        'path': folder_path,
        'allowed_users': user_ids if user_ids is not None else []
    }
    
    folders.append(new_folder)
    
    if save_allowed_folders(folders):
        return True, f"Папка {folder_path} добавлена в список разрешенных"
    else:
        return False, "Ошибка при сохранении папок"

def remove_allowed_folder(folder_path):
    """Удаляет папку из списка разрешенных"""
    folders = load_allowed_folders()
    
    # Ищем папку для удаления
    found = False
    new_folders = []
    for folder in folders:
        if folder['path'] == folder_path:
            found = True
        else:
            new_folders.append(folder)
    
    if not found:
        return False, "Папка не найдена в списке разрешенных"
    
    if save_allowed_folders(new_folders):
        return True, f"Папка {folder_path} удалена из списка разрешенных"
    else:
        return False, "Ошибка при сохранении папок"

def update_folder_permissions(folder_path, user_ids):
    """Обновляет права доступа к папке для указанных пользователей"""
    folders = load_allowed_folders()
    
    # Ищем папку для обновления
    found = False
    for folder in folders:
        if folder['path'] == folder_path:
            folder['allowed_users'] = user_ids
            found = True
            break
    
    if not found:
        return False, "Папка не найдена в списке разрешенных"
    
    if save_allowed_folders(folders):
        return True, f"Права доступа к папке {folder_path} обновлены"
    else:
        return False, "Ошибка при сохранении папок"

def add_user_to_folder(folder_path, user_id):
    """Добавляет пользователя к списку разрешенных для папки"""
    folders = load_allowed_folders()
    
    # Ищем папку
    found = False
    for folder in folders:
        if folder['path'] == folder_path:
            if user_id not in folder['allowed_users']:
                folder['allowed_users'].append(user_id)
            found = True
            break
    
    if not found:
        return False, "Папка не найдена в списке разрешенных"
    
    if save_allowed_folders(folders):
        return True, f"Пользователь добавлен к папке {folder_path}"
    else:
        return False, "Ошибка при сохранении папок"

def remove_user_from_folder(folder_path, user_id):
    """Удаляет пользователя из списка разрешенных для папки"""
    folders = load_allowed_folders()
    
    # Ищем папку
    found = False
    for folder in folders:
        if folder['path'] == folder_path:
            if user_id in folder['allowed_users']:
                folder['allowed_users'].remove(user_id)
            found = True
            break
    
    if not found:
        return False, "Папка не найдена в списке разрешенных"
    
    if save_allowed_folders(folders):
        return True, f"Пользователь удален из папки {folder_path}"
    else:
        return False, "Ошибка при сохранении папок"

def get_allowed_folders_for_user(user_id):
    """Возвращает список папок, доступных пользователю"""
    folders = load_allowed_folders()
    result = []
    
    for folder in folders:
        # Если список allowed_users пуст, то папка доступна всем
        # Или если пользователь в списке allowed_users
        if not folder['allowed_users'] or user_id in folder['allowed_users']:
            result.append(folder['path'])
    
    return result

def list_allowed_folders():
    """Возвращает список разрешенных папок в удобочитаемом формате"""
    folders = load_allowed_folders()
    if not folders:
        return "Список разрешенных папок пуст"
    
    result = "📂 Разрешенные папки:\n\n"
    
    for i, folder in enumerate(folders, 1):
        result += f"{i}. {folder['path']}\n"
        
        if folder['allowed_users']:
            # Получаем имена пользователей
            users = load_allowed_users()
            user_map = {user['id']: get_user_display_name(user) for user in users}
            
            allowed_users = []
            for user_id in folder['allowed_users']:
                allowed_users.append(user_map.get(user_id, f"ID: {user_id}"))
            
            result += f"   👥 Доступ: {', '.join(allowed_users)}\n"
        else:
            result += f"   👥 Доступ: Все пользователи\n"
    
    return result

def load_allowed_users():
    """Загружает список разрешенных пользователей из файла"""
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка при загрузке разрешенных пользователей: {str(e)}")
        return []

def save_allowed_users(users):
    """Сохраняет список разрешенных пользователей в файл"""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении разрешенных пользователей: {str(e)}")
        return False

def add_allowed_user(user_id, username=None, first_name=None, last_name=None):
    """Добавляет пользователя в список разрешенных"""
    users = load_allowed_users()
    
    # Проверяем, есть ли уже такой пользователь
    for user in users:
        if user['id'] == user_id:
            return False, "Этот пользователь уже в списке разрешенных"
    
    # Добавляем нового пользователя
    user_data = {
        'id': user_id,
        'username': username,
        'first_name': first_name,
        'last_name': last_name,
        'added_at': get_timestamp()
    }
    
    users.append(user_data)
    
    if save_allowed_users(users):
        name = username or first_name or f"ID: {user_id}"
        return True, f"Пользователь {name} добавлен в список разрешенных"
    else:
        return False, "Ошибка при сохранении пользователей"

def remove_allowed_user(user_id):
    """Удаляет пользователя из списка разрешенных"""
    users = load_allowed_users()
    
    # Ищем пользователя для удаления
    found = False
    user_name = None
    new_users = []
    for user in users:
        if user['id'] == user_id:
            found = True
            user_name = user.get('username') or user.get('first_name') or f"ID: {user_id}"
        else:
            new_users.append(user)
    
    if not found:
        return False, "Пользователь не найден в списке разрешенных"
    
    # Также удаляем пользователя из всех папок
    folders = load_allowed_folders()
    for folder in folders:
        if user_id in folder['allowed_users']:
            folder['allowed_users'].remove(user_id)
    save_allowed_folders(folders)
    
    if save_allowed_users(new_users):
        return True, f"Пользователь {user_name} удален из списка разрешенных"
    else:
        return False, "Ошибка при сохранении пользователей"

def list_allowed_users():
    """Возвращает список разрешенных пользователей в удобочитаемом формате"""
    users = load_allowed_users()
    if not users:
        return "Список разрешенных пользователей пуст"
    
    result = "👥 Разрешенные пользователи:\n\n"
    
    for i, user in enumerate(users, 1):
        display_name = get_user_display_name(user)
        result += f"{i}. {display_name} [ID: {user['id']}]\n"
    
    return result

def get_user_display_name(user):
    """Возвращает отображаемое имя пользователя"""
    username = user.get('username', '')
    first_name = user.get('first_name', '')
    last_name = user.get('last_name', '')
    
    name_parts = []
    if first_name:
        name_parts.append(first_name)
    if last_name:
        name_parts.append(last_name)
    full_name = ' '.join(name_parts)
    
    if username:
        if full_name:
            return f"@{username} ({full_name})"
        return f"@{username}"
    else:
        return full_name or 'Без имени'

def is_user_allowed(user_id):
    """Проверяет, разрешен ли доступ пользователю"""
    users = load_allowed_users()
    return any(user['id'] == user_id for user in users)

def is_folder_allowed_for_user(folder_path, user_id):
    """Проверяет, разрешена ли папка для пользователя"""
    folders = load_allowed_folders()
    
    for folder in folders:
        if folder['path'] == folder_path:
            # Если список allowed_users пуст, папка доступна всем
            # Или если пользователь в списке allowed_users
            return not folder['allowed_users'] or user_id in folder['allowed_users']
    
    # Если папка не найдена в списке разрешенных, она недоступна
    return False

def get_timestamp():
    """Возвращает текущий timestamp"""
    from datetime import datetime
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def get_user_data(user_id: int) -> Dict[str, Any]:
    """
    Получает данные пользователя по его ID.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Словарь с данными пользователя или пустой словарь, если пользователь не найден
    """
    users = load_allowed_users()
    
    # Преобразуем ID пользователя в строку, так как ключи в JSON - строки
    user_id_str = str(user_id)
    
    if user_id_str in users:
        user_data = users[user_id_str].copy()
        user_data['id'] = user_id  # Добавляем ID в данные
        return user_data
    
    return {'id': user_id, 'username': None, 'first_name': None, 'last_name': None, 'is_admin': False} 