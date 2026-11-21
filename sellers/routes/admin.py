import os
import sys
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

# Подключаем корень проекта для импортов
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from core.models import User, EffectStats
from core.session_manager import SessionManager
from config import STATIC_DIR

# Префикс /skulla-admin означает, что все пути в файле будут начинаться с него
router = APIRouter(prefix="/skulla-admin", tags=["Admin Panel"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def get_storage_mb(path='uploads'):
    """Считает реальный вес папок с картинками"""
    total = 0
    if not os.path.exists(path): return 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            total += os.path.getsize(os.path.join(dirpath, f))
    return round(total / (1024 * 1024), 2)

# --- ГЛАВНЫЙ ЭКРАН ТЕРМИНАЛА ---
@router.get("/", response_class=HTMLResponse)
async def admin_panel(db: Session = Depends(get_db)):
    # Собираем статистику из БД и системы
    users_count = db.query(User).count()
    all_stats = db.query(EffectStats).all()
    total_gens = sum([s.usage_count for s in all_stats])
    active_sessions = len(os.listdir('uploads')) if os.path.exists('uploads') else 0
    storage_mb = get_storage_mb()

    try:
        with open(os.path.join(STATIC_DIR, "admin.html"), "r", encoding="utf-8") as f:
            content = f.read()
            # Инъекция данных в HTML-шаблон
            replacements = {
                "{{active_sessions}}": active_sessions,
                "{{total_results}}": total_gens,
                "{{storage_mb}}": storage_mb,
                "{{total_users}}": users_count
            }
            for key, val in replacements.items():
                content = content.replace(key, str(val))
            return content
    except FileNotFoundError:
        return HTMLResponse("<h1>404: admin.html не найден в папке static/</h1>", status_code=404)

# --- API ОЧИСТКИ (PURGE PROTOCOL) ---
@router.post("/api/clean")
async def api_clean_sessions():
    """Удаляет папки сессий старше 24 часов"""
    try:
        deleted_count = SessionManager.clean_old_sessions(max_age_hours=24)
        print(f"🧹 [ADMIN]: Протокол очистки завершен. Удалено: {deleted_count}")
        return {"status": "success", "deleted": deleted_count}
    except Exception as e:
        print(f"❌ [ADMIN_ERROR]: Ошибка ядра при очистке: {e}")
        return {"status": "error", "message": str(e)}

# --- СТАТИСТИКА ПО ЭФФЕКТАМ (JSON) ---
@router.get("/api/top-effects")
async def get_top_effects(db: Session = Depends(get_db)):
    stats = db.query(EffectStats).order_by(EffectStats.usage_count.desc()).all()
    return [{"style": s.style_id, "usage": s.usage_count} for s in stats]
