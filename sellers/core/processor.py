import os 
import io
import time
import shutil
import json
import cv2
import numpy as np
from PIL import Image, ImageOps, ImageDraw, ImageFilter
from rembg import remove
from core.vision import SkullaVision

# СИЛОВОЙ ИМПОРТ (Тот самый, что выдал "✅ ЕСТЬ КОНТАКТ")
from mediapipe.python.solutions import face_mesh as mp_face_mesh

from effects import EFFECTS_DATA
from config import AVATAR_SIZE, RESULT_DIR, ASSETS_DIR, UPLOAD_DIR

class ImageProcessor:

# core/processor.py

    @staticmethod
    def apply_style(session_path, style_id, params, is_pro=False):
        """
        Применяет выбранный эффект к изображению в сессии.
        """
        # 1. ПРОВЕРКА ЭФФЕКТА
        if style_id not in EFFECTS_DATA:
            raise Exception(f"Style '{style_id}' not found in EFFECTS_DATA")
        
        effect_config = EFFECTS_DATA[style_id]
        effect_func = effect_config.get("func")
        
        if not effect_func:
            raise Exception(f"Effect function for '{style_id}' is missing")

        # 2. ПОДГОТОВКА ИЗОБРАЖЕНИЯ (Загружаем original.png)
        img_path = os.path.join(session_path, "original.png")
            
        if not os.path.exists(img_path):
            raise Exception("Source image (before.png/original.png) not found in session")

        user_pil = Image.open(img_path).convert("RGBA")

        # 3. ПОДГРУЗКА НЕЙРО-ДАННЫХ (MESH / LANDMARKS)
        if "user_data" not in params:
            for json_name in ["original_raw.json", "before_raw.json"]:
                json_path = os.path.join(session_path, json_name)
                if os.path.exists(json_path):
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            params["user_data"] = json.load(f)
                            print(f"🧠 [PROCESSOR]: Данные лица подгружены из {json_name}")
                        break
                    except Exception as e:
                        print(f"⚠️ [PROCESSOR_ERR]: Ошибка чтения JSON: {e}")

        # Прокидываем путь к сессии
        params["session_path"] = session_path

        # 4. ВЫЗОВ ЭФФЕКТА
        try:
            # 🎯 ИСПРАВЛЕНО: Принимаем результат в одну переменную, чтобы не падать на видеоэффектах
            effect_result = effect_func(user_pil, params, is_pro=is_pro)
            
            # 🎯 ИЗОЛЯЦИЯ ВИДЕО: Если вернулся словарь (наш видеоэффект)
            if isinstance(effect_result, dict) and effect_result.get("is_video") == True:
                if "preview_img" in effect_result:
                    target_path = os.path.join(session_path, "after.png")
                    effect_result["preview_img"].save(target_path, "PNG")
                
                print(f"✅ [PROCESSOR]: Видео-эффект '{style_id}' успешно обработан.")
                return effect_result

            # 🎯 СТАРАЯ ОРИГИНАЛЬНАЯ ЛОГИКА КАРТИНОК (Один в один как до поломки)
            _, processed_pil = effect_result
            

            # 🎯 КВАНТОВАЯ ОПТИМИЗАЦИЯ ШЕФА: Никакого спама и генерации лишних файлов!
            # Полностью выжгли after_full, processed_full и 768х1024 к чертям!
            
            if is_pro:
                # 🔥 РЕЖИМ А: БОЕВОЙ ЭКСПОРТ. Генерируем ЧИСТЫЙ Full HD 900x1200 строго в момент скачивания! [INDEX]
                # Изменяем размер холста до оригинального высокого разрешения 900х1200
                # (или 1200х900 в зависимости от ориентации твоего шаблона)
                W_target, H_target = 900, 1200
                img_final = processed_pil.resize((W_target, H_target), Image.Resampling.LANCZOS)
                
                # Сохраняем как временный экспортный файл, который сразу заберет роутер /export
                export_filename = "processed_export.png"
                target_path = os.path.join(session_path, export_filename)
                img_final.save(target_path, "PNG")
                
                print(f"🚀 [CORE EXPORT]: Сгенерирован чистый HD-файл {W_target}x{H_target} для скачивания", flush=True)
                return "original.png", export_filename
            else:
                # ⚡ РЕЖИМ Б: ОБЫЧНОЕ ПРЕВЬЮ. Сжимаем холст строго до легких 600х800 для админки Хрома! [INDEX]
                W_target, H_target = 600, 800
                img_final = processed_pil.resize((W_target, H_target), Image.Resampling.LANCZOS)
                
                # На сервере сохраняется ТОЛЬКО ОДИН файл превью after.png! [INDEX]
                target_path = os.path.join(session_path, "after.png")
                img_final.save(target_path, "PNG")
                
                print(f"📸 [CORE PREVIEW]: Сохранен единственный легкий файл превью after.png ({W_target}x{H_target})", flush=True)
                return "original.png", "after.png"


        except Exception as e:
            print(f"❌ [PROCESSOR_CRITICAL_ERR]: {str(e)}")
            raise e


    @staticmethod
    def remove_background(image_bytes, session_path):
        """Вырезает фон один раз и сохраняет в папку сессии"""
        no_bg_bytes = remove(image_bytes)
        no_bg_path = os.path.join(session_path, "no_bg.png")
        
        with open(no_bg_path, "wb") as f:
            f.write(no_bg_bytes)
            
        return no_bg_path

    @staticmethod
    def add_watermark(img, is_preview_mode=True):
        """
        Промышленный движок защиты контента Skulla DRM Engine.
        🎯 ИСПРАВЛЕНО: Добавлена поддержка флага разделения превью и Full HD оригинала!
        """
        from PIL import ImageFont, ImageDraw, ImageFilter, Image
        import os

        # 🔥 РЕЖИМ ВЫГРУЗКИ: Если это финальный оригинал для маркетплейса — отдаем картинку чистой!
        if not is_preview_mode:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            print("🚀 [SKULLA PROCESSOR]: Выгрузка Full HD оригинала 900x1200 без ватермарков зафиксирована!", flush=True)
            return img

        # 🔒 РЕЖИМ ПРЕВЬЮ: Включаем ИИ-защиту от скриншотов и воровства контента
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        W, H = img.size
        wm_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(wm_layer)
        
        # Размеры (0.06 от ширины)
        font_size = max(30, int(W * 0.06)) 
        margin = int(W * 0.04)
        
        # Проверяем пути к шрифту Teko
        font_path = os.path.join("assets", "fonts", "ariblk.ttf")
        if not os.path.exists(font_path):
            font_path = os.path.join("/app", "assets", "fonts", "ariblk.ttf")

        try:
            font = ImageFont.truetype(font_path, font_size)
        except:
            font = ImageFont.load_default()

        text = "SKULLA.RU" 
        
        # Позиционирование
        text_y = H - font_size - margin
        icon_res = int(font_size * 1.3) 
        text_x = margin + icon_res + int(font_size * 0.15)
        text_pos = (text_x, text_y)

        # Вставка фирменного черепа Skulla
        try:
            skull_icon = Image.open("static/favicons/favicon-128x128.png").convert("RGBA")
            skull_icon = skull_icon.resize((icon_res, icon_res), Image.LANCZOS)
            skull_y = text_y + int(font_size * 0.18) 
            wm_layer.paste(skull_icon, (margin, skull_y), skull_icon)
        except:
            text = "💀 " + text
            text_pos = (margin, text_y)

        # Рендеринг эффектов текста (Тонкая обводка + Бирюзовый Неон)
        stroke = max(1, font_size // 20)
        
        # Тень подложки
        draw.text((text_pos[0]+stroke, text_pos[1]+stroke), text, font=font, fill=(0,0,0,150))
        # Свечение неона
        draw.text(text_pos, text, font=font, fill=(34, 211, 238, 180), stroke_width=stroke, stroke_fill=(0,0,0,255))
        # Основной text
        draw.text(text_pos, text, font=font, fill=(255, 255, 255, 255))

        # Сливаем защиту с превью-слоем
        combined = Image.alpha_composite(img, wm_layer).convert("RGB")
        
        # 📐 СЖАТИЕ: Ужимаем превью-версию в 2 раза (450x600) для реактивной скорости сети 60 FPS!
        preview_w, preview_h = W // 2, H // 2
        compressed_preview = combined.resize((preview_w, preview_h), Image.Resampling.LANCZOS)
        
        print("🏁 [SKULLA PROCESSOR]: Защищенное превью 450x600 с неоновым черепом успешно собрано!", flush=True)
        return compressed_preview






    
    @staticmethod
    def prepare_layer(pil_img, session_path, filename, requirements):
        """
        Умная подготовка слоев с принудительным дебагом геометрии маркетплейсов.
        """
        import json
        import traceback
        
        orig_save_path = os.path.join(session_path, "original.png")
        if filename == "original.png" and not os.path.exists(orig_save_path):
            pil_img.convert("RGB").save(orig_save_path, "PNG")
            print("📸 [PREPARE]: Святой оригинал сохранен.")

        res_img = pil_img.copy()
        error_msg = None
        
        if "rgba" in requirements:
            res_img = res_img.convert("RGBA")
        
        if "mesh" in requirements:
            json_name = f"{os.path.splitext(filename)[0]}_raw.json"
            mesh_data = SkullaVision.get_universal_mesh(res_img, session_path, json_name)
        
        target_filename = filename
        if "no_bg" in requirements:
            try:
                print("📐 [DEBUG_GEOMETRY]: Запуск удаления фона...")
                res_img = SkullaVision.remove_background(res_img)
                if filename == "original.png":
                    target_filename = "no_bg.png"
                
                orig_w, orig_h = res_img.size
                prod_np = np.array(res_img)
                
                alpha_channel = prod_np[:, :, 3] if prod_np.shape[2] == 4 else cv2.cvtColor(prod_np, cv2.COLOR_RGB2GRAY)
                contours, _ = cv2.findContours(alpha_channel, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                item_x, item_y, item_w, item_h = 0, 0, orig_w, orig_h
                item_cx, item_cy = int(orig_w // 2), int(orig_h // 2)
                
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    x_b, y_b, w_b, h_b = cv2.boundingRect(largest_contour)
                    item_x, item_y = int(x_b), int(y_b)
                    item_w, item_h = int(w_b), int(h_b)
                    item_cx = int(x_b + (w_b // 2))
                    item_cy = int(y_b + (h_b // 2))
                
                meta_geometry = {
                    "original_width": int(orig_w), "original_height": int(orig_h),
                    "item_x": int(item_x), "item_y": int(item_y),
                    "item_width": int(item_w), "item_height": int(item_h),
                    "item_cx": int(item_cx), "item_cy": int(item_cy),
                    "ratio_width": float(round(item_w / orig_w, 4)),
                    "ratio_height": float(round(item_h / orig_h, 4)),
                    "ratio_cx": float(round(item_cx / orig_w, 4)),
                    "ratio_cy": float(round(item_cy / orig_h, 4))
                }
                
                json_geometry_path = os.path.join(session_path, "no_bg.json")
                with open(json_geometry_path, "w", encoding="utf-8") as f_geo:
                    json.dump(meta_geometry, f_geo, ensure_ascii=False, indent=4)
                    
                print(f"📐 [DEBUG_GEOMETRY SUCCESS]: Файл no_bg.json сохранен по пути {json_geometry_path}!")

            except Exception as e:
                print(f"❌ [DEBUG_GEOMETRY CRASH]: Ошибка расчетной геометрии: {e}")
                traceback.print_exc()

        res_img.save(os.path.join(session_path, target_filename), "PNG")
        print(f"✅ [PREPARE]: {target_filename} готов.")
        return True, None






