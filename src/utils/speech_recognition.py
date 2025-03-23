import os
import logging
import speech_recognition as sr
from pydub import AudioSegment
import tempfile
from config.config import LOG_LEVEL

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

def transcribe_audio(audio_path):
    """
    Преобразует аудиофайл в текст, используя Google Speech Recognition
    
    Args:
        audio_path (str): Путь к аудиофайлу (ogg формат)
        
    Returns:
        str: Распознанный текст или пустая строка в случае ошибки
    """
    try:
        # Конвертирование ogg в wav формат, который понимает speech_recognition
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
            wav_path = temp_wav.name
        
        # Конвертируем из ogg в wav
        logger.debug(f"Конвертирование {audio_path} в WAV формат")
        sound = AudioSegment.from_ogg(audio_path)
        sound.export(wav_path, format="wav")
        
        # Создаем распознаватель
        recognizer = sr.Recognizer()
        
        # Открываем аудиофайл
        with sr.AudioFile(wav_path) as source:
            # Читаем аудиоданные
            audio_data = recognizer.record(source)
            
            # Распознаем речь
            logger.debug("Отправка аудио в Google Speech Recognition")
            text = recognizer.recognize_google(audio_data, language="ru-RU")
            logger.info(f"Текст успешно распознан: {text[:30]}...")
            
            # Удаляем временный файл
            os.unlink(wav_path)
            
            return text
    
    except sr.UnknownValueError:
        logger.warning("Google Speech Recognition не смог распознать аудио")
        return ""
    except sr.RequestError as e:
        logger.error(f"Ошибка при обращении к сервису Google Speech Recognition: {e}")
        return ""
    except Exception as e:
        logger.error(f"Ошибка при распознавании речи: {e}", exc_info=True)
        return ""
    finally:
        # Удаляем временный файл, если он существует
        if 'wav_path' in locals() and os.path.exists(wav_path):
            try:
                os.unlink(wav_path)
            except Exception as e:
                logger.error(f"Не удалось удалить временный файл {wav_path}: {e}") 