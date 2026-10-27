import os
import uuid
import json
import shutil
from config import UPLOAD_DIR

import os
import json
import uuid
import time
import shutil
from config import UPLOAD_DIR

class SessionManager:
    @staticmethod
    def create_session():
        """Создает уникальный ID и папку для новой сессии"""
        session_id = str(uuid.uuid4())
        session_path = os.path.join(UPLOAD_DIR, session_id)
        
        # Создаем структуру внутри сессии
        os.makedirs(session_path, exist_ok=True)
        
        return session_id, session_path

    @staticmethod
    def get_session_path(session_id):
        """Возвращает путь к папке сессии по её ID"""
        return os.path.join(UPLOAD_DIR, session_id)

    @staticmethod
    def save_meta(session_id, data, filename="meta.json"):
        """Сохраняет JSON с координатами лица и другими данными"""
        path = os.path.join(SessionManager.get_session_path(session_id), filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def clean_old_sessions(max_age_hours=24):
        """Удаляет папки сессий, которые старше заданного времени"""
        now = time.time()
        max_age_seconds = max_age_hours * 3600
        deleted_count = 0
        
        if not os.path.exists(UPLOAD_DIR):
            return 0

        for session_id in os.listdir(UPLOAD_DIR):
            session_path = os.path.join(UPLOAD_DIR, session_id)
            
            # Проверяем возраст папки
            if os.path.isdir(session_path):
                # getmtime — время последнего изменения
                folder_age = now - os.path.getmtime(session_path)
                
                if folder_age > max_age_seconds:
                    try:
                        shutil.rmtree(session_path)
                        deleted_count += 1
                    except Exception as e:
                        print(f"❌ [CLEANER]: Ошибка при удалении {session_id}: {e}")
        
        if deleted_count > 0:
            print(f"🧹 [CLEANER]: Удалено {deleted_count} старых сессий.")
        return deleted_count
