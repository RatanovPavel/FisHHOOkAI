import os
import sys
import json
import random
import time
import shutil
import subprocess
import traceback
from pathlib import Path

# ============================================================================
# 📝 СИСТЕМА ЛОГИРОВАНИЯ
# ============================================================================

def log(message, level="INFO"):
    """Выводит сообщение с временной меткой"""
    timestamp = time.strftime("%H:%M:%S")
    colors = {
        "INFO": "📝",
        "SUCCESS": "✅",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "STEP": "🚀"
    }
    icon = colors.get(level, "📝")
    print(f"[{timestamp}] {icon} {message}")
    sys.stdout.flush()  # Принудительный вывод

def log_step(step_num, message):
    """Выводит сообщение о шаге"""
    log(f"[ШАГ {step_num}] {message}", "STEP")

# ============================================================================
# 📥 АВТОЗАГРУЗКА ГОЛОСОВ С GITHUB
# ============================================================================

GITHUB_REPO = "https://github.com/RatanovPavel/FisHHOOkAI.git"
VOICES_DIR = "./voices"
CHARACTERS_DIR = "./characters"

def download_voices_from_github():
    """Скачивает папку voices/ с GitHub если её нет локально"""
    
    log_step(1, "Проверка голосовых файлов")
    
    if os.path.exists(VOICES_DIR):
        voice_count = 0
        for root, dirs, files in os.walk(VOICES_DIR):
            for file in files:
                if file.lower().endswith(('.wav', '.mp3', '.ogg')):
                    voice_count += 1
        
        if voice_count > 0:
            log(f"Папка voices/ уже существует ({voice_count} файлов)", "SUCCESS")
            return True
        else:
            log(f"Папка voices/ пуста, скачиваю с GitHub...", "WARNING")
            shutil.rmtree(VOICES_DIR)
    
    log(f"Скачиваю голоса с GitHub: {GITHUB_REPO}")
    
    # Метод 1: Git sparse checkout
    try:
        log("Метод 1: Git sparse checkout...")
        temp_dir = "./temp_repo"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        subprocess.run(["git", "init", temp_dir], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", temp_dir, "remote", "add", "origin", GITHUB_REPO],
            check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", temp_dir, "config", "core.sparseCheckout", "true"],
            check=True, capture_output=True
        )
        
        sparse_checkout_file = os.path.join(temp_dir, ".git", "info", "sparse-checkout")
        with open(sparse_checkout_file, "w") as f:
            f.write("voices/\n")
        
        subprocess.run(
            ["git", "-C", temp_dir, "pull", "--depth=1", "origin", "main"],
            check=True, capture_output=True
        )
        
        if os.path.exists(os.path.join(temp_dir, "voices")):
            shutil.move(os.path.join(temp_dir, "voices"), VOICES_DIR)
            log("Голоса успешно скачаны (метод 1)", "SUCCESS")
        
        shutil.rmtree(temp_dir)
        return True
        
    except Exception as e:
        log(f"Метод 1 не сработал: {e}", "WARNING")
    
    # Метод 2: Git clone
    try:
        log("Метод 2: Git clone...")
        subprocess.run(
            ["git", "clone", "--depth=1", GITHUB_REPO, "temp_repo_full"],
            check=True, capture_output=True
        )
        
        if os.path.exists("./temp_repo_full/voices"):
            shutil.move("./temp_repo_full/voices", VOICES_DIR)
            log("Голоса успешно скачаны (метод 2)", "SUCCESS")
        
        shutil.rmtree("./temp_repo_full")
        return True
        
    except Exception as e:
        log(f"Метод 2 не сработал: {e}", "WARNING")
    
    # Метод 3: wget + unzip
    try:
        log("Метод 3: wget + unzip...")
        zip_url = "https://github.com/RatanovPavel/FisHHOOkAI/archive/refs/heads/main.zip"
        subprocess.run(
            ["wget", "-q", "-O", "repo.zip", zip_url],
            check=True, capture_output=True
        )
        subprocess.run(["unzip", "-q", "repo.zip"], check=True, capture_output=True)
        
        if os.path.exists("./FisHHOOkAI-main/voices"):
            shutil.move("./FisHHOOkAI-main/voices", VOICES_DIR)
            log("Голоса успешно скачаны (метод 3)", "SUCCESS")
        
        os.remove("repo.zip")
        shutil.rmtree("./FisHHOOkAI-main")
        return True
        
    except Exception as e:
        log(f"Метод 3 не сработал: {e}", "ERROR")
    
    return False

# ============================================================================
# 📦 УСТАНОВКА ЗАВИСИМОСТЕЙ
# ============================================================================

