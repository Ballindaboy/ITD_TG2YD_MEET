import json
import logging
from config.config import FOLDERS_FILE, USERS_FILE

logger = logging.getLogger(__name__)

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

def add_allowed_folder(folder_path, category):
    """Добавляет папку в список разрешенных"""
    folders = load_allowed_folders()
    
    # Проверяем, есть ли уже такая папка
    for folder in folders:
        if folder['path'] == folder_path and folder['category'] == category:
            return False, "Эта папка уже в списке разрешенных"
    
    # Добавляем новую папку
    folders.append({
        'path': folder_path,
        'category': category
    })
    
    if save_allowed_folders(folders):
        return True, f"Папка {folder_path} добавлена в категорию {category}"
    else:
        return False, "Ошибка при сохранении папок"

def remove_allowed_folder(folder_path, category):
    """Удаляет папку из списка разрешенных"""
    folders = load_allowed_folders()
    
    # Ищем папку для удаления
    found = False
    new_folders = []
    for folder in folders:
        if folder['path'] == folder_path and folder['category'] == category:
            found = True
        else:
            new_folders.append(folder)
    
    if not found:
        return False, "Папка не найдена в списке разрешенных"
    
    if save_allowed_folders(new_folders):
        return True, f"Папка {folder_path} удалена из категории {category}"
    else:
        return False, "Ошибка при сохранении папок"

def list_allowed_folders():
    """Возвращает список разрешенных папок в удобочитаемом формате"""
    folders = load_allowed_folders()
    if not folders:
        return "Список разрешенных папок пуст"
    
    result = "📂 Разрешенные папки:\n\n"
    
    # Группируем папки по категориям
    by_category = {}
    for folder in folders:
        category = folder['category']
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(folder['path'])
    
    # Формируем результат
    for category, paths in by_category.items():
        if category == "suppliers":
            category_name = "Поставщики"
        elif category == "clients":
            category_name = "Клиенты"
        elif category == "offers":
            category_name = "Ценовые предложения"
        else:
            category_name = category
            
        result += f"🔹 {category_name}:\n"
        for path in paths:
            result += f"  - {path}\n"
        result += "\n"
    
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
        username = user.get('username', '')
        first_name = user.get('first_name', '')
        last_name = user.get('last_name', '')
        user_id = user.get('id', '')
        
        name_parts = []
        if first_name:
            name_parts.append(first_name)
        if last_name:
            name_parts.append(last_name)
        full_name = ' '.join(name_parts)
        
        if username:
            result += f"{i}. @{username}"
            if full_name:
                result += f" ({full_name})"
        else:
            result += f"{i}. {full_name or 'Без имени'}"
        
        result += f" [ID: {user_id}]\n"
    
    return result

def is_user_allowed(user_id):
    """Проверяет, разрешен ли доступ пользователю"""
    users = load_allowed_users()
    return any(user['id'] == user_id for user in users)

def get_timestamp():
    """Возвращает текущий timestamp"""
    from datetime import datetime
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") 