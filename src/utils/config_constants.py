"""
Модуль с константами для конфигурации приложения.
Содержит тексты сообщений и другие настройки.
"""

# Настройки для навигации по папкам
MAX_FOLDERS_PER_MESSAGE = 20  # Максимальное количество папок для отображения в одном сообщении

# Кнопки для навигации по папкам
BUTTON_BACK = "🔙 Назад"
BUTTON_CANCEL = "❌ Отмена"
BUTTON_ADD_FOLDER = "✅ Добавить эту папку"
BUTTON_CREATE_FOLDER = "📁 Создать новую папку"
BUTTON_RETURN_TO_ROOT = "🔙 К выбору папок"

# Сообщения для административного интерфейса
ADMIN_WELCOME_MESSAGE = """
👨‍💼 Административное меню

Выберите действие:
""".strip()

FOLDER_ADDED_SUCCESS = "✅ Папка успешно добавлена в список разрешенных."
FOLDER_ADDED_EXISTS = "❌ Папка уже есть в списке разрешенных."
FOLDER_REMOVED_SUCCESS = "✅ Папка успешно удалена из списка разрешенных."
FOLDER_REMOVED_NOT_FOUND = "❌ Папка не найдена в списке разрешенных."
FOLDER_EMPTY_LIST = "❌ Список разрешенных папок пуст."

USER_ADDED_SUCCESS = "✅ Пользователь успешно добавлен в список разрешенных."
USER_ADDED_EXISTS = "❌ Пользователь уже есть в списке разрешенных."
USER_REMOVED_SUCCESS = "✅ Пользователь успешно удален из списка разрешенных."
USER_REMOVED_NOT_FOUND = "❌ Пользователь не найден в списке разрешенных."
USER_EMPTY_LIST = "❌ Список разрешенных пользователей пуст."

# Сообщения для навигации по папкам
FOLDER_LIST_TITLE = "📂 Выберите папку:"
FOLDER_SUBFOLDERS_TITLE = "📂 Подпапки в '{path}':"
FOLDER_NO_SUBFOLDERS = "📂 Директория '{path}' не содержит подпапок."
FOLDER_SELECTION_ERROR = "❌ Пожалуйста, выберите папку из предложенного списка"
FOLDER_INVALID_NUMBER = "❌ Неверный номер папки"
FOLDER_CREATION_PROMPT = "📁 Введите название новой папки в директории '{path}':"
FOLDER_CREATION_SUCCESS = "✅ Папка '{name}' успешно создана в '{path}'."
FOLDER_CREATION_ERROR = "❌ Произошла ошибка при создании папки: {error}"
FOLDER_EXISTS_ERROR = "❌ Папка '{name}' уже существует"
FOLDER_EMPTY_NAME_ERROR = "❌ Название папки не может быть пустым"

# Сообщения для прав доступа
FOLDER_PERMISSIONS_PROMPT = """
Хотите добавить пользователей с доступом к этой папке?
""".strip()

FOLDER_PERMISSIONS_TITLE = """
Управление правами доступа к папке '{path}'

{status}

Нажимайте на пользователей для выбора/отмены выбора.
Если не выбран ни один пользователь, папка будет доступна всем.
""".strip()

FOLDER_PERMISSIONS_STATUS_RESTRICTED = "✅ В данный момент папка доступна только выбранным пользователям"
FOLDER_PERMISSIONS_STATUS_ALL = "⚠️ В данный момент папка доступна всем пользователям"
FOLDER_PERMISSIONS_UPDATED = "✅ Права доступа к папке '{path}' обновлены."
FOLDER_PERMISSIONS_ERROR = "❌ Произошла ошибка при обновлении прав доступа: {error}"
FOLDER_PERMISSIONS_USER_ADDED = "✅ Пользователь добавлен в список доступа"
FOLDER_PERMISSIONS_USER_REMOVED = "❌ Пользователь удален из списка доступа" 