def install_dependencies():
    """Устанавливает все необходимые пакеты с подробным логированием"""
    
    log_step(2, "Установка зависимостей")
    
    packages = [
        "transformers", "accelerate", "bitsandbytes", "diffusers",
        "coqui-tts", "torch", "torchaudio", "Pillow"
    ]
    
    for pkg in packages:
        try:
            __import__(pkg.replace("-", "_"))
            log(f"{pkg} уже установлен", "SUCCESS")
        except ImportError:
            log(f"Устанавливаю {pkg}...")
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-q", pkg],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode == 0:
                    log(f"{pkg} установлен", "SUCCESS")
                else:
                    log(f"Ошибка установки {pkg}: {result.stderr}", "ERROR")
            except Exception as e:
                log(f"Критическая ошибка установки {pkg}: {e}", "ERROR")

def check_gpu():
    """Проверяет доступность GPU"""
    
    log_step(3, "Проверка GPU")
    
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            log(f"GPU: {gpu_name} | VRAM: {vram:.1f} GB", "SUCCESS")
            return True
        else:
            log("GPU не обнаружен! Скрипт требует CUDA.", "ERROR")
            log("Проверьте настройки Colab: Runtime → Change runtime type → GPU", "ERROR")
            return False
    except Exception as e:
        log(f"Ошибка проверки GPU: {e}", "ERROR")
        return False

# ============================================================================
# 🎤 СИСТЕМА ГОЛОСОВ
# ============================================================================

def scan_voice_folders():
    """Сканирует папки с голосами с подробным логированием"""
    
    log_step(4, "Сканирование папок с голосами")
    
    voices = {
        "female_young": [],
        "female_middle": [],
        "female_old": [],
        "male": []
    }
    
    # Проверяем структуру папок
    log(f"Папка voices/: {os.path.abspath(VOICES_DIR)}")
    
    if not os.path.exists(VOICES_DIR):
        log(f"Папка {VOICES_DIR} не существует!", "ERROR")
        return voices
    
    # Женские голоса по возрастам
    for age_group in ["young", "middle", "old"]:
        folder = os.path.join(VOICES_DIR, "female", age_group)
        log(f"Проверяю папку: {folder}")
        
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.lower().endswith(('.wav', '.mp3', '.ogg')):
                    voices[f"female_{age_group}"].append(os.path.join(folder, file))
            log(f"  Найдено {len(voices[f'female_{age_group}'])} файлов", "SUCCESS")
        else:
            log(f"  Папка не найдена", "WARNING")
    
    # Мужские голоса
    folder = os.path.join(VOICES_DIR, "male")
    log(f"Проверяю папку: {folder}")
    
    if os.path.exists(folder):
        for file in os.listdir(folder):
            if file.lower().endswith(('.wav', '.mp3', '.ogg')):
                voices["male"].append(os.path.join(folder, file))
        log(f"  Найдено {len(voices['male'])} файлов", "SUCCESS")
    else:
        log(f"  Папка не найдена", "WARNING")
    
    # Выводим статистику
    log("Статистика голосов:")
    for key, files in voices.items():
        log(f"  {key}: {len(files)} файлов")
    
    # Проверка
    total_voices = sum(len(files) for files in voices.values())
    if total_voices == 0:
        log("Не найдено ни одного голоса!", "ERROR")
        log("Проверьте структуру папки voices/", "ERROR")
    
    return voices

def select_voice(voices, gender, age):
    """Выбирает случайный голос из соответствующей папки"""
    if gender == "female":
        if age <= 30:
            voice_list = voices["female_young"]
        elif age <= 45:
            voice_list = voices["female_middle"]
        else:
            voice_list = voices["female_old"]
    else:
        voice_list = voices["male"]
    
    if not voice_list:
        log(f"Нет голосов для {gender} {age} лет, использую любой доступный", "WARNING")
        all_voices = voices["female_young"] + voices["female_middle"] + voices["female_old"] + voices["male"]
        if all_voices:
            return random.choice(all_voices)
        return None
    
    return random.choice(voice_list)

def copy_voice_to_character(source_voice, character_dir):
    """Копирует голос в папку персонажа"""
    dest_voice = os.path.join(character_dir, "voice.wav")
    shutil.copy2(source_voice, dest_voice)
    return dest_voice

# ============================================================================
# 🎨 БАЗА ДАННЫХ ПЕРСОНАЖЕЙ
# ============================================================================

NUM_REALISTIC_FEMALE = 50
NUM_REALISTIC_MALE = 20
NUM_ANIME = 30

AGE_GROUPS = {
    "young": (18, 30),
    "middle": (30, 45),
    "old": (45, 60)
}

FEMALE_AGE_DISTRIBUTION = {
    "young": 20,
    "middle": 15,
    "old": 15
}

