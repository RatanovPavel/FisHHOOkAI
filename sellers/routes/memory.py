import os
import json
import hashlib
from datetime import datetime
from fastapi import APIRouter, Body
from cryptography.fernet import Fernet

router = APIRouter(prefix="/api/memory", tags=["memory"])

KEY_PATH = "/app/.memory_key"
MEMORY_DIR = "/app/user_memory"

def get_cipher() -> Fernet:
    with open(KEY_PATH, "rb") as f:
        return Fernet(f.read().strip())

def get_memory_path(user_id: str, character_key: str) -> str:
    user_hash = hashlib.sha256(user_id.strip().lower().encode("utf-8")).hexdigest()[:24]
    safe_char = "".join(c for c in character_key if c.isalnum() or c in "_-")
    user_dir = os.path.join(MEMORY_DIR, user_hash)
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, f"{safe_char}.enc")

def default_memory() -> dict:
    return {
        "user_name": "",
        "facts": [],
        "state": {},
        "gifts": [],
        "history": []
    }

def read_memory(user_id: str, character_key: str) -> dict:
    path = get_memory_path(user_id, character_key)
    if not os.path.exists(path):
        return default_memory()
    try:
        cipher = get_cipher()
        with open(path, "rb") as f:
            decrypted = cipher.decrypt(f.read())
        data = json.loads(decrypted.decode("utf-8"))
        base = default_memory()
        base.update(data)
        return base
    except Exception:
        return default_memory()

def write_memory(user_id: str, character_key: str, data: dict):
    path = get_memory_path(user_id, character_key)
    cipher = get_cipher()
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    encrypted = cipher.encrypt(raw)
    with open(path, "wb") as f:
        f.write(encrypted)

@router.get("/{user_id}/{character_key}")
async def api_get_memory(user_id: str, character_key: str):
    return {"status": "ok", "memory": read_memory(user_id, character_key)}

@router.post("/{user_id}/{character_key}")
async def api_save_memory(user_id: str, character_key: str, payload: dict = Body(...)):
    mem = read_memory(user_id, character_key)
    for k in ["user_name", "facts", "state", "gifts", "history"]:
        if k in payload:
            mem[k] = payload[k]
    mem["history"] = mem["history"][-20:]
    mem["facts"] = mem["facts"][-15:]
    write_memory(user_id, character_key, mem)
    return {"status": "ok"}

@router.post("/{user_id}/{character_key}/gift")
async def api_give_gift(user_id: str, character_key: str, payload: dict = Body(...)):
    mem = read_memory(user_id, character_key)
    gift_name = str(payload.get("name", "Подарок")).strip()
    mood_boost = int(payload.get("mood", 15))
    trust_boost = int(payload.get("trust", 10))
    intimacy_boost = int(payload.get("intimacy", 10))

    state = mem.get("state", {})
    state["mood"] = min(100, state.get("mood", 50) + mood_boost)
    state["trust"] = min(100, state.get("trust", 30) + trust_boost)
    state["intimacy"] = min(100, state.get("intimacy", 20) + intimacy_boost)
    mem["state"] = state

    gifts = mem.get("gifts", [])
    gifts.append({"name": gift_name, "date": datetime.now().strftime("%d.%m.%Y")})
    mem["gifts"] = gifts[-20:]
    write_memory(user_id, character_key, mem)
    return {"status": "ok", "memory": mem}
