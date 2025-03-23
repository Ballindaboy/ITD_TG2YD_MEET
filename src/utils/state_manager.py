import logging
from typing import Dict, Any, Optional
from config.config import get_current_timestamp

logger = logging.getLogger(__name__)

class SessionState:
    """Класс для хранения данных о текущей сессии встречи"""
    def __init__(self, category: str, folder_path: str, folder_name: str):
        self.category = category
        self.folder_path = folder_path
        self.folder_name = folder_name
        self.timestamp = get_current_timestamp()
        self.txt_file_path = f"{folder_path}/{self.timestamp}_visit_{folder_name}.txt"
        self.file_prefix = f"{self.timestamp}_Files_{folder_name}"
    
    def get_txt_filename(self) -> str:
        """Возвращает имя текстового файла"""
        return f"{self.timestamp}_visit_{self.folder_name}.txt"
    
    def get_media_prefix(self) -> str:
        """Возвращает префикс для медиафайлов"""
        return f"{self.timestamp}_Files_{self.folder_name}"
    
    def get_media_path(self, extension: str) -> str:
        """Возвращает путь для медиафайла с указанным расширением"""
        return f"{self.folder_path}/{self.file_prefix}.{extension}"

class StateManager:
    """Класс для управления состояниями пользователей"""
    def __init__(self):
        # Ключ: user_id, Значение: текущая сессия
        self.sessions: Dict[int, SessionState] = {}
        # Ключ: user_id, Значение: текущее состояние в диалоге
        self.states: Dict[int, str] = {}
        # Ключ: user_id, Значение: временные данные
        self.data: Dict[int, Dict[str, Any]] = {}
    
    def set_state(self, user_id: int, state: str) -> None:
        """Устанавливает состояние для пользователя"""
        self.states[user_id] = state
        logger.debug(f"Установлено состояние {state} для пользователя {user_id}")
    
    def get_state(self, user_id: int) -> Optional[str]:
        """Возвращает текущее состояние пользователя"""
        return self.states.get(user_id)
    
    def reset_state(self, user_id: int) -> None:
        """Сбрасывает состояние пользователя"""
        if user_id in self.states:
            del self.states[user_id]
    
    def set_session(self, user_id: int, session: SessionState) -> None:
        """Устанавливает сессию для пользователя"""
        self.sessions[user_id] = session
        logger.info(f"Установлена сессия для пользователя {user_id}: {session.folder_path}")
    
    def get_session(self, user_id: int) -> Optional[SessionState]:
        """Возвращает текущую сессию пользователя"""
        return self.sessions.get(user_id)
    
    def clear_session(self, user_id: int) -> None:
        """Удаляет сессию пользователя"""
        if user_id in self.sessions:
            del self.sessions[user_id]
            logger.info(f"Сессия пользователя {user_id} завершена")
    
    def set_data(self, user_id: int, key: str, value: Any) -> None:
        """Сохраняет временные данные для пользователя"""
        if user_id not in self.data:
            self.data[user_id] = {}
        self.data[user_id][key] = value
    
    def get_data(self, user_id: int, key: str) -> Any:
        """Возвращает временные данные пользователя"""
        return self.data.get(user_id, {}).get(key)
    
    def clear_data(self, user_id: int) -> None:
        """Удаляет все временные данные пользователя"""
        if user_id in self.data:
            del self.data[user_id]

# Создаем глобальный экземпляр менеджера состояний
state_manager = StateManager() 