REALISTIC_FEMALE_NAMES = [
    "Анна", "Мария", "Екатерина", "Елена", "Ольга", "Наталья", "Ирина", "Светлана",
    "Татьяна", "Юлия", "Александра", "Дарья", "Софья", "Анастасия", "Виктория", "Полина",
    "Елизавета", "Маргарита", "Ксения", "Алина", "Валерия", "Диана", "Вероника", "Карина",
    "Кристина", "Яна", "Ангелина", "Евгения", "Марина", "Оксана", "Людмила", "Надежда",
    "Галина", "Тамара", "Зоя", "Лариса", "Нина", "Раиса", "Любовь", "Вера",
    "Алиса", "Варвара", "Ульяна", "Мирослава", "Ярослава", "Аглая", "Антонина", "Пелагея",
    "Серафима", "Авдотья"
]

REALISTIC_MALE_NAMES = [
    "Александр", "Дмитрий", "Максим", "Сергей", "Андрей", "Алексей", "Артём", "Илья",
    "Кирилл", "Михаил", "Никита", "Матвей", "Роман", "Егор", "Арсений", "Иван",
    "Денис", "Евгений", "Павел", "Владимир"
]

ANIME_NAMES = [
    "Сакура", "Юки", "Хината", "Рин", "Аой", "Мика", "Юна", "Ая",
    "Каори", "Наоми", "Томоми", "Эми", "Юи", "Мисаки", "Акира", "Харука",
    "Рен", "Каору", "Шин", "Кен", "Хиро", "Такуя", "Рю", "Казуя",
    "Аки", "Юджи", "Кента", "Дайсуке", "Масаши", "Тору"
]

REALISTIC_FEMALE_APPEARANCES = [
    "long wavy chestnut hair, green eyes, delicate features, porcelain skin",
    "short platinum blonde bob, blue eyes, sharp features, fair skin, freckles",
    "long straight dark brown hair, brown eyes, sophisticated features, olive skin",
    "long bright red hair with bangs, hazel eyes, playful features, fair skin, rosy cheeks",
    "long blonde hair, blue eyes, innocent face, soft features, fair skin",
    "sleek black bob hair, sharp green eyes, elegant features, pale skin",
    "medium brown hair, warm brown eyes, kind face, gentle smile",
    "ponytail blonde hair, bright blue eyes, athletic build, tanned skin",
    "short grey-streaked hair, piercing grey eyes, stern features, glasses",
    "long dark hair, striking hazel eyes, perfect makeup, model features"
]

REALISTIC_MALE_APPEARANCES = [
    "messy brown hair, gentle blue eyes, soft features, slim build",
    "short dark hair, confident brown eyes, strong jawline, athletic build",
    "short grey-brown hair, calm brown eyes, mature features, kind face",
    "blonde spiky hair, bright blue eyes, energetic look, fit body",
    "black curly hair, dark eyes, mysterious aura, tall build"
]

GALLERY_SCENES = {
    "realistic_female": [
        ("office", "modern bright office interior, smart business attire, soft natural light"),
        ("cafe", "cozy specialty coffee shop interior, warm ambient lighting, coffee cup, casual chic outfit"),
        ("gallery", "modern art gallery interior, minimalist paintings on background, stylish blazer"),
        ("library", "architectural library interior, bookshelves, smart casual sweater, natural daylight"),
        ("city", "european city street, modern architecture, trench coat, golden hour lighting"),
        ("studio", "professional photo studio, elegant minimalist dress, soft key lighting"),
        ("park", "botanical garden pathway, dappled sunlight, relaxed smart casual outfit"),
        ("lounge", "stylish hotel lounge interior, warm evening lights, sophisticated attire")
    ],
    "realistic_male": [
        ("office", "modern architectural office, tailored suit, professional lighting"),
        ("cafe", "specialty coffee shop interior, smart casual shirt, warm ambient lighting"),
        ("studio", "professional photo studio, minimalist turtleneck, soft key lighting"),
        ("city", "modern business district street, stylish coat, evening city lights"),
        ("library", "modern workspace library, bookshelves, casual blazer, natural light"),
        ("nature", "scenic mountain viewpoint, outdoor jacket, crisp morning daylight")
    ],
    "anime": [
        ("library", "anime modern library interior, warm sunlight through tall windows, anime style"),
        ("cafe", "anime cozy coffee shop, wooden interior, latte art, warm evening lighting, anime art"),
        ("rooftop", "anime rooftop terrace, panoramic city skyline at sunset, dramatic clouds, anime style"),
        ("gallery", "anime contemporary art museum, clean lighting, stylish outfit, detailed background"),
        ("garden", "anime botanical conservatory, lush green plants, glass roof, soft daylight, anime style"),
        ("street", "anime modern Tokyo street at twilight, soft bokeh city lights, stylish coat, anime art")
    ]
}

