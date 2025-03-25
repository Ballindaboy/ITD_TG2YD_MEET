import logging
from typing import Dict, Any, Optional
from enum import IntEnum

logger = logging.getLogger(__name__)

class SessionState(IntEnum):
    """
    Перечисление для возможных состояний сессии
    """
    INACTIVE = 0
    ACTIVE = 1
    WAITING_FOR_COMMENT = 2
    COMPLETED = 3

class StateManager:
    """
    Управляет состоянием пользователей бота:
    - хранит данные пользователей
    - хранит информацию о текущих сессиях
    """
    def __init__(self):
        self.sessions = {}  # Хранит текущие активные сессии пользователей
        self.data = {}      # Хранит временные данные пользователей
    
    def create_session(self, user_id: int, session_data: dict) -> None:
        """
        Создает новую сессию для пользователя
        """
        self.sessions[user_id] = session_data
        logger.info(f"Создана сессия для пользователя {user_id}: {session_data.get('folder_path', 'Неизвестно')}")
    
    def get_session(self, user_id: int) -> dict:
        """
        Возвращает текущую сессию пользователя
        """
        return self.sessions.get(user_id)
    
    def clear_session(self, user_id: int) -> None:
        """
        Удаляет сессию пользователя
        """
        if user_id in self.sessions:
            del self.sessions[user_id]
            logger.info(f"Сессия пользователя {user_id} завершена")
    
    def set_data(self, user_id: int, key: str, value) -> None:
        """
        Сохраняет данные пользователя по ключу
        """
        if user_id not in self.data:
            self.data[user_id] = {}
        self.data[user_id][key] = value
        logger.debug(f"Установлены данные {key} для пользователя {user_id}")
    
    def get_data(self, user_id: int, key: str, default=None):
        """
        Получает данные пользователя по ключу
        """
        return self.data.get(user_id, {}).get(key, default)
    
    def clear_data(self, user_id: int) -> None:
        """
        Удаляет все данные пользователя
        """
        if user_id in self.data:
            del self.data[user_id]
            logger.debug(f"Удалены все данные пользователя {user_id}")
    
    # Добавляем алиасы методов для совместимости
    def set_user_data(self, user_id: int, key: str, value) -> None:
        """
        Алиас для set_data для совместимости
        """
        return self.set_data(user_id, key, value)
    
    def get_user_data(self, user_id: int, key: str, default=None):
        """
        Алиас для get_data для совместимости
        """
        return self.get_data(user_id, key, default)
    
    def clear_user_data(self, user_id: int) -> None:
        """
        Алиас для clear_data для совместимости
        """
        return self.clear_data(user_id)

# Создаем глобальный экземпляр менеджера состояний
state_manager = StateManager() 