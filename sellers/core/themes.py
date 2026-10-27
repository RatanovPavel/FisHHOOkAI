import os
import copy
import json

class SkullaThemeManager:

    @classmethod
    def generate_virtual_style_configs(cls, base_config):
        """
        ДВИЖОК ВИРТУАЛЬНОГО КЛОНИРОВАНИЯ ШЕФА (ОБНОВЛЕННЫЙ).
        Создает базовый макет в единственном экземпляре без привязки к категориям.
        Автоматический маппинг теперь работает только внутри редактора.
        """
        virtual_cards = []
        base_id = base_config["id"] # Пример: "skulla_seller_product_showcase"
        
        # 1. Делаем глубокое копирование базового конфига
        v_cfg = copy.deepcopy(base_config)
        
        # 2. Намертво привязываем универсальный тег вместо категорий
        v_cfg["id"] = f"{base_id}"
        #v_cfg["tags"] = ["universal"]
        #v_cfg["groups"] = ["cat_templates"]
        
        # 3. Собираем универсальный пул превью-фонов из дефолтной папки
        style_bgs = []
        try:
            # Используем универсальную папку, например, "studio_general" или "cat_undefined"
            category_folder = "cat_undefined"
            v_cfg["category_id"] = category_folder
            
            BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            category_preview_dir = os.path.join(BASE_DIR, "static", "backgrounds_preview", category_folder)
            
            if os.path.exists(category_preview_dir) and os.path.isdir(category_preview_dir):
                raw_files = os.listdir(category_preview_dir)
                for f in raw_files:
                    if f.lower().endswith('.png'):
                        style_bgs.append(f.replace(".png", ""))
                style_bgs = sorted(style_bgs)
                print(f"✨ [SKULLA RECOVERY]: Папка превью '{category_folder}' успешно считана. Фонов: {len(style_bgs)}", flush=True)
            else:
                style_bgs = []
        except Exception as e:
            print(f"⚠️ [THEME_REGISTRY_WARN]: Ошибка чтения папки превью: {e}", flush=True)
            style_bgs = []
            
        if not style_bgs:
            style_bgs = ["studio_charcoal"]
            
        # 4. Инжектируем универсальный список фонов в контроллер
        for ctrl in v_cfg.get("controls", []):
            if ctrl.get("id") == "bg_material":
                ctrl["options"] = style_bgs
                
        # 5. Выставляем универсальные дефолтные значения для контролов
        for ctrl in v_cfg.get("controls", []):
            ctrl_id = ctrl["id"]
            
            if ctrl_id == "bg_color":
                ctrl["default"] = "#0F172A" # Базовый стильный темный фон
                
            elif ctrl_id == "bg_blur_strength":
                ctrl["default"] = 0
                
            elif ctrl_id == "font_name":
                ctrl["default"] = "ariblk.ttf"
                
            elif ctrl_id == "style_hue":
                ctrl["default"] = "#05B6D4" # Нейтральный бирюзовый акцент
                
            elif ctrl_id == "font_color":
                ctrl["default"] = "#FFFFFF"
                
        # 6. Добавляем чистую карту в массив и возвращаем её
        virtual_cards.append(v_cfg)
        return virtual_cards