ANIME_FEMALE_APPEARANCES = [
    "anime illustration, short dark blue bob cut, glasses, smart casual blazer, modern office, makoto shinkai lighting",
    "anime art, long wavy silver hair with side braid, gentle green eyes, cozy knit sweater, sunlit cafe",
    "stylized anime portrait, sleek high ponytail, auburn hair, sharp amber eyes, tailored trench coat, evening city",
    "semi-realistic anime style, shoulder-length chestnut hair, hairpins, warm brown eyes, minimalist studio",
    "kyoto animation style, long straight black hair, violet eyes, white blouse, botanical garden background",
    "modern digital anime, asymmetrical emerald hair, confident smile, techwear jacket, futuristic library",
    "90s retro anime aesthetic, curly honey blonde hair, soft film grain, vintage dress, art gallery",
    "anime portrait, braided dark red hair, freckles, hazel eyes, turtleneck sweater, autumn park",
    "clean lineart anime, platinum blonde pixie cut, piercing blue eyes, business shirt, bright workspace",
    "detailed anime art, long dark purple hair in low bun, calm expression, kimono-inspired modern jacket"
]

ANIME_MALE_APPEARANCES = [
    "anime illustration, messy dark brown hair, round glasses, grey turtleneck, modern studio, soft daylight",
    "semi-realistic anime art, neat black hair, sharp grey eyes, dark tailored suit, city skyline background",
    "modern digital anime, tousled silver hair, calm blue eyes, casual denim jacket, sunlit cafe",
    "kyoto animation style, short auburn hair, warm smile, beige cardigan, university library background",
    "stylized manhwa art, slicked back dark hair, confident look, minimalist black shirt, evening lighting",
    "anime portrait, wavy chestnut hair, green eyes, hoodie under blazer, creative workspace"
]

# Список увлечений и интересов персонажей
HOBBIES = [
    "архитектура", "джазовая музыка", "современная литература", "урбанистика",
    "пленочная фотография", "гастрономия и спешелти-кофе", "психология общения",
    "история искусств", "шахматы", "скандинавский дизайн", "когнитивистика",
    "документальное кино", "астрономия", "путешествия по малым городам"
]

# Профессиональные роли с разделением по гендеру
PROFESSIONAL_ROLES = {
    "female": [
        "архитектор общественных пространств", "нейропсихолог и специалист по когнитивным привычкам",
        "арт-директор независимого издательства", "финансовый аналитик в технологическом фонде",
        "куратор выставок современного искусства", "продуктовый дизайнер и исследователь пользовательского опыта",
        "редактор научно-популярного журнала", "коуч по публичным выступлениям и коммуникациям"
    ],
    "male": [
        "инженер-робототехник и преподаватель", "архитектор информационных систем",
        "сценарист документального кино", "урбанист и исследователь городской среды",
        "инвестиционный консультант", "промышленный дизайнер"
    ]
}

# Уникальные особенности и привычки
QUIRKS = [
    "коллекционирую виниловые пластинки с джазом шестидесятых",
    "по выходным реставрирую старую пленочную фототехнику",
    "веду авторские заметки об истории городской архитектуры",
    "разбираюсь в тонкостях обжарки редкого зернового кофе",
    "играю в шахматы вслепую и люблю сложные головоломки",
    "увлекаюсь парусным спортом и прогнозами погоды",
    "перевожу редкие статьи об искусстве и дизайне",
    "изучаю поведенческую экономику на примерах из кино",    
    "веду закрытый книжный клуб и разбираю сюжеты классики",
    "создаю авторскую керамику и люблю минимализм в интерьере",
    "прокладываю нетуристические пешие маршруты по старым городам",
    "анализирую психологию переговоров и язык жестов"
]


# Манера общения
COMMUNICATION_STYLES = [
    "Общается структурированно, с легкой самоиронией и вниманием к деталям.",
    "Умеет поддержать глубокий разговор, задает точные вопросы и ценит искренность.",
    "Говорит спокойно и рассудительно, помогает разложить сложные мысли по полочкам.",
    "Обладает живым умом, тактичностью и широким кругозором."
]
# ============================================================================
# 📝 ГЕНЕРАЦИЯ ТЕКСТА И КОНФИГА
# ============================================================================

def format_age_ru(age):
    last_two = age % 100
    last_one = age % 10
    if 11 <= last_two <= 19:
        word = "лет"
    elif last_one == 1:
        word = "год"
    elif 2 <= last_one <= 4:
        word = "года"
    else:
        word = "лет"
    return f"{age} {word}"

def format_age_words_ru(age):
    tens = {
        2: "двадцать", 3: "тридцать", 4: "сорок", 5: "пятьдесят",
        6: "шестьдесят", 7: "семьдесят", 8: "восемьдесят", 9: "девяносто"
    }
    teens = {
        10: "десять", 11: "одиннадцать", 12: "двенадцать", 13: "тринадцать",
        14: "четырнадцать", 15: "пятнадцать", 16: "шестнадцать",
        17: "семнадцать", 18: "восемнадцать", 19: "девятнадцать"
    }
    ones = {
        1: "один", 2: "два", 3: "три", 4: "четыре", 5: "пять",
        6: "шесть", 7: "семь", 8: "восемь", 9: "девять"
    }

    if 10 <= age <= 19:
        num_words = teens[age]
        word = "лет"
    else:
        t = tens.get(age // 10, "")
        o = ones.get(age % 10, "")
        num_words = f"{t} {o}".strip()

        last_one = age % 10
        if last_one == 1:
            word = "год"
        elif 2 <= last_one <= 4:
            word = "года"
        else:
            word = "лет"

    return f"{num_words} {word}"

def generate_self_introduction(name, age, role, quirk, comm_style, hobbies, gender):
    age_text = format_age_words_ru(age)
    hobby_text = ", ".join(random.sample(hobbies, min(3, len(hobbies))))
    rad = "рада" if gender == "female" else "рад"
    templates = [
        f"Привет! Меня зовут {name}, мне {age_text}. Я {role}. В свободное время {quirk}, а также люблю {hobby_text}. Буду {rad} интересному разговору!",
        f"Здравствуйте! Я {name}, мне {age_text}, работаю как {role}. Помимо работы, меня увлекает {hobby_text}. {comm_style} Приятно познакомиться!",
        f"Привет! Я {name}, {age_text}. По профессии я {role}, а для души {quirk}. С удовольствием обсужу {hobby_text}. Буду {rad} общению!"
    ]
    return random.choice(templates)

def generate_character_config(key, name, age, gender, appearance, role, quirk, comm_style, hobbies, style="realistic"):
    traits = {
        "intelligence": random.randint(60, 98),
        "confidence": random.randint(55, 95),
        "openness": random.randint(60, 98),
        "empathy": random.randint(55, 95),
        "humor": random.randint(45, 90)
    }

    initial_state = {
        "arousal": random.randint(10, 30),
        "mood": random.randint(50, 85),
        "trust": random.randint(30, 60),
        "intimacy": random.randint(10, 30),
        "energy": random.randint(60, 95)
    }

    age_text = format_age_ru(age)
    hobby_list = ", ".join(random.sample(hobbies, 3))
    personality_text = (
        f"Ты — {name}, {age_text}. Твоя профессия: {role}. "
        f"Твоя особенность: {quirk}. {comm_style} "
        f"Твои интересы: {hobby_list}. Общайся профессионально, доброжелательно и по делу."
    )
    description = f"{role.capitalize()}, {age_text}. {comm_style}"
    seed = hash(f"{name}_{age}_{gender}_{style}_{random.randint(1, 99999)}") % 100000

    emoji_map = {
        "realistic": ["💼", "📚", "💡", "🎯", "🧭", "🏛️", "☕", "🎨", "🔬", "✨"],
        "anime": ["✨", "📚", "🎨", "☕", "💡", "🌟"]
    }

    config = {
        "name": name,
        "age": age,
        "gender": gender,
        "style": style,
        "emoji": random.choice(emoji_map[style]),
        "personality": personality_text,
        "description": description,
        "face_desc": f"{age} yo {'woman' if gender == 'female' else 'man'}, {appearance}",
        "negative": "ugly, deformed, bad anatomy, bad hands, extra fingers, worst quality, low quality, blurry, nsfw, nude",
        "seed": seed,
        "subscription_required": random.choice([False, False, False, True]),
        "nsfw_allowed": False,
        "traits": traits,
        "initial_state": initial_state
    }
    return config


# ============================================================================
# 🖼️ ГЕНЕРАЦИЯ ФОТО (ИСПРАВЛЕНО: ПОРТРЕТЫ ПО ПЛЕЧИ!)
# ============================================================================

def load_image_models():
    """Загружает модели для генерации изображений с обработкой ошибок"""
    
    log_step(5, "Загрузка моделей для генерации изображений")
    
    realistic_model = None
    anime_model = None
    
    # Загружаем DreamShaper
    try:
        log("Загружаю DreamShaper (фотореализм)...")
        from diffusers import StableDiffusionPipeline
        import torch
        
        realistic_model = StableDiffusionPipeline.from_pretrained(
            "Lykon/DreamShaper",
            torch_dtype=torch.float16,
            safety_checker=None,
        ).to("cuda")
        realistic_model.enable_attention_slicing()
        log("DreamShaper загружен", "SUCCESS")
    except Exception as e:
        log(f"Ошибка загрузки DreamShaper: {e}", "ERROR")
        traceback.print_exc()
    
    # Загружаем Anything V3.1
    try:
        log("Загружаю Anything V3.1 (аниме)...")
        from diffusers import StableDiffusionPipeline
        import torch
        
        anime_model = StableDiffusionPipeline.from_pretrained(
            "Linaqruf/anything-v3-1",
            torch_dtype=torch.float16,
            safety_checker=None,
        ).to("cuda")
        anime_model.enable_attention_slicing()
        log("Anything V3.1 загружен", "SUCCESS")
    except Exception as e:
        log(f"Ошибка загрузки Anything V3.1: {e}", "ERROR")
        traceback.print_exc()
    
    if realistic_model is None and anime_model is None:
        log("Не удалось загрузить ни одну модель!", "ERROR")
        return None, None
    
    return realistic_model, anime_model

def generate_photo(model, prompt, negative_prompt, output_path, seed=42, is_anime=False, guidance_scale=8.0):
    """Генерирует одно фото с обработкой ошибок"""
    import torch
    
    try:
        generator = torch.Generator(device="cuda").manual_seed(seed)
        
        if is_anime:
            negative_prompt = "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, 3d, realistic, photorealistic, " + negative_prompt
        
        with torch.inference_mode():
            image = model(
                prompt,
                negative_prompt=negative_prompt,
                num_inference_steps=35,
                guidance_scale=guidance_scale,
                width=512,
                height=768,
                generator=generator,
            ).images[0]
        
        image.save(output_path, quality=95)
        return True
    except Exception as e:
        log(f"Ошибка генерации фото: {e}", "ERROR")
        traceback.print_exc()
        return False

# ============================================================================
# 🎤 ГЕНЕРАЦИЯ ГОЛОСА
# ============================================================================

def load_tts_model():
    """Загружает модель для синтеза речи с обработкой ошибок"""
    
    log_step(6, "Загрузка XTTS v2")
    
    try:
        from TTS.api import TTS
        import torch
        
        os.environ["COQUI_TOS_AGREED"] = "1"
        tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
        log("XTTS v2 загружен", "SUCCESS")
        return tts
    except Exception as e:
        log(f"Ошибка загрузки XTTS v2: {e}", "ERROR")
        traceback.print_exc()
        return None

def generate_voice(tts, text, speaker_wav, output_path):
    """Генерирует голосовое описание с обработкой ошибок"""
    try:
        tts.tts_to_file(
            text=text,
            language="ru",
            speaker_wav=speaker_wav,
            file_path=output_path
        )
        return True
    except Exception as e:
        log(f"Ошибка генерации голоса: {e}", "ERROR")
        traceback.print_exc()
        return False

# ============================================================================
# 🎯 ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================

def generate_all_characters():
    """Генерирует всех 100 персонажей с подробным логированием"""
    
    log("=" * 60)
    log("🎭 ГЕНЕРАТОР 100 ПЕРСОНАЖЕЙ v4.3")
    log("   ✅ УЛУЧШЕННАЯ ДИАГНОСТИКА")
    log("=" * 60)
    
    # Шаг 1: Скачиваем голоса
    if not download_voices_from_github():
        log("Не удалось загрузить голоса. Завершаю работу.", "ERROR")
        sys.exit(1)
    
    # Шаг 2: Устанавливаем зависимости
    install_dependencies()
    
    # Шаг 3: Проверяем GPU
    if not check_gpu():
        log("GPU не доступен. Завершаю работу.", "ERROR")
        sys.exit(1)
    
    # Шаг 4: Сканируем голоса
    voices = scan_voice_folders()
    
    total_voices = sum(len(files) for files in voices.values())
    if total_voices == 0:
        log("Не найдено ни одного голоса. Завершаю работу.", "ERROR")
        sys.exit(1)
    
    # Шаг 5: Загружаем модели изображений
    realistic_model, anime_model = load_image_models()
    
    if realistic_model is None and anime_model is None:
        log("Не удалось загрузить модели изображений. Завершаю работу.", "ERROR")
        sys.exit(1)
    
    # Шаг 6: Загружаем TTS
    tts_model = load_tts_model()
    
    if tts_model is None:
        log("Не удалось загрузить TTS модель. Продолжаю без озвучки.", "WARNING")
    
    # Создаём папку characters/
    characters_dir = Path(CHARACTERS_DIR)
    characters_dir.mkdir(exist_ok=True)
    
    # Формируем список персонажей
    log_step(7, "Формирование списка персонажей")
    
    characters = []

    for i in range(NUM_REALISTIC_FEMALE):
        if i < FEMALE_AGE_DISTRIBUTION["young"]:
            age_group = "young"
        elif i < FEMALE_AGE_DISTRIBUTION["young"] + FEMALE_AGE_DISTRIBUTION["middle"]:
            age_group = "middle"
        else:
            age_group = "old"

        age = random.randint(*AGE_GROUPS[age_group])
        name = REALISTIC_FEMALE_NAMES[i % len(REALISTIC_FEMALE_NAMES)]
        appearance = REALISTIC_FEMALE_APPEARANCES[i % len(REALISTIC_FEMALE_APPEARANCES)]
        role = random.choice(PROFESSIONAL_ROLES["female"])
        quirk = random.choice(QUIRKS)
        comm_style = random.choice(COMMUNICATION_STYLES)
        hobbies = random.sample(HOBBIES, random.randint(3, 5))

        characters.append({
            "key": f"realistic_female_{i+1}",
            "name": name,
            "age": age,
            "gender": "female",
            "appearance": appearance,
            "role": role,
            "quirk": quirk,
            "comm_style": comm_style,
            "hobbies": hobbies,
            "style": "realistic",
            "age_group": age_group
        })

    for i in range(NUM_REALISTIC_MALE):
        age = random.randint(24, 52)
        name = REALISTIC_MALE_NAMES[i % len(REALISTIC_MALE_NAMES)]
        appearance = REALISTIC_MALE_APPEARANCES[i % len(REALISTIC_MALE_APPEARANCES)]
        role = random.choice(PROFESSIONAL_ROLES["male"])
        quirk = random.choice(QUIRKS)
        comm_style = random.choice(COMMUNICATION_STYLES)
        hobbies = random.sample(HOBBIES, random.randint(3, 5))

        characters.append({
            "key": f"realistic_male_{i+1}",
            "name": name,
            "age": age,
            "gender": "male",
            "appearance": appearance,
            "role": role,
            "quirk": quirk,
            "comm_style": comm_style,
            "hobbies": hobbies,
            "style": "realistic"
        })

    for i in range(NUM_ANIME):
        age = random.randint(19, 32)
        name = ANIME_NAMES[i % len(ANIME_NAMES)]
        gender = "female" if i < 20 else "male"
        if gender == "female":
            appearance = ANIME_FEMALE_APPEARANCES[i % len(ANIME_FEMALE_APPEARANCES)]
        else:
            appearance = ANIME_MALE_APPEARANCES[i % len(ANIME_MALE_APPEARANCES)]
        role = random.choice(PROFESSIONAL_ROLES[gender])
        quirk = random.choice(QUIRKS)
        comm_style = random.choice(COMMUNICATION_STYLES)
        hobbies = random.sample(HOBBIES, random.randint(3, 5))

        characters.append({
            "key": f"anime_{i+1}",
            "name": name,
            "age": age,
            "gender": gender,
            "appearance": appearance,
            "role": role,
            "quirk": quirk,
            "comm_style": comm_style,
            "hobbies": hobbies,
            "style": "anime"
        })

    random.shuffle(characters)
    
    log(f"Сгенерировано {len(characters)} персонажей:")
    log(f"  👩 Реалистичных женщин: {NUM_REALISTIC_FEMALE}")
    log(f"  👨 Реалистичных мужчин: {NUM_REALISTIC_MALE}")
    log(f"  🌸 Аниме персонажей: {NUM_ANIME}")
    
    # Генерируем файлы для каждого персонажа
    log_step(8, "Генерация файлов персонажей")
    
    start_time = time.time()
    errors = []
    
    for idx, char in enumerate(characters, 1):
        log(f"\n{'=' * 60}")
        log(f"[{idx}/{len(characters)}] {char['name']} ({char['age']} лет)")
        log(f"Стиль: {'🌸 АНИМЕ' if char['style'] == 'anime' else '📷 ФОТОРЕАЛИЗМ'}")
        log(f"{'=' * 60}")
        
        try:
            char_dir = characters_dir / char["key"]
            char_dir.mkdir(exist_ok=True)
            (char_dir / "gallery").mkdir(exist_ok=True)
            
            # 1. Выбираем и копируем голос
            if char["style"] == "realistic":
                source_voice = select_voice(voices, char["gender"], char["age"])
            else:
                source_voice = select_voice(voices, char["gender"], 25)
            
            if source_voice:
                voice_path = copy_voice_to_character(source_voice, char_dir)
                log(f"Голос скопирован: {os.path.basename(source_voice)}", "SUCCESS")
            else:
                log(f"Голос не найден", "WARNING")
                voice_path = None
            
            # 2. Генерируем config.json
            config = generate_character_config(
                char["key"], char["name"], char["age"], char["gender"],
                char["appearance"], char["role"], char["quirk"],
                char["comm_style"], char["hobbies"], char["style"]
            )

            
            config_file = char_dir / "config.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            log(f"Создан config.json", "SUCCESS")
            
            # 3. Генерируем главное фото (ПОРТРЕТ ПО ПЛЕЧИ!)
            model = anime_model if char["style"] == "anime" else realistic_model
            
            if model is None:
                log(f"Модель для {char['style']} не загружена, пропускаю фото", "WARNING")
            else:
                is_anime = char["style"] == "anime"
                
                if is_anime:
                    main_prompt = f"masterpiece, best quality, portrait, upper body, head and shoulders, {config['face_desc']}, beautiful, detailed face, looking at viewer"
                    main_negative = f"{config['negative']}, full body, legs, feet, wide shot, distant, small figure"
                else:
                    main_prompt = f"photorealistic portrait, upper body, head and shoulders, {config['face_desc']}, professional photography, 8k, sharp focus, detailed face, looking at viewer"
                    main_negative = f"{config['negative']}, full body, legs, feet, wide shot, distant, small figure"
                
                main_photo = char_dir / "main.jpg"
                if generate_photo(model, main_prompt, main_negative, str(main_photo), config["seed"], is_anime, guidance_scale=8.0):
                    log(f"Создано main.jpg (ПОРТРЕТ ПО ПЛЕЧИ)", "SUCCESS")
                else:
                    log(f"Ошибка генерации main.jpg", "ERROR")
                    errors.append(f"{char['key']}: main.jpg")
            
            # 4. Генерируем 4 фото для галереи
            if model is not None:
                
                scene_key = "anime" if char["style"] == "anime" else f"realistic_{char['gender']}"
                available_scenes = GALLERY_SCENES.get(scene_key, GALLERY_SCENES["realistic_female"])

                scenes = random.sample(available_scenes, 4)
                
                for scene_name, scene_desc in scenes:
                    is_anime = char["style"] == "anime"
                    
                    if is_anime:
                        gallery_prompt = f"masterpiece, best quality, portrait, upper body, {config['face_desc']}, {scene_desc}"
                        gallery_negative = f"{config['negative']}, full body, legs, feet, wide shot, distant"
                    else:
                        gallery_prompt = f"photorealistic, portrait, upper body, {config['face_desc']}, {scene_desc}, 8k, sharp focus"
                        gallery_negative = f"{config['negative']}, full body, legs, feet, wide shot, distant"
                    
                    gallery_photo = char_dir / "gallery" / f"{scene_name}.jpg"
                    if generate_photo(model, gallery_prompt, gallery_negative, str(gallery_photo), 
                                 config["seed"] + hash(scene_name) % 1000, is_anime, guidance_scale=8.0):
                        log(f"Создано gallery/{scene_name}.jpg (ПОРТРЕТ)", "SUCCESS")
                    else:
                        log(f"Ошибка генерации gallery/{scene_name}.jpg", "ERROR")
                        errors.append(f"{char['key']}: gallery/{scene_name}.jpg")
            
            # 5. Генерируем голосовое описание
            if voice_path and tts_model is not None:
                voice_text = generate_self_introduction(
                    char["name"], char["age"], char["role"],
                    char["quirk"], char["comm_style"], char["hobbies"], char["gender"]
                )

                voice_file = char_dir / "voice_intro.wav"
                if generate_voice(tts_model, voice_text, voice_path, str(voice_file)):
                    log(f"Создано voice_intro.wav", "SUCCESS")
                    log(f"Текст: {voice_text[:60]}...")
                else:
                    log(f"Ошибка генерации voice_intro.wav", "ERROR")
                    errors.append(f"{char['key']}: voice_intro.wav")
            
            # Прогресс
            elapsed = time.time() - start_time
            avg_time = elapsed / idx
            remaining = avg_time * (len(characters) - idx)
            log(f"Прогресс: {idx}/{len(characters)} | Осталось: {remaining/60:.1f} мин")
            
        except Exception as e:
            log(f"Критическая ошибка при генерации {char['name']}: {e}", "ERROR")
            traceback.print_exc()
            errors.append(f"{char['key']}: {str(e)}")
            continue
    
    # Завершение
    total_time = time.time() - start_time
    
    log(f"\n{'=' * 60}")
    log(f"🎉 ГОТОВО!")
    log(f"{'=' * 60}")
    log(f"\n📊 Статистика:")
    log(f"   Персонажей: {len(characters)}")
    log(f"   Файлов: {len(characters) * 7}")
    log(f"   Время: {total_time/3600:.1f} часов")
    log(f"   Ошибок: {len(errors)}")
    
    if errors:
        log(f"\n⚠️ Список ошибок:")
        for error in errors:
            log(f"   - {error}")
    
    log(f"\n✅ ВСЕ ФОТО - ПОРТРЕТЫ ПО ПЛЕЧИ!")
    log(f"📁 Папка characters/ готова к загрузке на сервер")

# ============================================================================
# 🚀 ЗАПУСК
# ============================================================================

if __name__ == "__main__":
    try:
        log("Запуск скрипта...")
        generate_all_characters()
        log("Скрипт завершён успешно!", "SUCCESS")
    except KeyboardInterrupt:
        log("\n\n⚠️ Скрипт прерван пользователем", "WARNING")
        sys.exit(0)
    except Exception as e:
        log(f"\n\n❌ Критическая ошибка: {e}", "ERROR")
        traceback.print_exc()
        sys.exit(1)
