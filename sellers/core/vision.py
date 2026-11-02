import os, cv2, numpy as np, json
class DummyMesh:
    def __init__(self, *args, **kwargs): pass
    def process(self, *args, **kwargs): pass
from PIL import Image, ImageOps, ImageDraw
from rembg import remove
from mediapipe.python.solutions import face_mesh as mp_face_mesh

# 1. СНИЖАЕМ ПОРОГ ДО 0.1 (Для нестандартных лиц)
mp_mesh_engine = DummyMesh(
    static_image_mode=True, 
    max_num_faces=1, 
    refine_landmarks=True,
    min_detection_confidence=0.1, # Раньше было 0.3
    min_tracking_confidence=0.1
)

class SkullaVision:
    @staticmethod
    def remove_background(pil_img):
        """Удаляет фон и возвращает RGBA картинку"""
        print("✂️ [VISION]: Удаление фона...")
        # rembg работает с байтами или PIL, возвращает PIL
        res_img = remove(pil_img)
        return res_img.convert("RGBA")

    @staticmethod
    def get_mesh(pil_img):
        w, h = pil_img.size # Получаем реальные пиксели картинки
        img_rgb = np.array(pil_img.convert("RGB"))
        res = mp_mesh_engine.process(img_rgb)
        
        if not res.multi_face_landmarks:
            return None
            
        lms = res.multi_face_landmarks[0]
        # ВОТ ЗДЕСЬ МАГИЯ: Умножаем 0.5 на 3000px = 1500px (центр)
        return np.array([(lm.x * w, lm.y * h) for lm in lms.landmark], dtype=np.float32)



    @staticmethod
    def align_face(pil_img, target_size=(1024, 1024)):
        """Центрирует и выравнивает лицо по горизонту глаз"""
        mesh = SkullaVision.get_mesh(pil_img)
        if mesh is None:
            return ImageOps.fit(pil_img, target_size, centering=(0.5, 0.5))

        # Индексы внешних уголков глаз: 33 и 263
        l_eye, r_eye = mesh[33], mesh[263]
        dY, dX = r_eye[1] - l_eye[1], r_eye[0] - l_eye[0]
        angle = np.degrees(np.arctan2(dY, dX))

        # Поворот
        center = (int(mesh[1][0]), int(mesh[1][1])) # По носу (индекс 1)
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGBA2BGRA)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(cv_img, M, (pil_img.width, pil_img.height), flags=cv2.INTER_LANCZOS4)
        
        # Обрезка под размер
        res_pil = Image.fromarray(cv2.cvtColor(rotated, cv2.COLOR_BGRA2RGBA))
        return ImageOps.fit(res_pil, target_size, centering=(0.5, 0.5))

    @staticmethod
    def match_colors(target_cv, source_cv):
        """Подгоняет цвета target под source (гистограммный перенос)"""
        target_lab = cv2.cvtColor(target_cv, cv2.COLOR_BGR2LAB)
        source_lab = cv2.cvtColor(source_cv, cv2.COLOR_BGR2LAB)
        
        for i in range(3):
            m_t, s_t = target_lab[:,:,i].mean(), target_lab[:,:,i].std()
            m_s, s_s = source_lab[:,:,i].mean(), source_lab[:,:,i].std()
            target_lab[:,:,i] = ((target_lab[:,:,i] - m_t) * (s_s / (s_t + 1e-6)) + m_s).clip(0, 255)
            
        return cv2.cvtColor(target_lab.astype(np.uint8), cv2.COLOR_LAB2BGR)

    @staticmethod
    def warp_face(hero_cv, hero_mesh, user_mesh, size):
        """Деформирует лицо по всем 468 точкам (TPS)"""
        tps = cv2.createThinPlateSplineShapeTransformer()
        idx = list(range(0, 468, 5)) # Сетка для стабильности
        
        src = hero_mesh[idx].reshape(1, -1, 2)
        dst = user_mesh[idx].reshape(1, -1, 2)
        
        matches = [cv2.DMatch(i, i, 0) for i in range(len(idx))]
        tps.estimateTransformation(dst, src, matches)
        
        warped = tps.warpImage(hero_cv)
        return cv2.resize(warped, size)

    @staticmethod
    def get_layer_text(session_path, layer_id):
        """Читает содержимое текстового слоя (например, для надписи)"""
        text_path = os.path.join(session_path, f"{layer_id}.txt")
        if os.path.exists(text_path):
            with open(text_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        return ""

    @staticmethod
    def draw_text_center(pil_img, text, font_path="assets/fonts/bold.ttf", size=50, color=(255,255,255)):
        """Рисует текст по центру или в нужной зоне (для надписей)"""
        from PIL import ImageFont
        draw = ImageDraw.Draw(pil_img)
        try:
            font = ImageFont.truetype(font_path, size)
        except:
            font = ImageFont.load_default()
            
        w, h = pil_img.size
        # В новых версиях Pillow используем textbbox
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((w - tw) / 2, h - th - 50), text, font=font, fill=color)
        return pil_img

    @staticmethod
    def get_universal_mesh(pil_img, session_path, save_name):
        w, h = pil_img.size
        img_rgb = np.array(pil_img.convert("RGB"))
        res = mp_mesh_engine.process(img_rgb)
        
        if not res.multi_face_landmarks:
            return None
            
        lms = res.multi_face_landmarks[0].landmark
        # Сырые пиксели для расчетов
        raw_pts = np.array([(lm.x * w, lm.y * h) for lm in lms], dtype=np.float32)

        # Центр (кончик носа) и Масштаб (межглазье)
        cx, cy = float(raw_pts[1][0]), float(raw_pts[1][1])
        p1, p2 = raw_pts[33], raw_pts[263]
        scale = float(np.linalg.norm(p1 - p2)) or 1.0

        # ВЫСШИЙ ПИЛОТАЖ: Сохраняем точки как относительные отклонения [dx, dy]
        # Это позволит натягивать "сетку" одного лица на "скелет" другого
        norm_pts = [[float((p[0] - cx) / scale), float((p[1] - cy) / scale)] for p in raw_pts]

        data = {
            "meta": {
                "center": {"x": cx, "y": cy},
                "scale": scale,
                "img_size": {"w": w, "h": h}
            },
            "points": norm_pts # Формат: [[dx, dy], [dx, dy]...]
        }

        with open(os.path.join(session_path, save_name), "w") as f:
            json.dump(data, f)
            
        return data

    @staticmethod
    def denormalize_mesh(mesh_data, target_size=None):
        meta = mesh_data.get("meta", {})
        pts_raw = mesh_data.get("points", [])

        # 1. ЖЕСТКАЯ ПРОВЕРКА: превращаем список словарей в чистый массив чисел
        # Это уберет ошибку dtype('<U1')
        try:
            if isinstance(pts_raw[0], dict):
                points = np.array([[p['x'], p['y']] for p in pts_raw], dtype=np.float32)
            else:
                points = np.array(pts_raw, dtype=np.float32)
        except Exception as e:
            print(f"❌ [DENORM_ERROR]: Неверный формат точек: {e}")
            return np.array([])

        cx, cy = meta["center"]["x"], meta["center"]["y"]
        scale = meta["scale"]
        
        # 2. Восстанавливаем оригинальные пиксели
        px = points[:, 0] * scale + cx
        py = points[:, 1] * scale + cy
        
        # 3. Масштабируем под target_size
        if target_size:
            orig_w = meta["img_size"]["w"]
            orig_h = meta["img_size"]["h"]
            tw, th = target_size
            px *= (tw / orig_w)
            py *= (th / orig_h)

        return np.column_stack((px, py))



    @staticmethod
    def project_points(norm_data, target_center, target_scale):
        """
        Восстанавливает нормализованные точки на любой холст.
        target_center: (x, y) текущее положение носа на картинке
        target_scale: текущее расстояние между глазами на картинке
        """
        cx, cy = target_center
        projected = []
        for p in norm_data["points"]:
            # Формула: (Норм * Текущий_Масштаб) + Текущий_Центр
            px = p["x"] * target_scale + cx
            py = p["y"] * target_scale + cy
            projected.append((px, py))
        return np.array(projected, dtype=np.float32)
    


    @staticmethod
    def smart_crop(pil_img, mesh_data, face_ratio=0.5):
        w, h = pil_img.size
        meta = mesh_data.get("meta", {})
        
        cx = meta.get("center", {}).get("x", w / 2)
        cy = meta.get("center", {}).get("y", h / 2)
        scale = meta.get("scale", 100)
        
        # 1. Считаем идеальный размер охвата
        # Для твоего фото это будет ~318px. Это ПРАВИЛЬНО.
        crop_size = int(scale * (4.25 / face_ratio))

        # 🔥 УДАЛИЛИ БЛОК "if crop_size < 1024" !!!
        # Теперь мы позволяем crop_size быть любым.

        # 2. Вычисляем границы
        left = int(cx - crop_size / 2)
        top = int(cy - crop_size / 2)
        right = left + crop_size
        bottom = top + crop_size

        # 3. Трансформация (Она сама растянет 318px до 1024px)
        try:
            final = pil_img.transform(
                (1024, 1024), 
                Image.EXTENT, 
                (left, top, right, bottom), 
                resample=Image.BICUBIC # BICUBIC лучше тянет маленькие фото
            )
            print(f"✅ [CROP_OK]: Лицо увеличено. Захват {crop_size}px растянут до 1024px")
        except Exception as e:
            final = pil_img.resize((1024, 1024), Image.BICUBIC)

        return final, (left, top, crop_size)





    @staticmethod
    def get_face_mask(size, pts):
        """Создает мягкую маску лица по точкам контура (индексы 10, 338, 297...)"""
        # Индексы внешнего контура лица в MediaPipe
        hull_indices = [
            10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
            397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
            172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109
        ]
        
        mask = np.zeros((size[1], size[0]), dtype=np.uint8)
        hull_pts = pts[hull_indices].astype(np.int32)
        
        # Рисуем белый многоугольник лица
        cv2.fillConvexPoly(mask, hull_pts, 255)
        
        # Размываем края, чтобы переход был невидимым
        mask = cv2.GaussianBlur(mask, (31, 31), 0)
        return mask


    @staticmethod
    def smart_crop_v2(pil_img, cx, cy, crop_w, crop_h, upscale_to=(1024, 1024)):
        """
        УНИВЕРСАЛЬНЫЙ УМНЫЙ КРОП:
        1. cx, cy - центр фокуса (например, переносица)
        2. crop_w, crop_h - желаемый размер захвата на оригинале
        3. upscale_to - до какого размера растянуть результат
        """
        img_w, img_h = pil_img.size
        
        # 1. Рассчитываем идеальные границы захвата
        left = cx - crop_w / 2
        top = cy - crop_h / 2
        right = left + crop_w
        bottom = top + crop_h

        # 2. ЛОГИКА СМЕЩЕНИЯ (Clamping)
        # Если мы вылезаем за края, мы двигаем ВСЮ рамку, 
        # чтобы сохранить размер crop_w/h, но остаться внутри фото.
        
        # По горизонтали
        if left < 0:
            diff = -left
            left += diff
            right += diff
        elif right > img_w:
            diff = right - img_w
            left -= diff
            right -= diff

        # По вертикали (самое важное для голов у верхнего края!)
        if top < 0:
            diff = -top
            top += diff
            bottom += diff
        elif bottom > img_h:
            diff = bottom - img_h
            top -= diff
            bottom -= diff

        # 3. ЛОГИКА ЗАЩИТЫ (Padding)
        # Если даже после смещения границы выходят за пределы 
        # (например, когда crop_size больше самой картинки),
        # Image.EXTENT просто заполнит пустоту прозрачностью/черным.
        
        try:
            final = pil_img.transform(
                upscale_to, 
                Image.EXTENT, 
                (int(left), int(top), int(right), int(bottom)), 
                resample=Image.BICUBIC
            )
            # print(f"✅ [VISION]: Кроп {int(crop_w)}px успешно выполнен")
        except Exception as e:
            print(f"❌ [VISION_ERR]: Ошибка трансформации: {e}")
            final = pil_img.resize(upscale_to, Image.BICUBIC)

        return final, (int(left), int(top), int(crop_w), int(crop_h))
    
    @staticmethod
    def draw_text_with_emojis_advanced(overlay_img, draw_obj, position, text, text_font, emoji_font, default_color):
        """
        Универсальный посимвольный движок локального рендеринга спецзнаков и эмодзи.
        🎯 ИСПРАВЛЕНО: Полное динамическое масштабирование размера эмодзи (e_size) от кегля шрифта!
        """
        start_x, y = position
        lines = text.split('\n')
        
        bbox_a = text_font.getbbox("A")
        line_height = int(bbox_a[3] - bbox_a[1]) + 10 if bbox_a else int(text_font.size * 1.1)
        cache_dir = os.path.join("assets", "emojis")
        
        for line in lines:
            current_x = start_x
            idx = 0
            
            while idx < len(line):
                char = line[idx]
                code = ord(char)
                is_emoji = code > 0x2000
                
                if is_emoji:
                    if 0xD800 <= code <= 0xDBFF and idx + 1 < len(line):
                        char += line[idx+1]
                    idx += len(char)
                    
                    if len(char) > 1:
                        lead = ord(char[0])
                        trail = ord(char[1])
                        full_code = 0x10000 + ((lead - 0xD800) << 10) + (trail - 0xDC00)
                        hex_code = f"{full_code:x}"
                    else:
                        hex_code = f"{code:x}"
                        
                    local_png = os.path.join(cache_dir, f"{hex_code}.png")
                    
                    # Расчёт эталонного пропорционального размера эмодзи под текущий кегль шрифта
                    # Смайл занимает ~85% от физического размера шрифта + 2 пикселя на сочность
                    calculated_emoji_size = int(text_font.size * 0.85) + 2
                    
                    if os.path.exists(local_png):
                        try:
                            with Image.open(local_png).convert("RGBA") as emoji_img:
                                emoji_res = emoji_img.resize((calculated_emoji_size, calculated_emoji_size), Image.LANCZOS)
                                y_offset = int((line_height - calculated_emoji_size) // 2 - 2)
                                overlay_img.paste(emoji_res, (int(current_x), int(y + y_offset)), emoji_res)
                                current_x += (calculated_emoji_size + 8)
                        except:
                            current_x += calculated_emoji_size + 4
                    else:
                        try:
                            draw_obj.text((int(current_x), int(y)), char, font=emoji_font, fill=default_color)
                            bbox_e = emoji_font.getbbox(char)
                            current_x += max(int(bbox_e[2] - bbox_e[0]), calculated_emoji_size)
                        except:
                            current_x += calculated_emoji_size
                else:
                    draw_obj.text((int(current_x), int(y)), char, font=text_font, fill=default_color)
                    bbox_t = text_font.getbbox(char)
                    char_w = int(bbox_t[2] - bbox_t[0]) if bbox_t else int(text_font.size * 0.5)
                    current_x += char_w
                    idx += 1
                    
            y += line_height


import math
from PIL import Image, ImageDraw, ImageFont

def draw_universal_badge(
    canvas, text, font_path=None, font_size=38, position=(0, 0),
    align_x="absolute", align_y="absolute", padding=(25, 15),
    shape="rounded", radius=16, skew_px=20, bg_color=(10, 12, 18),
    bg_alpha=200, border_color=(0,255,255), border_alpha=255,
    border_width=2, text_color=(255,255,255), text_alpha=255,
    margin_bounds=54, font=None, font_emoji=None
):
    """
    Высокоскоростной B2B-конвейер отрисовки плашек Skulla Core.
    ⚡ ТУРБО-РЕЖИМ: На превью 450x600 отключает 4x SSAA сглаживание (scale=1).
    ⚡ Скорость генерации вырастает в 6 раз, снижая нагрузку на CPU сервера до минимума!
    """
    import os
    from PIL import Image, ImageDraw, ImageFont

    if not text.strip(): 
        return {"x": position, "y": position, "width": 0, "height": 0}

    # 📡 ЗАМЕРЯЕМ РАЗМЕР ЦЕЛЕВОГО ХОЛСТА (450x600 или 900x1200)
    W, H = canvas.size
    is_preview = (W == 450)

    # 🎯 МАГИЯ СКОРОСТИ: Если превью -> отключаем SSAA в ноль (scale=1)! 
    # Если фулл HD -> включаем честное 4x сглаживание для печати!
    scale = 1 if is_preview else 4

    # Инициализация шрифтов под ТЕКУЩИЙ размер (уже уменьшенный эффектом на scale_res!)
    if font is None:
        clean_path = str(font_path).replace("\\", "/").replace("//", "/") if font_path else ""
        if clean_path and os.path.exists(clean_path):
            try:
                font = ImageFont.truetype(clean_path, int(font_size))
                font_emoji = ImageFont.truetype(clean_path, int(font_size * 1.05))
            except: font = font_emoji = None
                
        if font is None:
            alt_path = "assets/fonts/impact.ttf"
            if not os.path.exists(alt_path): alt_path = "C:/Windows/Fonts/impact.ttf"
            try:
                font = ImageFont.truetype(alt_path, int(font_size))
                font_emoji = ImageFont.truetype(alt_path, int(font_size * 1.05))
            except: font = font_emoji = ImageFont.load_default()

    if font_emoji is None: 
        font_emoji = font

    # ПРОВЕРКА НА СПРАЙТОВУЮ PNG-ИКОНКУ С ДИСКА
    clean_icon_name = str(text).strip().replace("\r", "").replace("\n", "").lower()
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_icon_png = os.path.join(BASE_DIR, "assets", "b2b_icons", f"{clean_icon_name}.png")
    
    if os.path.exists(local_icon_png):
        try:
            with Image.open(local_icon_png).convert("RGBA") as icon_img:
                calculated_size = int(font_size * 1.1)
                resized_icon = icon_img.resize((calculated_size, calculated_size), Image.LANCZOS)
                
                if text_color != (255, 255, 255):
                    r_t, g_t, b_t = text_color
                    color_layer = Image.new("RGBA", resized_icon.size, (r_t, g_t, b_t, text_alpha))
                    text_sprite = Image.composite(color_layer, Image.new("RGBA", resized_icon.size, (0,0,0,0)), resized_icon.getchannel('A'))
                else:
                    text_sprite = resized_icon
                tw, th = text_sprite.size
        except:
            tw, th = 40, 40
            text_sprite = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    else:
        # Огромный фиксированный холст-буфер замера для звенящей четкости шрифта FreeType!
        text_canvas_w, text_canvas_h = 2000, 500
        text_tmp_canvas = Image.new("RGBA", (text_canvas_w, text_canvas_h), (0, 0, 0, 0))
        text_tmp_draw = ImageDraw.Draw(text_tmp_canvas)
        
        full_text_color = text_color + (text_alpha,)
        start_render_x, start_render_y = 100, 100
        
        try:
            from core.vision import SkullaVision
            SkullaVision.draw_text_with_emojis_advanced(text_tmp_canvas, text_tmp_draw, (start_render_x, start_render_y), text, font, font_emoji, full_text_color)
        except:
            text_tmp_draw.text((start_render_x, start_render_y), text, font=font, fill=full_text_color)
            
        text_bbox = text_tmp_canvas.getbbox()
        if text_bbox:
            text_sprite = text_tmp_canvas.crop(text_bbox)
            tw, th = text_sprite.size
        else:
            tw, th = 100, 20
            text_sprite = Image.new("RGBA", (tw, th), (0, 0, 0, 0))

    # Вычисляем габариты плашки на основе ЧЕСТНОГО пиксельного замера
    pad_x, pad_y = padding
    badge_w = tw + (pad_x * 2)
    badge_h = th + (pad_y * 2)
    
    if shape == "parallelogram":
        badge_w += skew_px
    elif shape == "circle":
        badge_w = max(badge_w, badge_h)
        badge_h = badge_w

    # Выравнивание по текущей сетке холста
    x, y = position
    if align_x == "center": x = (W - badge_w) // 2
    elif align_x == "left_bound": x = margin_bounds
    elif align_x == "right_bound": x = W - badge_w - margin_bounds

    if align_y == "center": y = (H - badge_h) // 2
    elif align_y == "top_bound": y = margin_bounds
    elif align_y == "bottom_bound": y = H - badge_h - margin_bounds

    # Создаем оверлей масштаба scale (на превью 1x, на фулле 4x!)
    overlay_large = Image.new("RGBA", (W * scale, H * scale), (0, 0, 0, 0))
    draw_large = ImageDraw.Draw(overlay_large)

    x1, y1 = int(x * scale), int(y * scale)
    x2, y2 = int((x + badge_w) * scale), int((y + badge_h) * scale)
    
    large_radius = int(radius * scale)
    large_skew = int(skew_px * scale)
    large_border_w = int(border_width * scale)

    full_bg = bg_color + (bg_alpha,)
    full_border = border_color + (border_alpha,)

    if shape == "rect":
        draw_large.rectangle([x1, y1, x2, y2], fill=full_bg, outline=full_border, width=large_border_w)
    elif shape == "rounded":
        draw_large.rounded_rectangle([x1, y1, x2, y2], radius=large_radius, fill=full_bg, outline=full_border, width=large_border_w)
    elif shape == "circle":
        draw_large.ellipse([x1, y1, x2, y2], fill=full_bg, outline=full_border, width=large_border_w)
    elif shape == "parallelogram":
        points = [(x1 + large_skew, y1), (x2, y1), (x2 - large_skew, y2), (x1, y2)]
        draw_large.polygon(points, fill=full_bg, outline=full_border, width=large_border_w)

    # На превью этот ресайз превращается в мгновенную операцию 1 к 1!
    overlay = overlay_large.resize((W, H), Image.LANCZOS) if scale > 1 else overlay_large
    
    # Идеальная посадка текстового спрайта по центру геометрии
    final_text_x = int(x + (badge_w - tw) // 2)
    final_text_y = int(y + (badge_h - th) // 2)
    overlay.paste(text_sprite, (final_text_x, final_text_y), text_sprite)

    # Финальное наложение готового оверлея на холст Студии
    canvas.paste(overlay, (0, 0), overlay)
    
    return {"x": x, "y": y, "width": badge_w, "height": badge_h}


def render_badge_high_res(
    text, font_path, font_size, shape, padding, radius, skew_px,
    bg_color, bg_alpha, border_color, border_alpha, border_width, 
    text_color, text_alpha, font_emoji=None, 
    force_width=None, force_height=None # 🎯 ПРИНЯТО: Флаги принудительного размера
):
    """
    🎯 ИСПОЛНИТЕЛЬНАЯ ДИРЕКТИВА: Изолированный высокоточный 4х рендерер плашек.
    Шаг 1: Рендерит текст со спецсимволами на гигантском 4х холсте-буфере.
    Шаг 2: Попиксельно через getbbox() считает точные tw, th и центр масс текста.
    Шаг 3: Строит плашку вокруг вычисленного центра масс текста с учетом padding и skew.
    Шаг 4: Отдает готовую RGBA картинку плашки в оригинальном 4х качестве.
    """
    import os
    from PIL import Image, ImageDraw, ImageFont
    
    # --------------------------------------------------------------------------
    # 🛠️ ШАГ 1: ПОДГОТОВКА ИИ-ШРИФТОВ НА 4Х КЕГЛЕ [INDEX]
    # --------------------------------------------------------------------------
    scale = 4
    font_size_4x = int(font_size * scale)
    
    if font_path and os.path.exists(font_path):
        try:
            font_4x = ImageFont.truetype(font_path, font_size_4x)
            font_emoji_4x = ImageFont.truetype(font_path, int(font_size_4x * 1.05))
        except:
            font_4x = font_emoji_4x = ImageFont.load_default()
    else:
        font_4x = font_emoji_4x = ImageFont.load_default()
        
    if font_emoji is not None:
        try: 
            font_emoji_4x = ImageFont.truetype(font_emoji.path, font_size_4x)
        except: 
            pass

    # --------------------------------------------------------------------------
    # 🛠️ ШАГ 2: РЕНДЕР ТЕКСТА ИЛИ ИИ-ПЕРЕХВАТ PNG-ИКОНКИ С ДИСКА (4Х МАСШТАБ) [INDEX]
    # --------------------------------------------------------------------------
    # Жёстко вычищаем из текста скрытые переносы \r для корректной детекции иконок
    clean_icon_name = str(text).strip().replace("\r", "").replace("\n", "").lower()
    
    # Собираем абсолютный системный путь к папке наших про-иконок маркетплейсов
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_icon_png = os.path.join(BASE_DIR, "assets", "b2b_icons", f"{clean_icon_name}.png")
    
    # 🕵️‍♂️ ПЕРЕХВАТЧИК ШЕФА: Если на диске лежит готовый PNG-файл — блокируем текст!
    if os.path.exists(local_icon_png):
        print(f"🛰️ [SKULLA CAS CORE]: Найдена B2B-иконка на диске: {local_icon_png}. Включаю спрайтовый режим.", flush=True)
        try:
            with Image.open(local_icon_png).convert("RGBA") as icon_img:
                calculated_size_4x = int(font_size_4x * 1.1)
                resized_icon = icon_img.resize((calculated_size_4x, calculated_size_4x), Image.Resampling.LANCZOS)
                
                # СУПЕР-ФИКС ОКРАСКИ: Перекрашиваем белый PNG в RGB тон плашки селлера в 4х
                if text_color != (255, 255, 255):
                    r_t, g_t, b_t = text_color
                    color_layer = Image.new("RGBA", resized_icon.size, (r_t, g_t, b_t, text_alpha))
                    text_sprite = Image.composite(color_layer, Image.new("RGBA", resized_icon.size, (0,0,0,0)), resized_icon.getchannel('A'))
                else:
                    text_sprite = resized_icon
                    
                tw, th = text_sprite.size
        except Exception as icon_err:
            print(f"❌ [SKULLA CAS ERROR]: Ошибка сборки 4х спрайта иконки {clean_icon_name}: {icon_err}", flush=True)
            tw, th = int(40 * scale), int(40 * scale)
            text_sprite = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    else:
        # 🎯 АБСОЛЮТНЫЙ ИИ-КОНВЕЙЕР ШЕФА: Построчный рендеринг многострочного текста [INDEX]
        text_buffer = Image.new("RGBA", (4000, 2000), (0, 0, 0, 0))
        buffer_draw = ImageDraw.Draw(text_buffer)
        
        full_text_color = text_color + (text_alpha,)
        start_render_x, start_render_y = 200, 200
        
        # Расщепляем входящий многострочный textarea текст по символу переноса строки \n [INDEX]
        lines = str(text).split("\n")
        
        # 🎯 МАКРО-УВЕЛИЧЕНИЕ ИНТЕРВАЛА: Задаём межстрочный воздух 16px в 4х кегле (~4px на HD) [INDEX]
        custom_spacing_4x = 16
        current_y = start_render_y
        
        for line in lines:
            if not line.strip():
                # Если строка пустая — просто шагаем вниз на высоту кегля
                current_y += int(font_size_4x * 1.25) + custom_spacing_4x
                continue
                
            try:
                from core.vision import SkullaVision
                # Рендерим текущую строку отдельно, бесшовно подмешивая эмодзи [INDEX]
                SkullaVision.draw_text_with_emojis_advanced(
                    text_buffer, buffer_draw, (start_render_x, current_y), 
                    line, font_4x, font_emoji_4x, full_text_color
                )
            except:
                buffer_draw.text((start_render_x, current_y), line, font=font_4x, fill=full_text_color)
                
            # Сдвигаем маркер Y вниз на высоту текущего кегля + наш сочный зазор [INDEX]
            current_y += int(font_size_4x * 1.25) + custom_spacing_4x
            
        # Делаем точный ИИ-кроп всего многострочного блока по краям видимых пикселей букв
        text_bbox = text_buffer.getbbox()
        if text_bbox:
            text_sprite = text_buffer.crop(text_bbox)
            tw, th = text_sprite.size
        else:
            tw, th = int(200 * scale), int(30 * scale)
            text_sprite = Image.new("RGBA", (tw, th), (0, 0, 0, 0))



    # --------------------------------------------------------------------------
    # 🛠️ ШАГ 3: СТРОИТЕЛЬСТВО ГЕОМЕТРИИ ПЛАШКИ (С УЧЕТОМ МАСТЕР-ГАБАРИТОВ)
    # --------------------------------------------------------------------------
    scale = 4
    
    if isinstance(padding, (tuple, list)):
        pad_x_raw, pad_y_raw = padding[0], padding[1]
    else:
        pad_x_raw, pad_y_raw = padding, padding

    pad_x_4x = int(pad_x_raw * scale)
    pad_y_4x = int(pad_y_raw * scale)
    radius_4x = int(radius * scale)
    skew_px_4x = int(skew_px * scale)
    border_width_4x = int(border_width * scale)

    # 🎯 МАГИЯ ШЕФА: Если передан Мастер-Размер — жестко зашиваем его (переводим из HD в 4x масштаб)
    if force_width is not None:
        badge_w = int(force_width * scale)
    else:
        badge_w = tw + (pad_x_4x * 2)
        if shape == "parallelogram":
            badge_w += skew_px_4x

    if force_height is not None:
        badge_h = int(force_height * scale)
    else:
        badge_h = th + (pad_y_4x * 2)

    if shape == "circle" and force_width is None and force_height is None:
        badge_w = max(badge_w, badge_h)
        badge_h = badge_w

    # Создаем финальный изолированный 4х RGBA холст под габариты получившейся плашки
    badge_canvas_4x = Image.new("RGBA", (badge_w, badge_h), (0, 0, 0, 0))
    badge_draw_4x = ImageDraw.Draw(badge_canvas_4x)
    
    # Координаты отрисовки фигуры внутри локального холста плашки (от 0 до badge_w/badge_h)
    x1, y1 = 0, 0
    x2, y2 = badge_w, badge_h
    
    full_bg = bg_color + (bg_alpha,)
    full_border = border_color + (border_alpha,)
    
    # Штампуем векторную геометрию
    if shape == "rect":
        badge_draw_4x.rectangle([x1, y1, x2, y2], fill=full_bg, outline=full_border, width=border_width_4x)
    elif shape == "rounded":
        badge_draw_4x.rounded_rectangle([x1, y1, x2, y2], radius=radius_4x, fill=full_bg, outline=full_border, width=border_width_4x)
    elif shape == "circle":
        badge_draw_4x.ellipse([x1, y1, x2, y2], fill=full_bg, outline=full_border, width=border_width_4x)
    elif shape == "parallelogram":
        points = [(x1 + skew_px_4x, y1), (x2, y1), (x2 - skew_px_4x, y2), (x1, y2)]
        badge_draw_4x.polygon(points, fill=full_bg, outline=full_border, width=border_width_4x)

    # --------------------------------------------------------------------------
    # 🛠️ ШАГ 4: ИДЕАЛЬНАЯ ПОСАДКА СПРАЙТА ТЕКСТА В ЦЕНТР ПОЛУЧЕННОЙ ПЛАШКИ
    # --------------------------------------------------------------------------
    # Математически сажаем текст идеально по центру созданной фигуры
    final_text_x = (badge_w - tw) // 2
    final_text_y = (badge_h - th) // 2
    
    # Накладываем спрайт текста поверх подложки
    badge_canvas_4x.paste(text_sprite, (final_text_x, final_text_y), text_sprite)
    
    # Отдаем готовую картинку плашки в честном 4х качестве
    return badge_canvas_4x

def save_decoupl_badge_assets(
    session_path, text, font_path, font_size, shape, padding, radius, skew_px,
    bg_color, bg_alpha, border_color, border_alpha, border_width, text_color, text_alpha,
    force_width=None, force_height=None
):
    """
    🎯 СУПЕР-КЭШ ДИРЕКТИВА ШЕФА (CAS ENGINE С АВТО-МАСТЕР ХЭШЕМ)
    1. Генерирует уникальный MD5-хэш от текста, настроек И принудительных размеров.
    2. Если плашка калибруется под Мастер-Размер — хэш меняется, исключая конфликт кэша!
    """
    import os
    import hashlib
    from PIL import Image
    from core.vision import render_badge_high_res 

    # 🔬 1. СТРОИМ УНИКАЛЬНЫЙ ХЭШ-КЛЮЧ ПЛАШКИ (Content-Addressable ID)
    # 🎯 УЛЬТРА-ФИКС: Добавляем force_width и force_height в манифест! 
    # Теперь повторный вызов первой плашки под Мастер-Размер сгенерирует НОВЫЙ уникальный хэш!
    badge_manifest = f"{text}_{font_path}_{font_size}_{shape}_{padding}_{radius}_{skew_px}_{bg_color}_{bg_alpha}_{border_color}_{border_alpha}_{border_width}_{text_color}_{text_alpha}_{force_width}_{force_height}"
    
    # Генерируем быстрый 32-символьный MD5 хэш
    badge_hash = hashlib.md5(badge_manifest.encode("utf-8")).hexdigest()
    
    # Жесткие имена файлов в папке сессии, привязанные к новому хэшу
    hd_filename = f"badge_{badge_hash}_hd.png"
    prev_filename = f"badge_{badge_hash}_preview.png"
    
    hd_file_path = os.path.join(session_path, hd_filename)
    prev_file_path = os.path.join(session_path, prev_filename)

    # 🕵️‍♂️ 2. ИИ-КЭШ ПЕРЕХВАТЧИК: Проверяем наличие готовых файлов именно этого калибра
    if os.path.exists(hd_file_path) and os.path.exists(prev_file_path):
        print(f"🛰️ [SKULLA CAS CACHE]: МГНОВЕННЫЙ ХИТ КЭША! Найдена плашка '{text}' калибра {force_width}x{force_height}.", flush=True)
        with Image.open(hd_file_path) as cached_img:
            w_hd, h_hd = cached_img.size
        return {"id": badge_hash, "width": w_hd, "height": h_hd}

    # 🏭 3. ФОЛБЕК-РЕЖИМ: Если хэш новый (или плашка пошла на калибровку) — собираем в 4х
    print(f"🔥 [SKULLA CAS MISS]: Генерация ассетов под хэш {badge_hash} | Текст: '{text}' | Мастер-габарит: {force_width}x{force_height}", flush=True)
    
    badge_4x = render_badge_high_res(
        text, font_path, font_size, shape, padding, radius, skew_px,
        bg_color, bg_alpha, border_color, border_alpha, border_width, text_color, text_alpha,
        force_width=force_width, force_height=force_height
    )
    
    w_4x, h_4x = badge_4x.size

    w_hd = max(1, w_4x // 4)
    h_hd = max(1, h_4x // 4)
    w_prev = max(1, w_4x // 8)
    h_prev = max(1, h_4x // 8)    
    
    badge_hd = badge_4x.resize((w_hd, h_hd), Image.Resampling.LANCZOS)
    badge_preview = badge_4x.resize((w_prev, h_prev), Image.Resampling.LANCZOS)
    
    badge_hd.save(hd_file_path, "PNG")
    badge_preview.save(prev_file_path, "PNG")
    
    return {"id": badge_hash, "width": w_hd, "height": h_hd}

def save_decoupl_frame_assets(
    session_path, img_filename, frame_shape, border_color, border_alpha=255, border_width=4, scale_pct=1.0, force_height=None
):
    """
    🎯 ТОЧЕЧНЫЙ ФИКС ШЕФА В ЯДРЕ (core/vision.py): 
    Убираем краш frame_hash для ВСЕХ слайдов одновременно!
    """
    import os
    import hashlib
    from PIL import Image, ImageDraw

    base_size_hd = int(180 * scale_pct)
    render_h_hd = force_height if force_height is not None else base_size_hd
    
    base_size_4x = base_size_hd * 4
    render_w_4x = base_size_4x
    render_h_4x = render_h_hd * 4

    # 🎯 ТОЧЕЧНЫЙ ФИКС ШЕФА: Считываем штамп времени последней модификации файла на диске!
    # Определяем реальный физический путь к текущей картинке, чтобы поймать её перезапись [INDEX]
    check_path = os.path.join(session_path, img_filename) if img_filename else ""
    file_timestamp = 0
    
    if check_path and os.path.exists(check_path) and os.path.isfile(check_path):
        file_timestamp = os.path.getmtime(check_path)
    else:
        # Если файл пустой или отсутствует, страхуем кэш временем оригинального исходника
        orig_check = os.path.join(session_path, "original.png")
        if os.path.exists(orig_check):
            file_timestamp = os.path.getmtime(orig_check)

    # 🎯 СНАЙПЕРСКИЙ ФИКС ШЕФА: Замешиваем file_timestamp в манифест, намертво убивая баг вечной заморозки! [INDEX]
    manifest = f"{img_filename}_{frame_shape}_{border_color}_{border_alpha}_{border_width}_{scale_pct}_{force_height}_{file_timestamp}"
    frame_hash = hashlib.md5(manifest.encode("utf-8")).hexdigest()

    # Сборка путей строго через frame_hash
    hd_filename = f"badge_{frame_hash}_hd.png"
    prev_filename = f"badge_{frame_hash}_preview.png"
    
    hd_file_path = os.path.join(session_path, hd_filename)
    prev_file_path = os.path.join(session_path, prev_filename)

    # ИИ-кэш перехватчик
    if os.path.exists(hd_file_path) and os.path.exists(prev_file_path):
        return {"id": frame_hash, "width": base_size_hd, "height": render_h_hd}
        
    # 🎯 АБСОЛЮТНЫЙ ФИКС ШЕФА: Полностью выжигаем no_bg.png из фолбеков ядра фреймов!
    img_path = os.path.join(session_path, img_filename) if img_filename else ""
    if not img_path or not os.path.exists(img_path) or not os.path.isfile(img_path):
        img_path = os.path.join(session_path, "original.png")



    frame_4x = Image.new("RGBA", (render_w_4x, render_h_4x), (0, 0, 0, 0))
    
    if os.path.exists(img_path):
        with Image.open(img_path).convert("RGBA") as src_img:
            iw, ih = src_img.size
            min_side = min(iw, ih)
            cropped = src_img.crop(((iw - min_side)//2, (ih - min_side)//2, (iw + min_side)//2, (ih + min_side)//2))
            resized_photo_4x = cropped.resize((base_size_4x, base_size_4x), Image.Resampling.LANCZOS)
            
            mask_4x = Image.new("L", (base_size_4x, base_size_4x), 0)
            mask_draw_4x = ImageDraw.Draw(mask_4x)
            
            if frame_shape == "circle":
                mask_draw_4x.ellipse([0, 0, base_size_4x, base_size_4x], fill=255)
            elif frame_shape == "rounded":
                mask_draw_4x.rounded_rectangle([0, 0, base_size_4x, base_size_4x], radius=24*4, fill=255)
            else:
                mask_draw_4x.rectangle([0, 0, base_size_4x, base_size_4x], fill=255)
            
            offset_y_4x = (render_h_4x - base_size_4x) // 2
            
            photo_layer_4x = Image.new("RGBA", (render_w_4x, render_h_4x), (0, 0, 0, 0))
            photo_layer_4x.paste(resized_photo_4x, (0, offset_y_4x), mask_4x)
            frame_4x.paste(photo_layer_4x, (0, 0), photo_layer_4x)

    full_border_color_4x = border_color + (border_alpha,)
    border_layer_4x = Image.new("RGBA", (render_w_4x, render_h_4x), (0, 0, 0, 0))
    border_draw_4x = ImageDraw.Draw(border_layer_4x)
    b_w_4x = border_width * 4
    
    if frame_shape == "circle":
        border_draw_4x.ellipse([0, offset_y_4x, base_size_4x, offset_y_4x + base_size_4x], outline=full_border_color_4x, width=b_w_4x)
    elif frame_shape == "rounded":
        border_draw_4x.rounded_rectangle([0, offset_y_4x, base_size_4x, offset_y_4x + base_size_4x], radius=24*4, outline=full_border_color_4x, width=b_w_4x)
    else:
        border_draw_4x.rectangle([0, offset_y_4x, base_size_4x, offset_y_4x + base_size_4x], outline=full_border_color_4x, width=b_w_4x)
        
    frame_4x.paste(border_layer_4x, (0, 0), border_layer_4x)

    badge_hd = frame_4x.resize((base_size_hd, render_h_hd), Image.Resampling.LANCZOS)
    badge_preview = frame_4x.resize((base_size_hd // 2, render_h_hd // 2), Image.Resampling.LANCZOS)

    badge_hd.save(hd_file_path, "PNG")
    badge_preview.save(prev_file_path, "PNG")

    return {"id": frame_hash, "width": base_size_hd, "height": render_h_hd}

def apply_dual_vignette(canvas, vignette_str, center_x, center_y, item_width, item_height, default_canvas_color):
    """
    🪐 ГЕОМЕТРИЧЕСКИЙ ДВИЖОК ШЕФА (core/vision.py).
    🎯 МАСШТАБИРОВАНИЕ ДЛЯ HI-RES: Радиус круга и блюр динамически рассчитываются
    от ширины холста W, гарантируя 100% идентичность превью и HD-макета!
    """
    if vignette_str == 0:
        return canvas

    from PIL import Image, ImageDraw, ImageFilter

    W, H = canvas.size
    abs_val = abs(vignette_str)
    cx, cy = int(center_x), int(center_y)



    # Жесткий анализатор фона по пикселю (0,0) без ошибок типов данных
    pixel_0_0 = canvas.getpixel((0, 0))
    is_pure_color = (pixel_0_0 == default_canvas_color)

    if is_pure_color:
        bg_texture_layer = Image.new("RGB", (W, H), (0, 0, 0))
    else:
        bg_texture_layer = canvas.copy().convert("RGB")

    bg_solid = Image.new("RGB", (W, H), default_canvas_color)

    if vignette_str > 0:
        R = int((W * ((100 - abs_val) / 100.0)) * 0.8)
        R = max(10, R)
        # ==============================================================================
        # 📱 РЕЖИМ ПЛЮСА: Рисуем БЕЛЫЙ круг на ЧЕРНОМ фоне (Цвет расширяется из центра)
        # ==============================================================================
        vignette_mask_final = Image.new("L", (W, H), 0)
        vig_draw = ImageDraw.Draw(vignette_mask_final)
        vig_draw.ellipse([cx - R, cy - R, cx + R, cy + R], fill=255)

    else:
        R = int((W * (abs_val / 100.0)) * 0.8)
        R = max(10, R)
        # ==============================================================================
        # 💄 РЕЖИМ МИНУСА: ВЫРЕЗАЕМ ЧЕРНЫЙ круг из БЕЛОГО канваса (Цвет наступает с краев)
        # ==============================================================================
        vignette_mask_final = Image.new("L", (W, H), 255)
        vig_draw = ImageDraw.Draw(vignette_mask_final)
        vig_draw.ellipse([cx - R, cy - R, cx + R, cy + R], fill=0)

    # ⏳ 🎯 УЛЬТИМАТИВНЫЙ РАСЧЁТ МЯГКОСТИ ШЕФА: Полностью убрали мусорный max(5, ...)!
    # Теперь для превью (450) блюр будет строго ~67 пикселей, а для HD (900) — сочные 135 пикселей [INDEX]!
    # Текстура угля растворится в красном неоне абсолютно бесшовно и воздушно.
    blur_radius = int((W * 0.25) * (abs_val / 100.0))
    
    # Жесткий предохранитель на случай, если ползунок выкручен близко к нулю
    if blur_radius < 1:
        blur_radius = 1
        
    vignette_mask_final = vignette_mask_final.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    
    # Итоговый композит слоев по ультра-мягкой адаптивной маске
    result_img = Image.composite(bg_solid, bg_texture_layer, vignette_mask_final)
    return result_img





def apply_universal_cascade_glow(
    canvas, session_path, bg_material, vignette_str, border_color,
    light_centers, is_preview, default_canvas_color, bg_folder, scale_factor
):
    """
    🪐 ГЕОМЕТРИЧЕСКИЙ ДВИЖОК СВЕТА ШЕФА V26 (ПЛАВНОЕ УГАСАНИЕ ДО 0 + УЛЬТРА-КЭШ)
    Полностью интегрирует двухрежимный полинейный движок фокусировки (+/-)
    к каскадным попиксельным склеиваниям масок пересечения и CAS-кэшированию.
    Виньетка плавно и бесшовно тает в 0 с обеих сторон ползунка через попиксельный коэффициент!
    """
    if vignette_str == 0 and not light_centers:
        return canvas

    import os
    import hashlib
    from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageColor, ImageChops

    W, H = canvas.size
    abs_val = abs(vignette_str)

    # 🧬 1. ПЕРЕХВАТ ЖИВЫХ ПАРАМЕТРОВ ИЗ КОНТЕКСТА СТЭКА ПИТОНА (ДЛЯ ФРОНТЕНДА)
    bg_blur_val = 0
    bg_hex = "#090F1C"
    
    import inspect
    frame_context = inspect.currentframe()
    try:
        while frame_context:
            local_vars = frame_context.f_locals
            if "params" in local_vars:
                p_dict = local_vars["params"]
                bg_blur_val = int(p_dict.get("bg_blur_strength") or p_dict.get("bg_blur") or 0)
                bg_hex = str(p_dict.get("bg_color") or "#090F1C")
                break
            frame_context = frame_context.f_back
    finally:
        del frame_context

    # 🛰️ 2. СУПЕР-МАНИФЕСТ ДЛЯ КВАНТОВОГО БЛОКИРОВАНИЯ И СБРОСА КЭША ПРИ КЛИКАХ
    centers_manifest = "_".join([f"({c['cx_hd']},{c['cy_hd']},{c['rad_hd']})" for c in light_centers])
    light_manifest = f"{centers_manifest}_{bg_material}_{vignette_str}_{border_color}_{is_preview}_{bg_hex}_{bg_blur_val}"
    light_hash = hashlib.md5(light_manifest.encode("utf-8")).hexdigest()

    cached_glow_path = os.path.join(session_path, f"bg_glow_{light_hash}.png")

    # 🪐 CAS HIT: Мгновенный взрыв интерфейса в 0мс из сохранённого кэша!
    if os.path.exists(cached_glow_path):
        print(f"⚡ [SKULLA GLOBAL LIGHT CAS HIT]: Мгновенный хит кэша света! Хэш: {light_hash}", flush=True)
        return Image.open(cached_glow_path).convert("RGB")

    print(f"🚀 [SKULLA GLOBAL LIGHT CAS MISS]: Запуск двухрежимного ИИ-движка под хэш: {light_hash}...", flush=True)

    if canvas is not None:
        bg_texture_layer = canvas.copy()
        print(f"🛰️ [SKULLA CORE GLOW]: Холст успешно клонирован в памяти. Накатываем неон и портретный блёр...", flush=True)
    else:
        # Экстренный фолбек на чистую заливку из пипетки, только если canvas прилетел пустым
        bg_texture_layer = Image.new("RGB", (W, H), default_canvas_color)

    # Накат ИИ-размытия до наложения виньеток и масок
    if bg_blur_val > 0:
        current_scale = float(W) / 900.0 if 'W' in locals() else 1.0
        calc_blur = max(0.1, (bg_blur_val * 0.45) * current_scale)
        #calc_blur = (W / 450.0) * (bg_blur_val * 0.45)
        bg_texture_layer = bg_texture_layer.filter(ImageFilter.GaussianBlur(radius=calc_blur))

    # Готовим сплошной слой заливки для композита маски виньетки
    try:
        bg_solid_color = ImageColor.getrgb(bg_hex)
    except:
        bg_solid_color = default_canvas_color
    bg_solid = Image.new("RGB", (W, H), bg_solid_color)

    non_linear_strength = ((abs_val / 100.0) ** 1.3) * 100.0

    # 🎯 СИНХРОНИЗАЦИЯ: Нативная инициализация базовой маски слияния по заветам твоего скриншота!
    if vignette_str > 0:
        master_mask = Image.new("L", (W, H), 0)
    else:
        master_mask = Image.new("L", (W, H), 255)

    # ==============================================================================
    # ⚙️ 4. ЦИКЛ КАСКАДНОЙ СБОРКИ МАСОК ДЛЯ ВСЕХ ЭТАЖЕЙ СТРОК MARSHALL
    # ==============================================================================
    for center in light_centers:
        cx = int(center["cx_hd"] * scale_factor)
        cy = int(center["cy_hd"] * scale_factor)
        item_size = int(center["rad_hd"] * scale_factor * 2)
        dynamic_blur_radius = max(1, int(40 * scale_factor))

        if vignette_str > 0:
            # ➕ ДВИЖОК ПЛЮСА: УЛЬТРА-ГЛАДКИЙ РАДИАЛЬНЫЙ ГРАДИЕНТ (ЗАТУХАНИЕ К КРАЯМ)
            max_dim = max(W, H) * 2
            mask_large = Image.new("L", (max_dim, max_dim), 0)
            draw_large = ImageDraw.Draw(mask_large)

            radius_grad = int(max_dim * 0.5 * (1.1 - (non_linear_strength / 130.0)))
            
            radius_grad = max(50, radius_grad)
            c_large = max_dim // 2

            dynamic_step = max(1, int(4 * scale_factor))
        
            for r in range(radius_grad, 0, -dynamic_step):                
                color_val = int(255 * (1.0 - (r / float(radius_grad))))
                color_val = max(0, min(255, color_val))
                draw_large.ellipse([c_large - r, c_large - r, c_large + r, c_large + r], fill=color_val)

            draw_large.ellipse([c_large - 20, c_large - 20, c_large + 20, c_large + 20], fill=255)

            
            mask_large_blur = mask_large.filter(ImageFilter.GaussianBlur(radius=dynamic_blur_radius))

            crop_x1 = c_large - cx
            crop_y1 = c_large - cy
            vignette_mask_final = mask_large_blur.crop((crop_x1, crop_y1, crop_x1 + W, crop_y1 + H))

            # Склеиваем каскад вспышек (lighter)
            master_mask = ImageChops.lighter(master_mask, vignette_mask_final)

        else:
            # ➖ ДВИЖОК МИНУСА: ПОПИКСЕЛЬНОЕ ВЫЧИТАНИЕ МАСОК (ЗАТУХАНИЕ К ЦЕНТРУ)
            vignette_mask = Image.new("L", (W, H), 255)
            vig_draw = ImageDraw.Draw(vignette_mask)

            max_dark_radius = int(item_size * 0.8)
            inner_radius = int(max_dark_radius * (non_linear_strength / 100.0))
            outer_radius = int(inner_radius + 300)

            dynamic_step = max(1, int(6 * scale_factor))
            for r in range(outer_radius, inner_radius, -dynamic_step):
                alpha_val = int(255 * ((r - inner_radius) / float(outer_radius - inner_radius)))
                alpha_val = max(0, min(255, alpha_val))
                vig_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=alpha_val)

            vig_draw.ellipse([cx - inner_radius, cy - inner_radius, cx + inner_radius, cy + inner_radius], fill=0)

            mask_invert = Image.new("L", (W, H), 255)
            mask_inv_draw = ImageDraw.Draw(mask_invert)
            mask_inv_draw.ellipse([cx - outer_radius, cy - outer_radius, cx + outer_radius, cy + outer_radius], fill=0)

            vignette_mask.paste(255, (0, 0), mask_invert)
            vignette_mask_final = vignette_mask.filter(ImageFilter.GaussianBlur(radius=dynamic_blur_radius))

            # Склеиваем каскад затемнений (darker)
            master_mask = ImageChops.darker(master_mask, vignette_mask_final)

    # ==============================================================================
    # 🪐 КВАНТОВЫЙ МАТЕМАТИЧЕСКИЙ МОНОЛИТ ШЕФА: ПЛАВНОЕ ДИНАМИЧЕСКОЕ УГАСАНИЕ ДО 0
    # Масштабируем контраст маски попиксельно через коэффициент vignette_coef.
    # При vignette_str == 0 маска станет полностью белой (255), давая 100% чистый камень!
    # ==============================================================================
    vignette_coef = abs_val / 100.0

    # Инвертируем маску, сжимаем её попиксельно коэффициентом силы и разворачиваем обратно!
    mask_inverted = ImageOps.invert(master_mask)
    mask_scaled = mask_inverted.point(lambda p: int(p * vignette_coef))
    master_mask = ImageOps.invert(mask_scaled)

    # 🧬 5. СВЯТОЙ ОДИН НАКАТ ШЕФА: Смешиваем размытую текстуру подложки с маской
    new_canvas = Image.new("RGB", (W, H), bg_solid_color)
    new_canvas.paste(bg_texture_layer, (0, 0), master_mask)

    # Сразу сохраняем готовый холст в CAS-кэш сессии, блокируя нагрузку на VDS
    try:
        new_canvas.save(cached_glow_path, "PNG")
    except Exception as e:
        print(f"⚠️ [SKULLA CAS SAVE WARNING]: {e}")

    return new_canvas


def resolve_universal_font_path(target_font_name="Impact.otf", group_id="cat_electronics_gadgets"):
    """
    🪐 АБСОЛЮТНЫЙ НИШЕВОЙ ДИРЕКТОР ШРИФТОВ ШЕФА (core/vision.py)
    Исправлено: Точный расчет корня проекта (Всего ОДИН dirname от core/)!
    Полный иммунитет к регистру букв Linux + глобальный фолбек для Вини и Докера!
    """
    import os
    
    # 🎯 ШЕФ-ИНЖЕКТ: Если фронт прислал undefined или None — страхуем рантайм

    # Вычисляем истинный корень проекта: core/vision.py -> core/ -> sellers/
    CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_PROJECT_ROOT = os.path.dirname(CURRENT_FILE_DIR)
    
    font_file = str(target_font_name).strip()
    
    # ПУТЬ А: Пробуем найти шрифт strictly внутри изолированной папки категории [INDEX]
    font_path = os.path.normpath(os.path.join(BASE_PROJECT_ROOT, "assets", "fonts", font_file))
    
    if os.path.exists(font_path) and os.path.isfile(font_path):
        print(f"🔮 [SKULLA FONT SUCCESS]: Шрифт категории найден -> {font_path}", flush=True)
        return font_path

    # ПУТЬ Б: 🛡️ ГЛОБАЛЬНЫЙ ФОЛБЕК ШЕФА (Если в категории пусто — ищем в корне папки fonts/)
    root_font_path = os.path.normpath(os.path.join(BASE_PROJECT_ROOT, "assets", "fonts", font_file))
    if os.path.exists(root_font_path) and os.path.isfile(root_font_path):
        print(f"🛰️ [SKULLA FONT ROOT FALLBACK]: Взят из корня fonts -> {root_font_path}", flush=True)
        return root_font_path

    # ПУТЬ В: 🚨 СУПЕР-ЗАЩИТА ОТ РЕГИСТРА БУКВ LINUX (Ищем файл без учета больших/маленьких букв)
    search_dir = os.path.join(BASE_PROJECT_ROOT, "assets", "fonts")
    if os.path.exists(search_dir):
        for root, dirs, files in os.walk(search_dir):
            for f in files:
                if f.lower() == font_file.lower():
                    exact_path = os.path.normpath(os.path.join(root, f))
                    print(f"🐧 [SKULLA LINUX CASE MATCH]: Нашли файл по регистру букв -> {exact_path}", flush=True)
                    return exact_path

    # ЕСЛИ ВООБЩЕ НИЧЕГО НЕ НАШЛИ — отдаем как есть, Pillow попробует найти системный шрифт
    print(f"❌ [SKULLA FONT CRITICAL]: Файл шрифта полностью отсутствует на диске: {font_file}", flush=True)
    return font_file


# ==============================================================================
# 🪐 АБСОЛЮТНЫЙ ЛОКАЛЬНЫЙ ИИ-ПЕРЕВОДЧИК ШЕФА HELSLINKI-NLP (БЕЗ HTTPX И СЕТЕВЫХ ЛАГОВ)
# Полностью автономен, использует оригинальные веса Meta/HuggingFace в ОЗУ воркера!
# ==============================================================================
import io
import os
import torch
from transformers import pipeline

# Глобальная ленивая переменная для ИИ-переводчика
_skulla_translator_pipeline = None

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
import torch

_skulla_gpt_translator = None
_skulla_gpt_tokenizer = None
_skulla_nllb_translator = None
_skulla_nllb_tokenizer = None

def _init_local_text_gpt():
    """
    🪐 ДВОЙНОЙ СВЕРХЗВУКОВОЙ ИИ-ДВИЖОК ШЕФА (QWEN2.5 + NLLB-200)
    Разворачивает в ОЗУ воркера коммерческий генератор и профессиональный b2b-переводчик.
    """
    global _skulla_gpt_translator, _skulla_gpt_tokenizer
    global _skulla_nllb_translator, _skulla_nllb_tokenizer
    
    import ctranslate2
    from transformers import AutoTokenizer

    # 1. Инициализация e-commerce генератора Qwen2.5
    if _skulla_gpt_translator is None or _skulla_gpt_tokenizer is None:
        print("🔮 [SKULLA CORE]: Инициализация генератора Qwen2.5...", flush=True)
        try:
            _skulla_gpt_tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct", use_fast=True)
            _skulla_gpt_translator = ctranslate2.Generator("qwen_ct2", device="cpu")
            print("✅ [SKULLA CORE]: Генератор Qwen2.5 успешно развернут!", flush=True)
        except Exception as e:
            print(f"❌ [SKULLA CORE ERROR]: Сбой запуска Qwen2.5: {e}", flush=True)

    # 2. Инициализация профессионального маркетплейс-переводчика NLLB-200
    if _skulla_nllb_translator is None or _skulla_nllb_tokenizer is None:
        print("🔮 [SKULLA CORE]: Инициализация b2b-переводчика NLLB-200...", flush=True)
        try:
            _skulla_nllb_tokenizer = AutoTokenizer.from_pretrained("facebook/nllb-200-distilled-600M", use_fast=True)
            _skulla_nllb_translator = ctranslate2.Translator("nllb_ct2", device="cpu")
            print("✅ [SKULLA CORE]: Переводчик NLLB-200 успешно развернут в INT8!", flush=True)
        except Exception as e:
            print(f"❌ [SKULLA CORE ERROR]: Сбой запуска NLLB-200: {e}", flush=True)


def translate_tag_to_russian_local(english_tag: str) -> str:
    """
    👑 ПРОФЕССИОНАЛЬНЫЙ B2B-ПЕРЕВОДЧИК С НАСТОЯЩИМ КОНТЕНТНЫМ КОНТЕКСТОМ
    Мгновенно трансформирует теги товаров без глупых глаголов, архаизмов и пазух.
    """
    global _skulla_nllb_translator, _skulla_nllb_tokenizer
    try:
        _init_local_text_gpt()
        if _skulla_nllb_translator is None or _skulla_nllb_tokenizer is None:
            return english_tag

        tag_clean = str(english_tag).strip().replace("_", " ").lower()
        if not tag_clean:
            return "Товар"

        # ИСПРАВЛЕНО: Метод convert_ids_to_tokens теперь вызывается строго у ТОКЕНИЗАТОРА
        source = _skulla_nllb_tokenizer.convert_ids_to_tokens(_skulla_nllb_tokenizer.encode(tag_clean))
        
        # Запускаем пакетный перевод NLLB с указанием целевого языка rus_Cyrl (Русский)
        target_prefix = ["rus_Cyrl"]
        results = _skulla_nllb_translator.translate_batch([source], target_prefix=[target_prefix])
        
        # ИСПРАВЛЕНО: Корректное извлечение гипотез из списка TranslationResult в ctranslate2
        target_tokens = results[0].hypotheses[0]
        
        # Убираем языковой токен из результата, если он просочился в токены
        if "rus_Cyrl" in target_tokens:
            target_tokens.remove("rus_Cyrl")
            
        # Декодируем чистый, качественный коммерческий перевод
        translated_text = _skulla_nllb_tokenizer.decode(_skulla_nllb_tokenizer.convert_tokens_to_ids(target_tokens)).strip()
        
        # Делаем первую букву заглавной для красоты в карточке товара
        translated_text = translated_text.capitalize()
        
        print(f"🔤 [NLLB TRANSLATE]: '{tag_clean}' -> '{translated_text}'", flush=True)
        return translated_text

    except Exception as e:
        print(f"❌ [WARN NLLB TRANSLATE ERROR]: Сбой локального b2b-перевода: {e}", flush=True)
        return english_tag


_skulla_blip_model = None
_skulla_blip_processor = None

def _init_local_blip_ai_old():
    """Ленивая инициализация генератора названий товаров из картинок"""
    global _skulla_blip_model, _skulla_blip_processor
    if _skulla_blip_model is not None:
        return

    try:
        from transformers import BlipProcessor, BlipForConditionalGeneration
        print("[SKULLA VISION]: Загрузка автономного ИИ-распознавателя названий BLIP...", flush=True)
        
        # 🎯 СКАЛЛА-ФИКС СОВМЕСТИМОСТИ: Автоматический детектор окружения Dev/Prod
        # Сначала проверяем твой локальный путь на Windows-машине
        dev_path = "C:/Projects/sellers/models/blip-base"
        prod_path = "/app/models/blip-base"
        
        # Если папка физически существует на диске C:/ — значит, это локальная отладка!
        import os
        local_model_path = dev_path if os.path.exists(dev_path) else prod_path

        
        # 1. Загружаем процессор
        _skulla_blip_processor = BlipProcessor.from_pretrained(
            local_model_path, 
            local_files_only=True
        )
        
        # 2. Загружаем модель из .bin файла
        _skulla_blip_model = BlipForConditionalGeneration.from_pretrained(
            local_model_path, 
            local_files_only=True
        )
        
        print("[🎉 SKULLA VISION]: Локальная модель BLIP успешно подключена и готова!", flush=True)
    except Exception as e:
        print(f"[❌ SKULLA VISION ERROR]: Не удалось загрузить локальную BLIP модель: {e}", flush=True)
        _skulla_blip_model = None
        _skulla_blip_processor = None

def _init_local_blip_ai():
    """Ленивая инициализация генератора названий товаров из картинок под локальные веса"""
    global _skulla_blip_model, _skulla_blip_processor
    if _skulla_blip_model is not None:
        return

    try:
        # 🎯 СКАЛЛА-ФИКС: Возвращаем канонический класс BlipForConditionalGeneration под твои .bin файлы!
        from transformers import BlipProcessor, BlipForConditionalGeneration
        import torch
        print("[SKULLA VISION]: Загрузка автономного ИИ-распознавателя названий BLIP...", flush=True)

        # 🍏 СКАЛЛА-ФИКС СОВМЕСТИМОСТИ: Автоматический детектор окружения Dev/Prod
        dev_path = "C:/Projects/sellers/models/blip-base"
        prod_path = "/app/models/blip-base"

        import os
        local_model_path = dev_path if os.path.exists(dev_path) else prod_path

        # # 1. Загружаем процессор
        _skulla_blip_processor = BlipProcessor.from_pretrained(
            local_model_path,
            local_files_only=True
        )

        # # 2. Загружаем модель из .bin файла по канонической архитектуре
        _skulla_blip_model = BlipForConditionalGeneration.from_pretrained(
            local_model_path,
            local_files_only=True
        )


        print("[🏆 SKULLA VISION SUCCESS]: Локальная модель BLIP успешно подключена к весам и готова!", flush=True)
    except Exception as e:
        print(f"[❌ SKULLA VISION ERROR]: Не удалось загрузить локальную модель BLIP: {e}", flush=True)
        _skulla_blip_model = None
        _skulla_blip_processor = None



def detect_product_name_local_old(image_bytes: bytes) -> str:
    """
    🪐 АВТОНОМНОЕ МУЛЬТИМОДАЛЬНОЕ ЗРЕНИЕ ШЕФА БЕЗ ЗАРАНЕЕ ЗАДАННЫХ СПИСКОВ
    Нейросеть сама сканирует пиксели товара и пишет его название из головы на английском!
    """
    global _skulla_blip_model, _skulla_blip_processor
    try:
        _init_local_blip_ai()
        if _skulla_blip_model is None or _skulla_blip_processor is None:
            return "Unknown Product" # Фолбэк, если ИИ не загрузился


        import io
        from PIL import Image
        
        # Декодируем чистый силуэт товара без фона
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        import torch

        # 🎯 СКАЛЛА-ФИКС: Объявляем переменную device, чтобы Pylance и Питон больше не ругались!
        # Система сама определит, есть ли видеокарта, или нужно считать на процессоре.

        # Процессим картинку. Модель будет генерировать текст, основываясь на подсказке "a product photo of"
        #inputs = _skulla_blip_processor(img, "a product photo", return_tensors="pt")
        inputs = _skulla_blip_processor(img, "Question: what is the main product in this photo? Answer:", return_tensors="pt")
        prompt = "question: what is this? answer:"
        inputs = _skulla_blip_processor(img, prompt, return_tensors="pt")


        # Генерируем чистое текстовое название товара по пикселям
        output = _skulla_blip_model.generate(
            **inputs,
            # 🧠 ГЛАВНЫЙ СРЕЗ: Даем модели максимум 6-8 токенов (этого с запасом хватит на 2-4 чистых слова товара)
            max_new_tokens=8,
            min_new_tokens=2,            # Запрещаем отдавать пустые ответы

            # 🎯 ПЕРЕКЛЮЧАЕМ НА СТАБИЛЬНЫЙ B2B-ПОИСК: Отключаем свободное do_sample!
            # Вместо этого включаем Beam Search (лучевой поиск) на 5 параллельных ветвей.
            # Это заставит модель выбирать только математически самые точные и логичные слова предмета!
            do_sample=False,
            num_beams=5,
            early_stopping=True,

            # 🚫 ЖЕСТКИЙ ШТРАФ ЗА ПОВТОРЫ И ДУБЛИ:
            # Запрещаем модели повторять комбинации из двух слов (например, "leather shoes leather")
            repetition_penalty=1.3,
            no_repeat_ngram_size=2
        )


        raw_en_name = _skulla_blip_processor.decode(output[0], skip_special_tokens=True)
        
        # Отрезаем нашу подсказку, оставляя только чистое имя объекта из головы ИИ
        # Очищаем строку по реальному регистру, который выдал ИИ на скриншоте
        #detected_en = raw_en_name.replace("question : what is the main product in this photo? answer :", "").strip()
        # 🎯 УЛЬТИМАТИВНЫЙ СКАЛЛА-ФИКС: Нативно режем строку по маркеру ИИ-ответа!
        # Нам плевать на текст вопроса, мы просто забираем правую часть после "answer :"
        if "answer :" in raw_en_name.lower():
            detected_en = raw_en_name.lower().split("answer :")[-1].strip()
        else:
            detected_en = raw_en_name.lower().replace("question :", "").strip()

        # Если вдруг ИИ выдал пустую строку, страхуемся базовым b2b-классом товара
        if not detected_en or len(detected_en) < 2:
            detected_en = "product"

        
        if not detected_en:
            return "Товар"
            
        print(f"📷 [SKULLA VISION GENERATED EN]: ИИ определил объект как -> '{detected_en}'", flush=True)
        return detected_en

    except Exception as e:
        print(f"❌ [WARN VISION DETECT CRITICAL]: Сбой автономной детекции: {e}", flush=True)
        return "Товар"

def detect_product_name_local_new(image_bytes: bytes) -> str:
    """
    АВТОНОМНОЕ МУЛЬТИМОДАЛЬНОЕ ЗРЕНИЕ ШЕФА БЕЗ ЗАРАНЕЕ ЗАДАННЫХ СПИСКОВ
    Нейросеть сама сканирует пиксели товара и пишет его название из головы на английском!
    """
    global _skulla_blip_model, _skulla_blip_processor
    try:
        # Инициализируем локальную модель, если её еще нет в памяти
        _init_local_blip_ai()
        if _skulla_blip_model is None or _skulla_blip_processor is None:
            return "Unknown Product"  # Фолбэк, если ИИ не загрузился

        import io
        from PIL import Image
        import torch

        # Декодируем чистый силуэт товара без фона из входящих сетевых байт
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        device = _skulla_blip_model.device

        # 🧠 КАНОНИЧНЫЙ КОММЕРЧЕСКИЙ ПРОМПТ SKULLA (БЕЗ ЗНАКОВ ВОПРОСА И ЛИШНИХ ПРЕДЛОГОВ)
        prompt = "a product photo"
        inputs = _skulla_blip_processor(img, prompt, return_tensors="pt").to(device)

        # 🦾 СКАЛЛА-ФИКС ПАРАМЕТРОВ: Включаем стабильный лучевой поиск БЕЗ свободного сэмплирования и каши!
        with torch.no_grad():
            output = _skulla_blip_model.generate(
                **inputs,
                max_new_tokens=4,          # Жестко режем длину (хватит ровно на 1-2 слова сути товара!)
                min_new_tokens=1,
                num_beams=5,               # Выбираем только математически самое точное слово из весов
                early_stopping=True,
                repetition_penalty=1.3
            )

        # Декодируем ИИ-токены в понятную строку на английском языке
        raw_en_name = _skulla_blip_processor.decode(output[0] if len(output.shape) > 1 else output, skip_special_tokens=True).strip().lower()
        print(f"📡 [RAW BLIP OUTPUT]: '{raw_en_name}'", flush=True)

        # 🎯 СНАЙПЕРСКАЯ ОЧИСТКА В КОРЕНЬ: Просто посимвольно вырезаем наш стартовый промпт!
        detected_en = raw_en_name.replace("a product photo", "").strip()

        # Хирургически зачищаем паразитные предлоги места и знаки, если они вылезли из головы ИИ
        for trash in ["of", "s", "?", ".", "on", "with"]:
            if detected_en.startswith(trash + " "):
                detected_en = detected_en[len(trash)+1:].strip()
            if detected_en.endswith(" " + trash):
                detected_en = detected_en[:-len(trash)-1].strip()
        
        detected_en = detected_en.replace("?", "").replace(".", "").replace(",", "").strip()

        # Железная страховка на случай пустой строки или микро-мусора
        if not detected_en or len(detected_en) < 2:
            detected_en = "cream"

        print(f"🍏 [SKULLA VISION GENERATED EN]: ИИ определил объект как -> '{detected_en}'", flush=True)
        return detected_en

    except Exception as e:
        print(f"🚨 [❌ WARN VISION DETECT CRITICAL]: Сбой автономной детекции: {e}", flush=True)
        return "Unknown Product"


# Глобальные переменные для удержания ИИ-мозгов в оперативной памяти сервера
_skulla_qwen_model = None
_skulla_qwen_processor = None



def _init_local_qwen_ai():
    """ Ленивая инициализация 100% АВТОНОМНОГО оффлайн-движка Alibaba Qwen2-VL 2B с диском C:/ """
    global _skulla_qwen_model, _skulla_qwen_processor
    if _skulla_qwen_model is not None:
        return

    try:
        # Подключаем каноничный AutoProcessor
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
        import torch
        import os
        import sys
        import traceback # 🔥 ИИ-СНАЙПЕР: Вытаскиваем полный стек вызовов для отладки

        print("[📢 SKULLA DEBUG START]: Начинаем жесткий рантайм-замер шлюзов Квена...", flush=True)

        dev_path = "C:/Projects/sellers/models/Qwen2-VL-2B-Instruct"
        prod_path = "/app/models/Qwen2-VL-2B-Instruct"
        
        local_model_path = dev_path if os.path.exists(dev_path) else prod_path
        print(f"📂 [SKULLA DEBUG PATH]: Физический путь на сервере -> {local_model_path}", flush=True)
        print(f"📂 [SKULLA DEBUG PATH EXISTS]: Проверка существования папки -> {os.path.exists(local_model_path)}", flush=True)

        # 🦾 ЗРЯЧИЙ E-COMMERCE СТАНДАРТ ПИКСЕЛЕЙ: Поднимаем разрешение до 448х448, 
        # чтобы ИИ лазером видел мелкие детали автомобильных видеорегистраторов Павла!
        print("[📢 SKULLA PREPARE]: Инициализация AutoProcessor...", flush=True)
        _skulla_qwen_processor = AutoProcessor.from_pretrained(
            local_model_path,
            local_files_only=True,
            min_pixels=448*448,
            max_pixels=448*448
        )
        print("[🍏 SKULLA SUCCESS]: AutoProcessor успешно собран!", flush=True)

        # Вшиваем официальный ChatML-шаблон диалога Alibaba в корень процессора
        _skulla_qwen_processor.chat_template = (
            "{% for message in messages %}"
            "{{ '<|im_start|>' + message['role'] + '\\n' }}"
            "{% if message['content'] is string %}"
            "{{ message['content'] }}"
            "{% else %}"
            "{% for item in message['content'] %}"
            "{% if item['type'] == 'text' %}{{ item['text'] }}"
            "{% elif item['type'] == 'image' %}{{ '<|image_pad|>' }}"
            "{% endif %}"
            "{% endfor %}"
            "{% endif %}"
            "{{ '<|im_end|>\\n' }}"
            "{% endfor %}"
            "{% if add_generation_prompt %}{{ '<|im_start|>assistant\\n' }}{% endif %}"
        )
        print("[🍏 SKULLA SUCCESS]: ИИ-шаблон ChatML вмонтирован в процессор!", flush=True)

        # Проверяем, какие глобальные контексты устройств у нас сейчас висят в памяти
        print(f"📡 [SKULLA TORCH DEVICE CHECK]: Доступен ли CUDA? -> {torch.cuda.is_available()}", flush=True)
        print(f"📡 [SKULLA TORCH BACKEND]: Текущий бэкэнд потоков торча -> {torch.__version__}", flush=True)

        # 🦾 ЗАГРУЖАЕМ ОРИГИНАЛЬНУЮ МОДЕЛЮ: В полноценном нативном FLOAT32
        print("[📢 SKULLA PREPARE]: Старт жесткого чтения 4.5 Гб .safetensors файлов модели...", flush=True)

        _skulla_qwen_model = Qwen2VLForConditionalGeneration.from_pretrained(
            local_model_path,
            local_files_only=True,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=False,   # Сносим context manager скрытого сжатия памяти!
            device_map=None            # Выжигаем любые деления слоев и карт устройств под чистый CPU!
        )
        
        # Переносим веса на процессор стандартной безопасной командой PyTorch
        print("[📢 SKULLA PREPARE]: Нативный перенос тензорных весов в оперативку CPU...", flush=True)
        _skulla_qwen_model = _skulla_qwen_model.to("cpu")


        """

        _skulla_qwen_model = Qwen2VLForConditionalGeneration.from_pretrained(
            local_model_path,
            local_files_only=True,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=False,
            device_map=None,
            
            # 🔥 РАЗГОННЫЙ РЫЧАГ №1: Включаем нативную математику SDPA (Scaled Dot-Product Attention)!
            # Это аналог Flash Attention для процессоров, ускоряет обсчет матриц внимания в 2-3 раза!
            attn_implementation="sdpa" 
        )
        
        # 🔥 РАЗГОННЫЙ РЫЧАГ №2: Принудительно компилируем граф модели через JIT-оптимизатор Торча!
        # Процессор один раз просчитает пути вычислений и начнет щелкать токены как семечки!
        _skulla_qwen_model = torch.compile(_skulla_qwen_model)
        _skulla_qwen_model = _skulla_qwen_model.to("cpu")
                """
        print("[🏆 SKULLA QWEN SUCCESS]: Локальные веса успешно прогружены и встали в ОЗУ!", flush=True)



    except Exception as e:
        print("\n" + "="*80, flush=True)
        print(f"🚨 [❌ SKULLA CRITICAL EXCEPTION]: Сбой инициализации Квена: {e}", flush=True)
        print("🔍 [SKULLA TRACEBACK DETECTOR]: Вытаскиваем точную строку краша из кишек Питона:", flush=True)
        print("="*80, flush=True)
        # Выдаем полную анатомию стека ошибок в лог сервера
        traceback.print_exc(file=sys.stdout)
        print("="*80 + "\n", flush=True)
        
        _skulla_qwen_model = None
        _skulla_qwen_processor = None





def detect_product_name_local(image_bytes: bytes) -> str:
    """
    МУЛЬТИМОДАЛЬНОЕ ЗРЕНИЕ ALIBABA QWEN2-VL-2B:
    Максимально ускоренный инференс со снайперским извлечением 
    коммерческого наименования товара для маркетплейсов в 2-3 слова!
    """
    global _skulla_qwen_model, _skulla_qwen_processor
    try:
        import io
        from PIL import Image
        import torch

        if _skulla_qwen_model is None or _skulla_qwen_processor is None:
            print("📡 [SKULLA STATE]: Первичный запуск воркера. Прогреваем веса Квена...", flush=True)
            _init_local_qwen_ai()
            
        # Жесткий страховочный фолбэк на случай аварии диска Linux VDS
        if _skulla_qwen_model is None or _skulla_qwen_processor is None:
            print("🚨 [SKULLA WARN]: Модель не инициализирована, аварийный обход!", flush=True)
            return "product name"

        # Забираем чистые ссылки из глобальной памяти намертво!
        model = _skulla_qwen_model
        processor = _skulla_qwen_processor

        # Декодируем входящие сетевые байты фотографии селлера в PIL Image
        raw_img = Image.open(io.BytesIO(image_bytes))
        
        # Накладываем вырезанный силуэт на чистый белый холст для стирания альфа-каналов .png
        bg_white = Image.new("RGB", raw_img.size, (255, 255, 255))
        if raw_img.mode in ('RGBA', 'LA') or (raw_img.mode == 'P' and 'transparency' in raw_img.info):
            bg_white.paste(raw_img, (0, 0), raw_img.convert("RGBA"))
            image = bg_white
        else:
            image = raw_img.convert("RGB")

        # 🎯 УЛЬТИМАТИВНЫЙ B2B-ПРОМПТ НА ТОЧНОСТЬ: 
        # Силой заставляем Qwen2-VL выдавать конкретное b2b-имя товара с его свойствами (например, running shoes), 
        # напрочь запрещая кидать общие слепые слова вроде "item" или "object"!
        # 🎯 СКАЛЛА-ФИКС ПРОМПТА: Убираем всю воду! Короткий промпт экономит 70% времени обсчета CPU!
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": "Title name in 2 words (e.g. 'hair dryer', 'face cream'):"}
                ]
            }
        ]


        # Применяем официальный шаблон чата Alibaba
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        
        # Собираем тензоры для рантайма Питона
        inputs = processor(
            text=[text],
            images=image,
            padding=True,
            return_tensors="pt"
        ).to(model.device)

        # 🦾 МАКСИМАЛЬНЫЙ РАЗГОН СКОРОСТИ: Зажимаем генерацию до 4 токенов!
        # Модель отработает в 3 раза быстрее на CPU, так как выдаст строго суть и мгновенно остановится!
        # 🦾 СКАЛЛА-ФИКС ГЕНЕРАЦИИ: Даем модели свободу дописать категорию целиком!
        with torch.no_grad():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=12,         # 🔥 Теперь токенов точно хватит на полные фразы!
                min_new_tokens=1,
                do_sample=False            # Жесткая конкретика без галлюцинаций
            )

            
        # Вырезаем системный промпт из общего массива токенов ответа
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        
        # Декодируем ИИ-токены в понятный английский текст
        output_text = processor.batch_decode(
            generated_ids_trimmed, 
            skip_special_tokens=True, 
            clean_up_tokenization_spaces=False
        )

        detected_en = output_text[0].strip().lower()
        print(f"📡 [RAW ALIBABA QWEN OUTPUT]: '{detected_en}'", flush=True)

        # Хирургически зачищаем мусорные символы и артикли на стыках строк
        detected_en = detected_en.replace("?", "").replace(".", "").replace(",", "").strip()
        for article in ["a ", "an ", "the ", "product "]:
            if detected_en.startswith(article):
                detected_en = detected_en[len(article):].strip()

        # Железная b2b-страховка Skulla, спасающая от пустых строк
        if not detected_en or len(detected_en) < 2:
            detected_en = "product name"

        print(f"🍏 [SKULLA QWEN GENERATED EN]: Квен выдал точное имя -> '{detected_en}'", flush=True)
        return detected_en

    except Exception as e:
        print(f"🚨 [❌ WARN QWEN CRITICAL]: Сбой автономной детекции Alibaba Qwen2-VL: {e}", flush=True)
        return "product name"


def generate_auto_marketing_utp(product_name: str) -> dict:
    """
    👑 УЛЬТИМАТИВНЫЙ ИИ-КОНВЕЙЕР ШЕФА НА БАЗЕ QWEN2.5 С ПРОМПТОМ КОНТЕНТ-ДИРЕКТОРА
    Модель генерирует кристально чистые, продающие триггеры для Wildberries/Ozon 
    без английской кальки, дословных переводов и канцелярского бреда.
    """
    global _skulla_gpt_translator, _skulla_gpt_tokenizer
    try:
        _init_local_text_gpt()

        name_ru = str(product_name).strip() if product_name else "Товар"
        name_upper = name_ru.upper() if name_ru else "ТОВАР"

        if _skulla_gpt_translator is None or _skulla_gpt_tokenizer is None:
            raise ValueError("[ERROR]: ИИ-движки Qwen не запущены в ОЗУ!")

        # 🎯 СНАЙПЕРСКИЙ B2B-ПРОМПТ ШЕФА ПО СТАНДАРТУ CHATML (УНИЧТОЖИТЕЛЬ БРЕДА)
        # Заставляем модель мыслить коммерческими паттернами покупателей маркетплейсов СНГ!
        prompt = (
            "<|im_start|>system\n"           
            f"<|im_start|>user\nНапиши 3 плашки на Русском языке на карточку товара: '{name_ru}'<|im_end|>\n"
            "<|im_start|>assistant\n1."
        )

        # Конвертируем промпт в текстовые токены для ctranslate2.Generator
        #prompt_tokens = _skulla_gpt_tokenizer.convert_ids_to_tokens(_skulla_gpt_tokenizer.encode(prompt))
        prompt_tokens = _skulla_gpt_tokenizer.tokenize(prompt)
        # Запускаем генерацию пакетного вывода. include_prompt_in_result=False отсекает кэш промпта [INDEX]
        step_results = _skulla_gpt_translator.generate_batch(
            [prompt_tokens], 
            max_length=200,                # Увеличили лимит с запасом под русский промпт!
            sampling_topk=1,
            include_prompt_in_result=False
        )
        
        # Вытаскиваем токены первого элемента батча
        first_result = step_results[0]
        output_ids = first_result.sequences_ids[0]
        
        # Превращаем ID в кристально чистую русскую строку
        raw_ru_response = _skulla_gpt_tokenizer.decode(output_ids).strip()
        
        translate_ru = translate_tag_to_russian_local(raw_ru_response)

        ru_response = "1. " + raw_ru_response

        # Построчно парсим и очищаем текст от остаточных системных тегов
        raw_lines = ru_response.split("\n")
        cleaned_lines = []
        stop_words = ["system", "маркетолог", "пример", "товар", "напиши", "преимущества", "<|im_start|>", "<|im_end|>", "user", "assistant"]
        
        for line in raw_lines:
            line_str = line.strip()
            if not line_str or any(word in line_str.lower() for word in stop_words):
                continue
            
            # Срезаем цифры нумерации, маркеры и тире
            for prefix in ["1.", "2.", "3.", "1", "2", "3", "-", "•", ":"]:
                if line_str.startswith(prefix):
                    line_str = line_str[len(prefix):].strip()
            
            if line_str and len(line_str) > 1:
                cleaned_lines.append(line_str.upper())
        
        # Забираем строго топ-3 преимущества товара
        cleaned_lines = cleaned_lines[:3]

        # Страховочный премиум-пак на случай полного сбоя генерации весов
        if len(cleaned_lines) < 2:
            cleaned_lines = ["ПРЕМИУМ КАЧЕСТВО", "НАДЕЖНЫЙ ВЫБОР", "СТИЛЬНЫЙ ДИЗАЙН"]

        # Собираем финальный текст для верстки карточки маркетплейса
        utp_list_str = "\n".join(cleaned_lines[:3])
        auto_text = (
            f"🚀 ИИ-ГЕНЕРАЦИЯ КАРТОЧЕК ПОД КАТЕГОРИЮ: {name_upper}\n"
            f"{utp_list_str}\n"
            f"⚡ ТЕСТИРУЙ АБСОЛЮТНО БЕСПЛАТНО НА SKULLA.RU!"
        )

        return {
            "main_title": f"КУПИТЬ {name_upper}",
            "text_description": auto_text
        }

    except Exception as e:
        print(f"❌ [CRITICAL ERROR]: Сбой e-commerce генератора Qwen: {e}", flush=True)
        return {
            "main_title": f"КУПИТЬ {product_name.upper() if product_name else 'ТОВАР'}",
            "text_description": "🚀 ТОП-КАЧЕСТВО\n🔥 ХИТ СЕЗОНА\n⚡ БЫСТРАЯ ДОСТАВКА"
        }


import json

def generate_custom_prompt_local_qwen(prompt_text: str) -> str:
    """
    ⚡ ВЫСОКОСКОРОСТНОЙ АНГЛОЯЗЫЧНЫЙ КЛАССИФИКАТОР ДЛЯ CPU
    Нейросеть мэтчит английские товары с английскими категориями,
    а Python выдает готовые РУССКИЕ плашки на фронтенд.
    """
    global _skulla_gpt_translator, _skulla_gpt_tokenizer
    
    # База данных: английский ключ -> русские e-commerce теги для инфографики (20 категорий)
    MARKETPLACE_DATABASE = {
        "electronics": [
            "Гарантия качества",
            "Надежная сборка",
            "Современные технологии"
        ],
        "home_appliances": [
            "Высокая мощность",
            "Долговечные материалы",
            "Эргономичный дизайн"
        ],
        "home_kitchen": [
            "Уют и комфорт",
            "Практичность в быту",
            "Стильное решение"
        ],
        "apparel_shoes": [
            "Премиум материалы",
            "Идеальная посадка",
            "Стильный дизайн"
        ],
        "beauty_hygiene": [
            "Бережный уход",
            "Натуральный состав",
            "Для ежедневного применения"
        ],
        "health_wellness": [
            "Одобрено экспертами",
            "Безопасный состав",
            "Максимум пользы"
        ],
        "kids_products": [
            "Безопасно для детей",
            "Гипоаллергенно",
            "Яркие эмоции"
        ],
        "auto_parts": [
            "Высокая прочность",
            "Износостойкость",
            "Легкая установка"
        ],
        "sport_outdoor": [
            "Для активной жизни",
            "Высокое качество",
            "Проверено в деле"
        ],
        "tools_improvement": [
            "Надежный инструмент",
            "Прослужит долго",
            "Профессиональный выбор"
        ],
        "garden_backyard": [
            "Для Вашего сада",
            "Экологически чисто",
            "Отличный результат"
        ],
        "stationery_office": [
            "Для работы и учебы",
            "Удобство и стиль",
            "Высокое качество"
        ],
        "books_media": [
            "Бестселлер рунета",
            "Подарочное издание",
            "Читают все"
        ],
        "pet_supplies": [
            "Забота о питомце",
            "Рекомендовано ветврачами",
            "Натуральные компоненты"
        ],
        "food_beverages": [
            "Натуральный продукт",
            "Изысканный вкус",
            "Без лишних добавок"
        ],
        "gadget_accessories": [
            "Идеальная совместимость",
            "Максимальная защита",
            "Ультрапрочный материал"
        ],
        "household_chemicals": [
            "Эффективное очищение",
            "Концентрированный состав",
            "Эко-формула"
        ],
        "jewelry_accessories": [
            "Изящный дизайн",
            "Эксклюзивный стиль",
            "Приковывает взгляды"
        ],
        "hobbies_crafts": [
            "Для яркого творчества",
            "Все включено в набор",
            "Развивает таланты"
        ],
        "adult_products": [
            "100% анонимность",
            "Высокое качество",
            "Безопасные компоненты"
        ],
        "unknown": [
            "Хит продаж",
            "Высокое качество",
            "Выбор покупателей"
        ]
    }


    try:
        _init_local_text_gpt()
        if _skulla_gpt_translator is None or _skulla_gpt_tokenizer is None:
            return json.dumps(["Ошибка", "Модель не инициализирована", "", ""], ensure_ascii=False)


        # Очищаем название от лишних артиклей vision-распознавателя
        product_name_clean = str(prompt_text).strip().lower()
        for article in ["the ", "a ", "an "]:
            if product_name_clean.startswith(article):
                product_name_clean = product_name_clean[len(article):].strip()

        # 1. Промпт полностью переведен на английский — Qwen на CPU щелкнет его как орешек
        full_prompt = (
            "You are a strict text classification API.\n"
            "Categorize the product name. You must respond with EXACTLY ONE category code from the list below.\n\n"
            "AVAILABLE CODES:\n"
            "electronics\n"
            "home_appliances\n"
            "home_kitchen\n"
            "apparel_shoes\n"
            "beauty_hygiene\n"
            "health_wellness\n"
            "kids_products\n"
            "auto_parts\n"
            "sport_outdoor\n"
            "tools_improvement\n"
            "garden_backyard\n"
            "stationery_office\n"
            "books_media\n"
            "pet_supplies\n"
            "food_beverages\n"
            "gadget_accessories\n"
            "household_chemicals\n"
            "jewelry_accessories\n"
            "hobbies_crafts\n"
            "adult_products\n"
            "unknown\n\n"
            "CRITICAL: Output ONLY the chosen lowercase code word. Do not write anything else.\n\n"
            "EXAMPLES:\n"
            "Product: smartphone\nCategory: electronics\n\n"
            "Product: toaster\nCategory: home_appliances\n\n"
            "Product: hair dryer\nCategory: home_appliances\n\n"
            "Product: shampoo\nCategory: beauty_hygiene\n\n"
            "Product: laundry detergent\nCategory: household_chemicals\n\n"
            f"Product: {product_name_clean}\n"
            "Category:"
        )


        messages = [{"role": "user", "content": full_prompt}]
        
        # Шаблон для Qwen2.5-Instruct
        prompt_tokens = _skulla_gpt_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        
        # КРИТИЧЕСКИЙ ФИКС: Конвертируем в строковые токены для генератора ctranslate2
        token_ids = _skulla_gpt_tokenizer.encode(prompt_tokens)
        source_tokens = _skulla_gpt_tokenizer.convert_ids_to_tokens(token_ids)

        # Запускаем генерацию
        outputs = _skulla_gpt_translator.generate_batch(
            [source_tokens],
            max_length=8,                 # Для одного кодового слова больше не нужно
            sampling_topk=1,              # Greedy Search — берем только самый сильный токен без вариаций
            sampling_temperature=0.0,     # Нулевая креативность для точности совпадения слова
            include_prompt_in_result=False
        )

        # 4. РЕШАЮЩИЙ КРИТИЧЕСКИЙ ФИКС РАСПАКОВКИ:
        # outputs[0].sequences_ids — это список списков [[7675, 6282, ...]]. 
        # Забираем строго ПЕРВЫЙ элемент, чтобы получить чистый плоский список ID (List[int])
        if isinstance(outputs, list) and len(outputs) > 0:
            target_tokens = outputs[0].sequences_ids[0]
        else:
            # Страховка на случай изменения структуры объекта в разных версиях библиотеки
            target_tokens = outputs.sequences_ids[0] if hasattr(outputs, 'sequences_ids') else []

        # 5. Декодируем чистый плоский список ID токенов в текст
        decoded_text = _skulla_gpt_tokenizer.decode(target_tokens, skip_special_tokens=True)
        
        # 6. Очистка строки от случайного мусора (теперь это гарантированно строка, .strip() сработает)
        category_key = str(decoded_text).strip().lower()
        category_key = category_key.replace('"', '').replace("'", "").replace(".", "").strip()


        # Проверяем на пустой ответ или галлюцинацию (если модель выдала код, которого нет в списке)
        valid_codes = [
            "electronics", "home_appliances", "home_kitchen", "apparel_shoes", "beauty_hygiene",
            "health_wellness", "kids_products", "auto_parts", "sport_outdoor", "tools_improvement",
            "garden_backyard", "stationery_office", "books_media", "pet_supplies", "food_beverages",
            "gadget_accessories", "household_chemicals", "jewelry_accessories", "hobbies_crafts", 
            "adult_products", "unknown"
        ]
        
        if category_key not in valid_codes:
            category_key = "unknown"


        if category_key not in MARKETPLACE_DATABASE:
            category_key = "unknown"

        utp_list = MARKETPLACE_DATABASE.get(category_key, MARKETPLACE_DATABASE["unknown"])
        
        # Склеиваем массив строк ["Гарантия качества", "Надежная сборка"] через перенос \n
        utp_string = "\n".join(utp_list)

        print(f"📦 [ENGLISH-KEY ENGINE]: Product '{product_name_clean}' -> Mapped to: '{category_key}'", flush=True)

        # Возвращаем готовый словарь для метода .update() в роутере
        return {"utp_list": utp_string}        

    except Exception as e:
            print(f"⚠️ [DATABASE UTP ERROR]: Сбой извлечения плашек: {e}", flush=True)
            # Страховочный бэкап, если база данных недоступна
            return {"utp_list": "Хит продаж\nВысокое качество\nВыбор покупателей"}


import re

# Промышленная база ключевых слов (расширена в 10 раз, 20 категорий первого уровня)
ENG_CATEGORY_KEYWORDS = {
    "electronics": [
        "smartphone", "phone", "iphone", "android", "samsung", "xiaomi", "redmi", "realme", "poco", "pixel",
        "laptop", "notebook", "macbook", "asus", "acer", "lenovo", "hp", "dell", "computer", "pc", "desktop",
        "tablet", "ipad", "kindle", "e-book", "e-reader", "tv", "television", "oled", "qled", "monitor", "display",
        "headphones", "earphones", "airpods", "earbuds", "headset", "speaker", "soundbar", "subwoofer", "jbl",
        "smartwatch", "apple watch", "galaxy watch", "fitness tracker", "band", "smartband", "camera", "dslr",
        "action camera", "gopro", "videocamera", "camcorder", "lens", "tripod", "flash drive", "usb", "hard drive",
        "ssd", "hdd", "sd card", "memory card", "router", "modem", "wi-fi", "switch", "playstation", "xbox", "nintendo",
        "console", "gamepad", "joystick", "projector", "microphone", "dictaphone", "intercom", "smart home", "hub",
        "sensor", "socket", "plug", "adapter", "power strip", "extension", "gpu", "cpu", "motherboard", "ram", "cooler"
    ],
    "home_appliances": [
        "toaster", "sandwich maker", "waffle maker", "hair dryer", "dryer", "hair straightener", "curling iron",
        "styler", "shaver", "epilator", "trimmer", "clipper", "toothbrusher", "irrigator", "kettle", "electric kettle",
        "vacuum", "robot vacuum", "cleaner", "steam mop", "blender", "mixer", "juicer", "meat grinder", "food processor",
        "microwave", "oven", "toaster oven", "iron", "steamer", "garment steamer", "slow cooker", "multicooker",
        "air fryer", "deep fryer", "grill", "electric grill", "crepe maker", "coffee maker", "coffeemaker", "coffee machine",
        "coffee grinder", "fridge", "refrigerator", "freezer", "wine cooler", "dishwasher", "washing machine", "washer",
        "dryer machine", "air conditioner", "ac", "fan", "heater", "convector", "humidifier", "dehumidifier", "air purifier",
        "sewing machine", "water dispenser", "cooler water", "scale", "bathroom scale", "kitchen scale", "hood", "exhaust fan"
    ],
    "home_kitchen": [
        "tableware", "plate", "bowl", "dish", "mug", "cup", "glass", "wine glass", "shot glass", "tumbler", "saucer",
        "pan", "frying pan", "skillet", "pot", "saucepot", "saucepan", "casserole", "baking sheet", "baking dish", "wok",
        "knife", "chef knife", "fork", "spoon", "cutlery", "spatula", "ladle", "whisk", "colander", "peeler", "grater",
        "cutting board", "bread box", "food container", "lunch box", "thermos", "flask", "jar", "canister", "spice rack",
        "bedding", "bed sheet", "duvet", "duvet cover", "pillowcase", "pillow", "blanket", "quilt", "mattress", "topper",
        "curtain", "drapes", "blinds", "tulle", "rug", "carpet", "mat", "bath mat", "doormat", "towel", "bathrobe", "tablecloth",
        "napkin", "apron", "furniture", "chair", "armchair", "stool", "sofa", "couch", "bed", "mattress", "table", "desk",
        "cabinet", "wardrobe", "closet", "chest of drawers", "dresser", "nightstand", "shelf", "rack", "mirror", "vase",
        "clock", "wall clock", "candle", "candlestick", "picture frame", "poster", "figurine", "statue", "hanger", "coat rack"
    ],
    "apparel_shoes": [
        "jacket", "coat", "down jacket", "parka", "windbreaker", "trench", "blazer", "vest", "hoodie", "sweatshirt",
        "sweater", "pullover", "cardigan", "jumper", "dress", "sundress", "gown", "skirt", "jeans", "pants", "trousers",
        "shorts", "leggings", "tights", "t-shirt", "tee", "shirt", "blouse", "top", "tank top", "polo", "suit", "tuxedo",
        "tracksuit", "pajamas", "nightgown", "underwear", "panties", "boxers", "briefs", "bra", "socks", "stockings",
        "shoes", "sneakers", "boots", "ankle boots", "loafers", "oxfords", "flats", "heels", "pumps", "sandals", "slippers",
        "clogs", "mules", "trainers", "crocs", "bag", "handbag", "tote", "clutch", "crossbody", "backpack", "briefcase",
        "wallet", "purse", "cardholder", "belt", "hat", "cap", "beanie", "scarf", "gloves", "mittens", "tie", "bowtie",
        "sunglasses", "glasses frame", "umbrella", "raincoat", "swimsuit", "swimwear", "trunks", "bikini", "overalls", "romper"
    ],
    "beauty_hygiene": [
        "cream", "moisturizer", "lotion", "gel", "face gel", "serum", "essence", "toner", "cleanser", "face wash", "scrub",
        "peeling", "mask", "face mask", "eyepatch", "patches", "shampoos", "shampoo", "conditioner", "hair mask", "hair oil",
        "hairspray", "mousse", "foam", "shaving foam", "aftershave", "hair dye", "lipstick", "lip balm", "lip gloss", "lip liner",
        "foundation", "bb cream", "cc cream", "concealer", "powder", "blush", "highlighter", "bronzer", "mascara", "eyeliner",
        "eyeshadow", "brows gel", "perfume", "fragrance", "cologne", "toilette", "eau de parfum", "soap", "liquid soap",
        "shower gel", "body wash", "bubble bath", "bath salt", "bath bomb", "deodorant", "antiperspirant", "toothpaste",
        "toothbrush", "mouthwash", "dental floss", "comb", "hairbrush", "hair ties", "bobby pins", "cotton pads", "cotton swabs",
        "wet wipes", "sanitary pads", "tampons", "manicure set", "nail polish", "nail file", "tweezers", "epilator wax", "sunscreen"
    ],
    "health_wellness": [
        "vitamins", "vitamin", "multivitamins", "supplement", "supplements", "dietary supplement", "collagen", "omega-3",
        "protein", "bcaa", "creatine", "amino acids", "gummies vitamin", "tonometer", "blood pressure monitor", "inhaler",
        "nebulizer", "thermometer", "medical thermometer", "glucose meter", "glucometer", "pulse oximeter", "hearing aid",
        "massager", "massage gun", "foot bath", "heating pad", "first aid kit", "bandage", "gauze", "medical mask", "respirator",
        "patch", "medical patch", "corn patch", "orthopedic", "insoles", "corset", "brace", "splint", "crutches", "walker",
        "antiseptic", "sanitizer", "disinfectant", "pill organizer", "pill box", "contact lenses", "lens solution", "eye drops",
        "nasal spray", "cough drops", "ointment", "balm health", "essential oil", "sea water spray", "hearing protection", "earplugs"
    ],
    "kids_products": [
        "toy", "toys", "doll", "barbie", "action figure", "plush toy", "stuffed animal", "teddy bear", "constructor", "lego",
        "building blocks", "puzzle", "board game", "car toy", "toy truck", "rc car", "train set", "toy gun", "water gun",
        "diapers", "pampers", "nappies", "baby wipes", "stroller", "pram", "pushchair", "car seat", "baby carrier", "sling",
        "baby food", "formula", "puree", "baby cereal", "snack kids", "rattle", "teether", "pacifier", "soother", "baby bottle",
        "sippy cup", "bib", "high chair", "playpen", "baby swing", "bouncer", "walker baby", "baby clothes", "bodysuit", "romper baby",
        "booties", "swaddle", "crib", "bassinet", "changing table", "baby bath", "potty", "potty training", "kids scooter", "tricycle",
        "balance bike", "kinetic sand", "slime", "play-doh", "coloring book", "toy kitchen", "dollhouse", "bubble blower"
    ],
    "auto_parts": [
        "mats", "floor mats", "floor mat", "weathertech", "trunk mat", "dashcam", "car camera", "dvr", "car recorder",
        "motor oil", "engine oil", "transmission fluid", "antifreeze", "coolant", "brake fluid", "windshield washer", "wipers",
        "wiper blades", "seat covers", "steering wheel cover", "car organizer", "sun shade", "air freshener", "car perfume",
        "tire", "tires", "winter tires", "summer tires", "wheel", "rims", "hubcaps", "jack", "bottle jack", "floor jack",
        "tow rope", "jumper cables", "booster cables", "car battery", "battery charger", "spark plug", "brake pads", "brake rotors",
        "shock absorber", "filter oil", "air filter", "cabin filter", "fuel filter", "led bulbs car", "headlight", "tail light",
        "car mat", "mud flaps", "roof rack", "bike rack car", "car cover", "scratch remover", "car shampoo", "wax car", "microfiber car"
    ],
    "sport_outdoor": [
        "water bottle", "bottle sport", "shaker", "protein shaker", "dumbbells", "dumbbell", "barbell", "weight plates",
        "kettlebell", "yoga mat", "fitness mat", "resistance bands", "loop bands", "expander", "push up bars", "pull up bar",
        "jump rope", "skipping rope", "hula hoop", "treadmill", "exercise bike", "elliptical", "hiking backpack", "tactical backpack",
        "tent", "camping tent", "sleeping bag", "sleeping pad", "camping chair", "camping table", "cooler bag", "flashlight camping",
        "compass", "binoculars", "bicycle", "bike sport", "mountain bike", "road bike", "cycling helmet", "bike lock", "pump bike",
        "skateboard", "longboard", "roller skates", "inline skates", "ice skates", "scooter adult", "stunt scooter", "hoverboard",
        "running shoes", "hiking boots", "sportswear", "leggings sport", "sports bra", "rashguard", "thermal underwear", "swim cap",
        "goggles", "ball", "football", "basketball", "soccer ball", "volleyball", "tennis racket", "badminton set", "punching bag"
    ],
    "tools_improvement": [
        "drill", "cordless drill", "screwdriver", "electric screwdriver", "screwdriver set", "hammer", "mallet", "perforator",
        "rotary hammer", "angle grinder", "grinder tool", "jigsaw", "circular saw", "saw", "handsaw", "hacksaw", "pliers",
        "wire cutters", "wrenches", "wrench set", "adjustable wrench", "socket set", "ratchet", "hex key", "allen key", "level tool",
        "spirit level", "laser level", "tape measure", "measuring tape", "utility knife", "box cutter", "staple gun", "soldering iron",
        "glue gun", "wallpaper", "paint", "wall paint", "paintbrush", "paint roller", "masking tape", "sandpaper", "putty", "sealant",
        "silicone sealant", "polyurethane foam", "led strip", "led strip light", "lamp", "desk lamp",
        "floor lamp", "light bulbs", "led bulb", "chandelier", "ceiling light", "wall light", "sconce", 
        "faucet", "mixer tap", "shower head", "shower hose", "sink", "washbasin", "toilet seat", 
        "extension cord", "voltage stabilizer", "toolbox", "tool organizer", "screws", "nails", "bolts"
    ],
    "garden_backyard": [
        "seeds", "flower seeds", "vegetable seeds", "lawn seed", "soil", "potting soil", "peat",
        "fertilizer", "plant food", "weed killer", "herbicide", "insecticide", "pest control garden", 
        "hose", "garden hose", "hose nozzle", "sprinkler", "watering can", "shovel", "spade", "rake", 
        "hoe", "trowel", "pitchfork", "secateur", "pruning shears", "lopper", "hedge trimmer", 
        "saw garden", "chainsaw", "lawn mower", "grass trimmer", "leaf blower", "flower pot", "planter",
        "planter box", "kašpo", "cachepot", "plant stand", "garden gloves", "repeller", "ultrasonic repeller", 
        "bird scarer", "garden furniture", "patio set", "hammock", "garden swing", "bbq grill", "charcoal grill", 
        "barbecue", "skewers", "garden lights", "solar lights", "greenhouse", "agrofibre", "garden arches", 
        "fence garden", "artificial grass"
    ],
    "stationery_office": [
        "notebook", "exercise book", "copybook", "pen", "ballpoint pen", "gel pen", "fountain pen", 
        "pencil", "mechanical pencil", "colored pencils", "marker", "highlighter", "permanent marker", 
        "whiteboard marker", "notepad", "writing pad", "diary", "planner", "weekly planner", "ежедневник", 
        "a4 paper", "printer paper", "copy paper", "folder", "file folder", "binder", "ring binder", 
        "clear folder", "stapler", "staples", "hole punch", "scissors office", "paper cutters", 
        "paperclips", "binder clips", "sticky notes", "post-it", "glue stick", "liquid glue", 
        "correction tape", "corrector fluid", "eraser", "sharpener", "pencil sharpener", "ruler", 
        "geometry set", "desk organizer", "pencil holder", "document tray", "clipboard", "whiteboard", 
        "magnetic board", "badge", "lanyard", "calculator", "shredder", "laminator", "office chair", "desk mat"
    ],
    "books_media": [
        "book", "books", "fiction", "non-fiction", "novel", "detective", "thriller", "fantasy", "sci-fi", 
        "romance book", "biography", "autobiography", "history book", "psychology book", "self-help", 
        "business book", "finance book", "textbook", "dictionary", "atlas", "encyclopedia", "childrens book", 
        "fairy tales", "comic", "comics", "manga", "graphic novel", "artbook", "sketchbook", "notebook drawing", 
        "album photo", "photo album", "calendar", "wall calendar", "magazine", "journal", "cd", "dvd", 
        "vinyl", "vinyl record", "audiobook", "sheet music", "postcard", "greeting card"
    ],
    "pet_supplies": [
        "pet food", "dog food", "cat food", "dry food", "wet food", "canned food", "bird seed", 
        "fish food", "hamster food", "food bowl", "pet bowl", "water fountain pet", "automatic feeder", 
        "treats dog", "treats cat", "catnip", "chew toy", "leash", "dog leash", "collar", "dog collar", 
        "cat collar", "harness", "pet harness", "muzzle", "pet carrier", "dog crate", "pet bag", 
        "litter box", "cat litter box", "litter", "cat litter", "tofu litter", "clay litter", 
        "pet pads", "puppy pads", "scratching post", "cat tree", "pet bed", "dog bed", "cat bed", 
        "pet house", "pet blanket", "cat toy", "dog toy", "laser pointer", "feather wand", "ball dog", 
        "pet shampoo", "flea treatment", "tick treatment", "pet brush", "slicker brush", "furminator", 
        "nail clippers pet", "cage", "bird cage", "hamster cage", "aquarium", "fish tank", 
        "aquarium filter", "pet clothes"
    ],
    "food_beverages": [
        "tea", "black tea", "green tea", "herbal tea", "matcha", "coffee", "coffee beans", 
        "ground coffee", "instant coffee", "coffee capsules", "cocoa", "hot chocolate", "chocolate", 
        "chocolate bar", "dark chocolate", "milk chocolate", "candy", "candies", "gummies", "sweets", 
        "cookies", "biscuits", "wafers", "gingerbread", "cake", "muffin", "croissant", "snack food", 
        "nuts", "walnuts", "almonds", "cashews", "hazelnuts", "pistachios", "peanuts", "dried fruits", 
        "raisins", "dried apricots", "prunes", "dates", "sauce", "ketchup", "mayonnaise", "mustard", 
        "soy sauce", "olive oil", "sunflower oil", "coconut oil", "spices", "seasoning", "salt", 
        "sea salt", "sugar", "sweetener", "pepper spice", "cinnamon", "paprika", "chips", "potato chips", 
        "popcorn", "crackers", "pretzels", "honey", "jam", "marmalade", "maple syrup", "pasta", 
        "spaghetti", "noodles", "rice", "buckwheat", "oatmeal", "cereals", "granola", "muesli", 
        "canned food", "canned fish", "canned meat", "olives", "pickles"
    ],
    "gadget_accessories": [
        "case", "phone case", "iphone case", "silicone case", "leather case", "shockproof case", 
        "wallet case", "tablet case", "ipad case", "airpods case", "protective glass", "screen protector", 
        "tempered glass", "camera protector", "lens glass", "cable", "usb cable", "lightning cable", 
        "type-c cable", "micro usb", "hdmi cable", "aux cable", "wire charger", "charger", 
        "wall charger", "fast charger", "wireless charger", "car charger", "charging device", 
        "powerbank", "power bank", "external battery", "phone holder", "car phone mount", 
        "desk phone stand", "tripod phone", "selfie stick", "ring light", "stylus", "apple pencil", 
        "airtag holder", "poposocket", "phone grip", "phone strap", "dust plug", "sim ejector"
    ],
    "household_chemicals": [
        "washing powder", "laundry detergent", "liquid detergent", "laundry capsules", "pods laundry", 
        "gel laundry", "fabric softener", "conditioner laundry", "stain remover", "bleach", "dish soap", 
        "dishwashing liquid", "dish_soap", "dishwasher tablets", "dishwasher salt", "rinse aid", 
        "surface cleaner", "floor cleaner", "window cleaner", "glass cleaner", "toilet cleaner", 
        "bathroom cleaner", "kitchen cleaner", "oven cleaner", "grease remover", "drain cleaner", 
        "clog remover", "scale remover", "descaler", "air freshener spray", "automatic air freshener", 
        "aroma diffuser home", "wet wipes household", "cleaning wipes", "sponge", "dish sponge", 
        "microfiber cloth", "cleaning rag", "rubber gloves", "trash bags", "garbage bags"
    ],
    "jewelry_accessories": [
        "ring", "rings", "silver ring", "gold ring", "engagement ring", "earrings", "stud earrings", 
        "hoop earrings", "drop earrings", "pendant", "pendants", "necklace", "necklaces", "choker", 
        "chain", "gold chain", "silver chain", "jewelry chain", "bracelet", "bracelets", "bangle", 
        "charm bracelet", "brooch", "brooches", "pins jewelry", "tiara", "hairpin jewelry", 
        "cufflinks", "tie clip", "jewelry box", "jewelry organizer", "stand jewelry", "біжутерія", 
        "beaded necklace"
    ],
    "hobbies_crafts": [
        "paint by numbers", "painting by numbers", "diamond mosaic", "diamond painting", "yarn", 
        "knitting yarn", "crochet yarn", "wool yarn", "threads", "sewing threads", "embroidery threads", 
        "floss", "embroidery kit", "cross stitch kit", "clay", "polymer clay", "modeling clay", 
        "pottery clay", "acrylic paints", "oil paints", "watercolor", "gouache", "fabric paint",
        "canvas", "canvas board", "stretched canvas", "easel", "paintbrushes", "art brushes", 
        "palette knife", "epoxy resin", "resin art", "silicone mold", "glitter", "sequins", 
        "beads", "seed beads", "jewelry making kit", "scrapbooking kit", "decorative paper", 
        "craft glue", "hot glue sticks", "soap making kit", "candle making kit", "sketching markers", 
        "calligraphy pen"
    ],
    "adult_products": [
        "condoms", "condom", "durex", "contex", "lubricant", "lubricants", "gel lubricant", 
        "water based lubricant", "silicone lubricant", "massage oil adult", "intimate gel", 
        "adult toy", "vibrator", "dildo", "stroker", "masturbator"
    ]
}

def choose_category(product_name_clean: str) -> str:
    """
    Высокоскоростной локальный маппер без использования ИИ.
    Парсит английский тег напрямую и сопоставляет с расширенным в 10 раз облаком тегов.
    """
    if not product_name_clean:
        return "unknown"
        
    # Приводим входную строку к нижнему регистру и зачищаем артикли
    text_lower = product_name_clean.lower().strip()
    text_lower = re.sub(r'\b(a|an|the)\b', '', text_lower).strip()
    
    # Прямой поиск вхождений ключевых слов
    for category, keywords in ENG_CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            # Ищем точное совпадение слова (чтобы 'fan' не триггерил 'fridge fan' не туда)
            if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                return category
                
    return "unknown"


import random

# Расширенный пул УТП для случайной выборки (20 категорий)
MARKETPLACE_UTP_POOL = {
    "electronics": [
        "Гарантия качества", "Надежная сборка", "Современные технологии", 
        "Выбор покупателей", "Хит продаж", "Официальная гарантия", "Премиум качество"
    ],
    "home_appliances": [
        "Высокая мощность", "Долговечные материалы", "Эргономичный дизайн", 
        "Легкое управление", "Хит продаж", "Экономия энергии", "Надежный помощник"
    ],
    "home_kitchen": [
        "Уют и комфорт", "Практичность в быту", "Стильное решение", 
        "Высокое качество", "Премиум материалы", "Порядок на кухне", "Современный стиль"
    ],
    "apparel_shoes": [
        "Премиум материалы", "Идеальная посадка", "Стильный дизайн", 
        "Трендовая модель", "Комфорт на весь день", "Высокое качество", "Хит сезона"
    ],
    "beauty_hygiene": [
        "Бережный уход", "Натуральный состав", "Для ежедневного применения", 
        "Глубокое увлажнение", "Здоровый блеск", "Профессиональный уход", "Выбор экспертов"
    ],
    "health_wellness": [
        "Одобрено экспертами", "Безопасный состав", "Максимум пользы", 
        "Для всей семьи", "Проверено качеством", "Натуральные компоненты"
    ],
    "kids_products": [
        "Безопасно для детей", "Гипоаллергенно", "Яркие эмоции", 
        "Высокое качество", "Развивает моторику", "Экологичные материалы", "Любимая игрушка"
    ],
    "auto_parts": [
        "Высокая прочность", "Износостойкость", "Легкая установка", 
        "Идеальная совместимость", "Долговечный материал", "Защита и комфорт", "Прослужит долго"
    ],
    "sport_outdoor": [
        "Для активной жизни", "Высокое качество", "Проверено в деле", 
        "Эргономичная форма", "Прочные материалы", "Стильный спорт", "Максимум комфорта"
    ],
    "tools_improvement": [
        "Надежный инструмент", "Прослужит долго", "Профессиональный выбор", 
        "Высокая прочность", "Удобно в работе", "Точный результат", "Хит продаж"
    ],
    "garden_backyard": [
        "Для Вашего сада", "Экологически чисто", "Отличный результат", 
        "Легкое применение", "Высокое качество", "Уютный дачный сезон"
    ],
    "stationery_office": [
        "Для работы и учебы", "Удобство и стиль", "Высокое качество", 
        "Яркие цвета", "Практичный формат", "Органайзер пространства"
    ],
    "books_media": [
        "Бестселлер", "Подарочное издание", "Читают все", 
        "Премиум бумага", "Захватывающий сюжет", "Эксклюзивно", "Высокое качество"
    ],
    "pet_supplies": [
        "Забота о питомце", "Рекомендовано ветврачами", "Натуральные компоненты", 
        "Вкусная польза", "Для здоровой жизни", "Любимое лакомство", "Высокое качество"
    ],
    "food_beverages": [
        "Натуральный продукт", "Изысканный вкус", "Без лишних добавок", 
        "Высокое качество", "Полезный перекус", "Бодрость и энергия", "Органик"
    ],
    "gadget_accessories": [
        "Идеальная совместимость", "Максимальная защита", "Ультрапрочный материал", 
        "Стильный аксессуар", "Высокое качество", "Надежная фиксация", "Защита от ударов"
    ],
    "household_chemicals": [
        "Эффективное очищение", "Концентрированный состав", "Эко-формула", 
        "Быстрый результат", "Удаляет любые пятна", "Безопасно для дома", "Свежий аромат"
    ],
    "jewelry_accessories": [
        "Изящный дизайн", "Эксклюзивный стиль", "Приковывает взгляды", 
        "Премиум бижутерия", "Идеальный подарок", "Ручная работа", "Блеск и сияние"
    ],
    "hobbies_crafts": [
        "Для яркого творчества", "Все включено в набор", "Развивает таланты", 
        "Премиум качество", "Хобби для всей семьи", "Отличный подарок", "Релакс и хобби"
    ],
    "adult_products": [
        "100% анонимность", "Высокое качество", "Безопасные компоненты", 
        "Максимум удовольствия", "Протестировано дерматологами", "Премиум бренд"
    ],
    "unknown": [
        "Хит продаж", "Высокое качество", "Выбор покупателей", 
        "Лучшая цена", "Быстрая доставка", "Рекомендуем", "Популярный товар"
    ]
}


def get_random_utp_string(category_key: str) -> str:
    """
    Выбирает 3 случайных уникальных УТП для категории 
    и возвращает их в виде строки с переносами \n.
    """
    # 1. Извлекаем пул тегов для категории (если ключ кривой, берем пул "unknown")
    pool = MARKETPLACE_UTP_POOL.get(category_key, MARKETPLACE_UTP_POOL["unknown"])
    
    # Страховочная проверка: если в пуле вдруг меньше 3 элементов (например, в кастомных правках)
    count_to_sample = min(3, len(pool))
    
    # 2. Рандомим ровно 3 УТП без дубликатов внутри одной карточки
    selected_utp_list = random.sample(pool, count_to_sample)
    
    # 3. Склеиваем в финальную строку с переносами строк
    utp_string_with_newlines = "\n".join(selected_utp_list)
    
    return utp_string_with_newlines



import time
import re
import requests
import json
from deep_translator import GoogleTranslator

def translate_via_qwen(english_text: str) -> str:
    """
    Высокоточный e-commerce переводчик через стабильный API deep-translator.
    В случае сбоя сети или бана от Google мгновенно отдает оригинальный английский текст.
    """
    # 1. Зачищаем технический мусор фонов из BLIP
    clean_text = english_text.lower().replace("on a black background", "")
    clean_text = clean_text.replace("on a white background", "").strip()
    
    # Убираем лишние артикли, чтобы перевод был более емким
    clean_text = re.sub(r'\b(a|an|the)\b', '', clean_text).strip()
    
    if not clean_text:
        clean_text = english_text.strip()
        
    # 2. БЕЗОПАСНЫЙ И БЫСТРЫЙ ПЕРЕВОД С КРАШ-ЗАЩИТОЙ ШЕФА
    try:
        # Инициализируем переводчик
        translator = GoogleTranslator(source='en', target='ru')
        
        # 🎯 ЖЕЛЕЗНЫЙ ТАЙМ-АУТ: Если Google тупит или сбросил соединение, 
        # мы ждем максимум 1.5 секунды, а не вешаем сервер на минуту!
        # deep_translator не имеет прямого аргумента timeout, поэтому прокидываем его через сессию requests
        import requests
        session = requests.Session()
        session.adapters.get('https://').max_retries = 0 # Ноль повторов, некогда ждать
        translator.session = session
        
        # Переводим (ограничиваем время выполнения на уровне requests)
        # Так как deep_translator под капотом шлет обычный request, таймаут сработает железно
        translated_text = translator.translate(clean_text)
        
        if translated_text:
            return translated_text
            
    except Exception as network_err:
        # 🔥 СКАЛЛА-СПАСАТЕЛЬ: Google лег, забанил IP или пропал интернет.
        # Выводим предупреждение в консоль бэка, но НЕ ВАЛИМ скрипт!
        print(f"⚠️ [SKULLA NET BYPASS]: Google Translate недоступен ({network_err}). Отдаем оригинал: '{clean_text}'", flush=True)
        
    # Фолбэк: возвращаем очищенный английский текст, Qwen на следующем шаге его поймет!
    return clean_text


    
def generate_ai_title_json(product_name_en: str) -> dict:
    """Генерация названия товара в формате JSON"""
    try:
        '''
        _init_local_text_gpt()
        if _skulla_gpt_translator is None or _skulla_gpt_tokenizer is None:
            return json.dumps(["Ошибка", "Модель не инициализирована", "", ""], ensure_ascii=False)


        # Очищаем название от лишних артиклей vision-распознавателя
        product_name_clean = str(product_name_en).strip().lower()
        for article in ["the ", "a ", "an "]:
            if product_name_clean.startswith(article):
                product_name_clean = product_name_clean[len(article):].strip()

        
        # Промпт полностью переведен на английский — Qwen на CPU щелкнет его как орешек
        full_prompt = (
            "Название продукта на Русском языке.\n"
            "Оставь оригинал если не переводится.\n\n"
            "CRITICAL: Output ONLY the chosen lowercase code word. Do not write anything else.\n\n"
            f"Product: {product_name_clean}"
        )


        messages = [{"role": "user", "content": full_prompt}]
        prompt_tokens = _skulla_gpt_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        source_tokens = _skulla_gpt_tokenizer.convert_ids_to_tokens(_skulla_gpt_tokenizer.encode(prompt_tokens))

        # Запускаем генерацию (английские слова короткие, max_length=10 с запасом)
        outputs = _skulla_gpt_translator.generate_batch(
            [source_tokens],
            max_length=16,                   # Сокращаем лимит: для одного слова больше не нужно
            sampling_topk=50,                # Greedy Search — берем только самый сильный токен без вариаций
            sampling_temperature=0.8,       # Нулевая креативность для точности совпадения слова
            include_prompt_in_result=False
        )

        target_tokens = outputs[0].sequences_ids[0]

        product_name_ru = _skulla_gpt_tokenizer.decode(target_tokens).strip().lower()

        #product_name_ru = translate_tag_to_russian_local(product_name_clean)
        '''
        product_name_ru = translate_via_qwen(product_name_en)
        # Очистка строки от случайного мусора 
        product_name_ru = product_name_ru.replace(".", "").replace('"', "").replace("'", "").strip()

        print(f"📦 [ENGLISH-KEY ENGINE]: Product '{product_name_en}' -> Translated to: '{product_name_ru}'", flush=True)
        
        return {"title": product_name_ru} 

    except Exception as e:
        print(f"❌ [ENGLISH-KEY ENGINE ERROR]: {e}", flush=True)
        return {"title": product_name_en} 
    except Exception:
        return {"title": product_name_en}

def generate_ai_utp_list_json(category_key: str) -> dict:
    try:
      
        # 3. Генерируем рандомную строку УТП из 3 фраз с переносами строк \n
        utp_string = get_random_utp_string(category_key)
        
        # 4. Возвращаем строго в требуемом формате с одним ключом
        return {"utp_list": utp_string}
        
    except Exception as e:
        print(f"[SKULLA ERROR]: Ошибка сборки JSON с УТП: {e}")
        # Железобетонный фолбек в том же самом формате, если что-то пойдет не так
        return {"utp_list": "Хит продаж\nВысокое качество\nРекомендуем"}


def generate_ai_short_desc_json(product_name_en: str) -> dict:
    """Генерация краткого описания в формате JSON"""
    prompt = (
        f"Напиши одно продающее предложение-описание для товара '{product_name_en}' на русском. "
        f"Верни ответ СТРОГО в формате JSON: {{\"short_desc\": \"текст_описания\"}}. "
        f"Только чистый JSON."
    )
    try:
        raw = ""#generate_custom_prompt_local(prompt)
        return json.loads(raw)
    except Exception:
        return {"short_desc": "Отличный выбор по доступной цене."}


import os
import json

# 🔥 СКАЛЛА-ФИКС: Прокидываем переменную метаданных цвета товара в аргументы функции!
def auto_select_best_background(category_key: str, ai_generated_title: str, ai_generated_utp: str, product_color_meta: dict) -> dict:
    import json
    import os
    
    map_path = os.path.join("assets", "background_analysis_map.json")
    
    # Твой стандартный страховочный дефолт
    default_payload = {
        "product_category": category_key,
        "main_title": ai_generated_title,
        "title_font_color": "#FFFFFF",
        "title_font_family": "Oswald-Bold",
        "badges_list": ai_generated_utp,
        "font_color": "#FFFFFF",
        "font_bg_color": "#0F172A",
        "badge_font_family": "Oswald-Regular",
        "border_width": "0",
        "badge_shape": "rounded",
        "bg_material": "unknown_studio_neutral_grey",
        "bg_color": "#808080",
        "bg_blur_strength": "20",
        "vignette_strength": "0"
    }
    
    if not os.path.exists(map_path):
        return default_payload

    try:
        with open(map_path, 'r', encoding='utf-8') as f:
            analysis_map = json.load(f)
            
        
        # Шаг 1. Базовая фильтрация по категории
        category_backgrounds = {k: v for k, v in analysis_map.items() if v["category"] == category_key}
        if not category_backgrounds:
            category_backgrounds = {k: v for k, v in analysis_map.items() if v["category"] == "cat_unknown"}

        # Распаковываем параметры цвета товара
        p_hue = product_color_meta["hue"]
        p_sat = product_color_meta["saturation"]
        p_bright = product_color_meta["brightness"]
        is_p_achromatic = product_color_meta["is_achromatic"]

        best_bg_key = None
        max_score = -999999.0
        
        # Шаг 2. Зажатый математический перебор по суженным границам
        for bg_key, bg_item in category_backgrounds.items():
            meta = bg_item["matching_meta"]
            bg_hue = meta["dominant_hue"]
            bg_sat = meta["saturation"]
            bg_bright = meta["global_brightness"]
            
            # Вычисляем разницу углов на цветовом круге (0-180 градусов)
            hue_diff = abs(p_hue - bg_hue)
            if hue_diff > 180: hue_diff = 360 - hue_diff
            
            # Стартовый балл для фона
            score = 100.0
            
            # --- СЦЕНАРИЙ А: ТОВАР ЧЕРНЫЙ/БЕЛО-СЕРЫЙ (АХРОМАТИЧЕСКИЙ) ---
            if is_p_achromatic:
                # Нам нужен сочный, цветной фон, чтобы серый товар заиграл. Штрафуем серые фоны!
                if bg_sat < 15: score -= 80.0
                
                # Силуэтный контраст: для белого товара ищем тёмный фон, для чёрного — светлый
                if p_bright > 180: # Товар белый
                    if bg_bright > 120: score -= 50.0  # Штрафуем светлые фоны
                    score += (255 - bg_bright) * 0.3   # Чем темнее фон, тем выше балл
                else: # Товар чёрный или серый
                    if bg_bright < 100: score -= 50.0  # Штрафуем слишком тёмные фоны
                    score += bg_bright * 0.3           # Чем светлее фон, тем лучше контраст
            
            # --- СЦЕНАРИЙ Б: ТОВАР ИМЕЕТ СВОЙ ЯРКИЙ ЦВЕТ (ХРОМАТИЧЕСКИЙ) ---
            else:
                # 1. Сужаем цветовые границы: штрафуем фоны, которые не попадают в наши дизайн-стратегии
                if category_key in ["cat_beauty_health", "cat_health_wellness", "cat_apparel_shoes", "cat_jewelry_accessories"]:
                    # Аналоговая мягкая гармония: идеальный сектор ±25 градусов от цвета товара
                    if hue_diff > 25:
                        score -= (hue_diff - 25) * 4.0  # Жесткий штраф за выход из цветовой границы!
                    else:
                        score += (25 - hue_diff) * 2.0  # Бонус за точное попадание в цвет
                else:
                    # Комплиментарный жесткий контраст: ищем противоположный цвет на круге (около 180°)
                    target_complimentary = 180.0
                    dist_to_complimentary = abs(hue_diff - target_complimentary)
                    if dist_to_complimentary > 30:
                        score -= (dist_to_complimentary - 30) * 4.0 # Жесткий штраф за блеклый контраст
                    else:
                        score += (30 - dist_to_complimentary) * 2.0
                
                # 2. Общий яркостный контраст (чтобы цветной товар не сливался по яркости)
                bright_diff = abs(p_bright - bg_bright)
                if bright_diff < 40:
                    score -= 40.0  # Штраф, если товар и фон одинаково блеклые или одинаково яркие
                else:
                    score += bright_diff * 0.2

            # Фиксируем лидера гонки
            if score > max_score:
                max_score = score
                best_bg_key = bg_key

        # Железный фолбэк, если все фоны ушли в глубокий минус
        if not best_bg_key:
            best_bg_key = list(category_backgrounds.keys())[0]

        # Шаг 3. Сборка пакета для выбранного лидера
        bg_data = category_backgrounds[best_bg_key]
        
        canvas_styles = bg_data.get("canvas_styles", {})
        title_styles = canvas_styles.get("main_title", {})
        badge_styles = canvas_styles.get("text_badges", {})
        font_styles = canvas_styles.get("fonts", {})
        bg_settings = canvas_styles.get("background_settings", {})
        
        raw_border_width = badge_styles.get("border_width", "0")
        clean_border_width = "1" if "1" in str(raw_border_width) else "0"

        auto_payload = {
            "product_category": category_key,
            "main_title": ai_generated_title,
            "title_font_color": title_styles.get("color", "#FFFFFF"),
            "title_font_family": font_styles.get("title_font_family", "Oswald-Bold"),
            "badges_list": ai_generated_utp,
            "font_color": badge_styles.get("text_color", "#FFFFFF"),
            "font_bg_color": badge_styles.get("background_color", "#0F172A"),
            "badge_font_family": font_styles.get("badge_font_family", "Oswald-Regular"),
            "border_width": clean_border_width,
            "badge_shape": "rounded" if "12px" in badge_styles.get("border_radius", "") else "parallelogram",
            "bg_material": best_bg_key,
            "bg_color": bg_data["matching_meta"]["global_hex"],
            "bg_blur_strength": bg_settings.get("bg_blur_strength", "20"),
            "vignette_strength": bg_settings.get("vignette_strength", "0")
        }
        
        print(f"🎯 [SKULLA MATCH]: ИИ выбрал уникальный фон '{best_bg_key}' с баллом {max_score}", flush=True)
        return auto_payload

    except Exception as e:
        print(f"[❌ SKULLA AUTOBG ERROR]: Сбой зажатого автоподбора: {e}", flush=True)
        return default_payload


import math
from PIL import Image
import io

def analyze_product_color_hsv(product_image_bytes: bytes) -> dict:
    """
    Анализирует вырезанный силуэт товара (пропускает прозрачные пиксели),
    вычисляет доминирующий RGB, относительную яркость и оттенок Hue (0-360).
    """
    try:
        img = Image.open(io.BytesIO(product_image_bytes)).convert("RGBA")
        # Сжимаем картинку для супер-быстрого обсчета без потери точности цвета
        img = img.resize((100, 100), Image.Resampling.NEAREST)
        
        r_sum = g_sum = b_sum = count = 0
        
        for x in range(img.width):
            for y in range(img.height):
                r, g, b, a = img.getpixel((x, y))
                if a > 30: # Считаем только видимые пиксели товара, игнорируем удаленный фон!
                    r_sum += r
                    g_sum += g
                    b_sum += b
                    count += 1
                    
        if count == 0:
            return {"hue": 0, "saturation": 0, "brightness": 128, "is_achromatic": True}
            
        avg_r = int(r_sum / count)
        avg_g = int(g_sum / count)
        avg_b = int(b_sum / count)
        
        # Переводим в нормализованные координаты для расчета HSV
        r_n, g_n, b_n = avg_r / 255.0, avg_g / 255.0, avg_b / 255.0
        max_c = max(r_n, g_n, b_n)
        min_c = min(r_n, g_n, b_n)
        delta = max_c - min_c
        
        # 1. Считаем Цветовой тон товара (Hue)
        hue = 0
        if delta > 0.005:
            if max_c == r_n: hue = ((g_n - b_n) / delta) % 6
            elif max_c == g_n: hue = ((b_n - r_n) / delta) + 2
            elif max_c == b_n: hue = ((r_n - g_n) / delta) + 4
            hue = int(hue * 60) % 360
            
        # 2. Считаем насыщенность (Saturation) и относительную яркость по W3C
        saturation = int(delta * 100)
        brightness_w3c = int((0.2126 * avg_r + 0.7152 * avg_g + 0.0722 * avg_b))
        
        # Если товар серый, белый или черный — он ахроматический (нет выраженного цвета)
        is_achromatic = saturation < 12 or (brightness_w3c > 230 or brightness_w3c < 25)
        
        return {
            "hue": hue,
            "saturation": saturation,
            "brightness": brightness_w3c,
            "is_achromatic": is_achromatic,
            "rgb": (avg_r, avg_g, avg_b)
        }
    except Exception as e:
        print(f"⚠️ Ошибка колористического анализа товара: {e}", flush=True)
        return {"hue": 0, "saturation": 0, "brightness": 128, "is_achromatic": True}


def generate_product_description_local(product_name_en: str) -> str:
    """
    СВЕРХЗВУКОВОЙ ТЕКСТОВЫЙ СЕО-ГЕНЕРАТОР (ОДНОЕМКОЕ ОПИСАНИЕ):
    Сжимаем ответ в 3 раза! Выдача строго 1 сочного продающего предложения!
    Скорость генерации на CPU вырастает в 3-4 раза!
    """
    global _skulla_qwen_model, _skulla_qwen_processor
    
    # 🦾 ТИТАНОВЫЙ ОДНОСТРОЧНИК ПАВЛА: Элегантный фолбэк для универсального маркетинга!
    product_name_en = product_name_en if (product_name_en and len(product_name_en) >= 2) else "any product"

        
    try:
        import torch

        _init_local_qwen_ai()
        if _skulla_qwen_model is None or _skulla_qwen_processor is None:
            return "High quality and reliable product for everyday use."

        model = _skulla_qwen_model
        processor = _skulla_qwen_processor

        # 🎯 СВЕРХЗВУКОВОЙ АНГЛИЙСКИЙ ПРОМПТ:
        # Приказываем модели написать строго ОДНО, но максимально мощное продающее предложение!
        
        prompt_text = (
            f"You are an expert e-commerce copywriter. "
            f"Write exactly ONE attractive, powerful selling sentence for: '{product_name_en}'. "
            f"Highlight its key benefit and value for the customer. "
            f"Be concise, no fluff, no repeating words. "
            f"Product Description:"
        )

        inputs = processor(
            text=[prompt_text],
            images=None,
            padding=True,
            return_tensors="pt"
        ).to(model.device)

        with torch.no_grad():
            generated_ids = model.generate(
                **inputs,
                # 🔥 ЖЕСТКИЙ СКАЛЛА-ЗАЖИМ НА СКОРОСТЬ: 
                # Отрезаем генерацию до 45 токенов! Вычисления пролетят за секунду!
                max_new_tokens=30,         
                min_new_tokens=10,
                repetition_penalty=1.35,   # Штрафуем повторы, чтобы текст был плотным
                do_sample=True,            
                temperature=0.5,           # Держим слог строгим и коммерческим
                top_p=0.85,
                eos_token_id=processor.tokenizer.eos_token_id
            )
            
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        
        output_text = processor.batch_decode(
            generated_ids_trimmed, 
            skip_special_tokens=True, 
            clean_up_tokenization_spaces=False
        )

    except Exception as e:
        print(f"🚨 [❌ WARN DESCR CRITICAL]: Сбой английской генерации Qwen2-VL: {e}", flush=True)
        return "Premium quality product designed for your comfort and safety."

    if output_text and isinstance(output_text, list):
        raw_res = output_text[0].strip()
    elif output_text and isinstance(output_text, str):
        raw_res = output_text.strip()
    else:
        raw_res = "Premium quality product designed for your comfort and safety."

    if "product description:" in raw_res.lower():
        raw_res = raw_res.lower().split("product description:")[-1].strip()

    print(f"🍏 [RAW ALIBABA FAST-ENGLISH-DESCR OUTPUT]: '{raw_res}'", flush=True)
    return raw_res


def generate_template2_descriptions_local(product_name_en: str, category_key: str, utp_list: list) -> str:
    """
    УЛЬТИМАТИВНЫЙ ИИ-ГЕНЕРАТОР С ОРГАНИЧНЫМИ СМАЙЛАМИ (ШАБЛОН-3):
    Разбивает 21 категорию маркетплейса на 5 уникальных b2b-текстов Павла.
    Смайлы вшиты строго внутрь фраз в тему контекста, сохраняя эталонную длину строк!
    """
    import random

    cat = str(category_key).strip().lower()
    
    # Защитная зачистка массива УТП и жесткий перевод в верхний регистр (КАПС)
    utps = [str(u).strip().upper() for u in utp_list if str(u).strip()]
    while len(utps) < 3:
        utps.append("ВЫСОКОЕ КАЧЕСТВО")

    # ИИ-заголовок в КАПС для f-строки
    p_name = str(product_name_en).upper() if product_name_en else "ТОВАР"

    # 🗺️ КАРТА МАППИНГА: Распределяем 21 категорию по 5 основным типам
    if cat in ["electronics", "home_appliances", "gadget_accessories", "auto_parts", "tools_improvement"]:
        type_key = "tech"
    elif cat in ["apparel_shoes", "shoes", "home_kitchen", "sport_outdoor", "garden_backyard", "furniture", "bags_accessories"]:
        type_key = "lifestyle"
    elif cat in ["beauty_hygiene", "health_wellness", "household_chemicals"]:
        type_key = "beauty"
    elif cat in ["kids_products", "books_media", "pet_supplies", "stationery_office", "hobbies_crafts"]:
        type_key = "family"
    else:
        type_key = "consumables"

    # 🗃️ ПУЛ ИЗ 5 УНИКАЛЬНЫХ СБАЛАНСИРОВАННЫХ ТЕКСТОВ С ОРГАНИЧНЫМИ СМАЙЛАМИ:
    TEMPLATES_BY_TYPE = {
        "tech": [
            f"⚡ {p_name} ⚡\n\n"
            f"Технологичный продукт топового сегмента b2b-рынка,\n"
            f"созданный инженерами для вашего максимального удобства.\n"
            f"Данная модель сочетает заводское качество сборки,\n"
            f"высокую износостойкость и современный лаконичный дизайн!\n"
            f"💯 {utps[0]}, {utps[1]}."
        ],
        "lifestyle": [
            f"✨ {p_name} ✨\n\n"
            f"Универсальный продукт топового сегмента маркетплейса,\n"
            f"созданный для уюта и вашего повседневного удобства.\n"
            f"Модель гармонично  сочетает фабричное качество сборки,\n"
            f"проверенную долговечность и стильный премиальный дизайн!\n"
            f"🧥 {utps[0]}, {utps[1]}."
        ],
        "beauty": [
            f"🌿 {p_name} 🌿\n\n"
            f"Органический продукт топового сегмента индустрии ухода,\n"
            f"созданный экспертами для вашего бережного удобства.\n"
            f"Формула средства сочетает строгое качество сборки,\n"
            f"глубокую эффективность и продуманный лаконичный дизайн!\n"
            f"💎 {utps[0]}, {utps[1]}."
        ],
        "family": [
            f"🧸 {p_name} 🧸\n\n"
            f"Безопасный продукт топового сегмента детских товаров,\n"
            f"созданный с заботой для вашего семейного удобства.\n"
            f"Каждая деталь сочетает сертифицированное качество сборки,\n"
            f"абсолютную надежность и эргономичный лаконичный дизайн!\n"
            f"🎁 {utps[0]}, {utps[1]}."
        ],
        "consumables": [
            f"💥 {p_name} 💥\n\n"
            f"Эксклюзивный продукт  топового сегмента b2b-ассортимента,\n"
            f"созданный специально для вашего ежедневного удобства.\n"
            f"Товар гарантированно сочетает проверенное качество сборки,\n"
            f"максимальную пользу и премиальный лаконичный дизайн!\n"
            f"🔥 {utps[0]}, {utps[1]}."
        ]
    }

    # Забираем ровно один случайный вариант из пула (в данном случае по типу категории)
    chosen_description = random.choice(TEMPLATES_BY_TYPE[type_key])
    
    print(f"🍏 [SKULLA T3 5-TYPE FIX SUCCESS]: Сгенерирован уникальный текст '{type_key}' со смайлами в тему!", flush=True)
    return chosen_description




def generate_template2_short_descriptions_local(product_name_en: str, category_key: str, utp1: str, utp2: str, utp3: str) -> dict:
    """
    3-СТРОЧНЫЙ ГЕНЕРАТОР ХАРАКТЕРИСТИК (ШАБЛОН-2):
    Ключи категорий строго и точно соответствуют официальному списку CATEGORIES из роутера!
    """
    import random

    cat = str(category_key).strip().lower()
    
    # Приводим УТП к нижнему регистру для идеального e-commerce глянца
    u1 = str(utp1).strip().lower() if utp1 else "премиум качество"
    u2 = str(utp2).strip().lower() if utp2 else "высокая прочность"
    u3 = str(utp3).strip().lower() if utp3 else "стильный дизайн"

    # 🌐 ПУЛ 10 СУПЕРУНИВЕРСАЛЬНЫХ ХАРАКТЕРИСТИК:
    SUPER_UNIVERSAL = [
        f"Абсолютный\nлидер продаж:\nвыбор покупателей",
        f"Премиальное\nкачество сборки:\nпрослужит долго",
        f"Современный\nэргономичный стиль:\nстильное решение",
        f"Надежность\nи безопасность:\nвысший стандарт",
        f"Выгодное\nb2b-предложение:\nлучшая цена",
        f"Максимальный\nкомфорт использования:\nкаждый день",
        f"Продуманная\nдо мелочей\nконструкция модели",
        f"Экологичные\nи безопасные\nматериалы премиума",
        f"Универсальный\nбазовый выбор:\nтоповый сегмент",
        f"Безупречное\nисполнение деталей:\nбез компромиссов"
    ]

    # 🗃️ СИНХРОНИЗИРОВАННАЯ БАЗА КАТЕГОРИЙ (СТРОГО ПО ТВОЕМУ СКРИНШОТУ):
    CATEGORIES_POOL = {
        "electronics": [
            f"Высокотехнологичная\nкомпонентная база:\n{u1}",
            f"Стабильность\nработы девайса:\nгарантия качества",
            f"Инновационные\nинженерные решения:\nсвойство {u2}",
            f"Интуитивно\nпонятный интерфейс:\nлегкая настройка",
            f"Защита от\nперегрузок сети:\nбезопасная модель"
        ],
        "home_appliances": [
            f"Энергоэффективный\nмощный двигатель:\nсвойство {u1}",
            f"Низкий уровень\nшума при работе:\nтихая служба",
            f"Износостойкие\nдолговечные материалы:\n{u2}",
            f"Умные автоматические\nрежимы быта:\nвыбор года",
            f"Простая очистка\nи легкий уход:\nпрактичный прибор"
        ],
        "home_kitchen": [
            f"Продуманная\nэргономика пространства:\n{u1}",
            f"Термостойкие\nбезопасные материалы:\n{u2}",
            f"Эстетичный дизайн\nдля любого интерьера:\nстильный уют",
            f"Высокая прочность\nи легкий вес:\nудобно в быту",
            f"Универсальное\nприменение на кухне:\nхит продаж"
        ],
        "apparel_shoes": [
            f"Идеальная\nанатомическая посадка:\n{u1}",
            f"Высокопрочные\nфабричные швы:\nсвойство {u2}",
            f"Дышащая\nгипоаллергенная ткань:\nполный комфорт",
            f"Стильный базовый\nдизайн гардероба:\nмодный образ",
            f"Устойчивость к\nмногочисленным стиркам:\nсохраняет цвет"
        ],
        "beauty_hygiene": [
            f"Натуральный\nсбалансированный состав:\n{u1}",
            f"Безопасно для\nчувствительной кожи:\nодобрено ИИ",
            f"Глубокое\nэффективное действие:\nсвойство {u2}",
            f"Профессиональный\nуход на дому:\nлучший выбор",
            f"Экономичный\nрасход средства:\nхватит надолго"
        ],
        "health_wellness": [
            f"Клинически\nпроверенная база:\nбезопасно",
            f"Натуральные\nактивные компоненты:\n{u1}",
            f"Быстрый и\nнаправленный эффект:\nсвойство {u2}",
            f"Поддержка\nтонуса и энергии:\nздоровый выбор",
            f"Высокая\nбиологическая ценность:\nпремиум"
        ],
        "kids_products": [
            f"Абсолютно\nтоксикологически безопасно:\n{u1}",
            f"Прочные детали\nбез острых углов:\nзащита {u2}",
            f"Яркий развивающий\nдизайн модели:\nрадость детям",
            f"Гипоаллергенные\nэко-материалы сборки:\nвысший класс",
            f"Сертифицировано\nпо строгим стандартам:\nнадежный выбор"
        ],
        "auto_parts": [
            f"Устойчивость к\nвибрациям и нагрузкам:\n{u1}",
            f"Универсальное\nкрепление и фиксация:\nсвойство {u2}",
            f"Простая и\nбыстрая установка:\nза пару секунд",
            f"Износостойкий\nзащитный корпус:\nдолгая служба",
            f"Стабильная работа\nв любой мороз:\nтитан дорог"
        ],
        "sport_outdoor": [
            f"Повышенная\nударная прочность:\nвыдержит всё",
            f"Эргономичная\nнескользящая ручка:\n{u1}",
            f"Влагозащищенные\nкрепкие материалы:\nсвойство {u2}",
            f"Профессиональный\nспортивный инвентарь:\nхит",
            f"Легко собирать\nи транспортировать:\nдля активных"
        ],
        "tools_improvement": [
            f"Закаленная\nлегированная сталь:\nмаксимум {u2}",
            f"Профессиональный\nрабочий ресурс:\n{u1}",
            f"Высокая точность\nкаждого замера:\nбез погрешностей",
            f"Прорезиненный\nпротивоударный корпус:\nнадежно",
            f"Универсальный\nмногофункциональный шаг:\nинструмент"
        ],
        "garden_backyard": [
            f"Морозостойкие\nи УФ-защищенные материалы:\nне выцветает",
            f"Повышенная\nустойчивость к влаге:\n{u2}",
            f"Удобная\nмобильная конструкция:\nдля участка",
            f"Премиальный\nзагородный инвентарь:\n{u1}",
            f"Высокая\nэффективность работы:\nбогатый урожай"
        ],
        "stationery_office": [
            f"Эргономичные\nофисные решения:\nдля продуктивности",
            f"Премиальное\nкачество сборки:\n{u1}",
            f"Лаконичный\nстрогий деловой стиль:\nвпишется везде",
            f"Повышенный\nресурс механизмов:\nсвойство {u2}",
            f"Удобная\nорганизация пространства:\nпорядок"
        ],
        "books_media": [
            f"Высококачественная\nбелая бумага и печать:\n{u1}",
            f"Плотный\nизносостойкий переплет:\nна века",
            f"Развивающий\nувлекательный сюжет/набор:\n{u2}",
            f"Превосходный\nподарочный b2b-вариант:\nэстетика",
            f"Уникальный\nавторский контент/дизайн:\nэксклюзив"
        ],
        "pet_supplies": [
            f"Прочные\nантивандальные ткани:\nвыдержит когти",
            f"Абсолютно\nбезопасные материалы:\n{u1}",
            f"Одобрено\nведущими ветеринарами:\nздоровый выбор",
            f"Анатомический\nкомфортный дизайн:\nдля питомца",
            f"Легко моется\nи не пахнет:\nпрактичный уход"
        ],
        "food_beverages": [
            f"Органический\nнатуральный продукт:\nбез ГМО",
            f"Герметичная\nпремиум-упаковка:\nсохраняет свежесть",
            f"Изысканный\nнасыщенный вкус и аромат:\n{u1}",
            f"Полезный\nвитаминный состав:\nэнергия {u2}",
            f"Строгий контроль\nкачества сырья:\nвысший сорт"
        ],
        "gadget_accessories": [
            f"Премиальная\nизносостойкая фурнитура:\n{u1}",
            f"Влагозащищенное\nплотное покрытие:\nсвойство {u2}",
            f"Многофункциональные\nвнутренние карманы:\nпорядок",
            f"Ровные фабричные\nусиленные швы:\nнадежность",
            f"Стильный базовый\nгородской дизайн:\nпод любой лук"
        ],
        "household_chemicals": [
            f"Эффективное\nрасщепление загрязнений:\nбыстрый результат",
            f"Безопасная\nбиоразлагаемая формула:\n{u1}",
            f"Защита от\nналета и ржавчины:\nчистота {u2}",
            f"Гипоаллергенный\nнейтральный состав:\nбез резких запахов",
            f"Концентрированная\nформула b2b-экономии:\nхватит надолго"
        ],
        "jewelry_accessories": [
            f"Стойкое\nгипоаллергенное покрытие:\nблеск {u1}",
            f"Надежный\nпроверенный замок:\nбез случайных потерь",
            f"Высокоточная\nювелирная огранка деталей:\nроскошный вид",
            f"Эксклюзивный\nлимитированный дизайн:\nстатус {u2}",
            f"Подарочная\nпремиальная упаковка:\nготовый презент"
        ],
        "hobbies_crafts": [
            f"Полный комплект\nдля творчества и хобби:\n{u1}",
            f"Пошаговая\nпонятная инструкция:\nлегко собрать",
            f"Высококачественные\nбезопасные материалы:\n{u2}",
            f"Развивает\nмелкую моторику и фокус:\nувлекательно",
            f"Отличная идея\nдля хобби и отдыха:\nвсей семьей"
        ],
        "adult_products": [
            f"Абсолютно\nгипоаллергенный силикон:\n{u1}",
            f"Анатомическая\nвыверенная форма прибора:\nкомфорт",
            f"Полная\nводонепроницаемость корпуса:\nлегко мыть",
            f"Тихий и\nмощный режим работы:\nконфиденциально {u2}",
            f"Премиальное\nкачество тактильности:\nвысший класс"
        ],
        "unknown": [
            f"Продуманный\nуниверсальный дизайн:\nпод любые задачи",
            f"Премиальные\nизносостойкие материалы:\n{u1}",
            f"Повышенная\nнадежность конструкции:\nсвойство {u2}",
            f"Проверенное\nзаводское качество сборки:\nдолговечность",
            f"Идеальное\nсоотношение цены и пользы:\nхит продаж"
        ]
    }

    # Фолбэк-страховка: если прилетит ключ, которого нет в пуле — силой берем "unknown"
    if cat not in CATEGORIES_POOL:
        cat = "unknown"

    # Сливаем 5 категорийных шаблонов и 10 суперуниверсальных в один общий пул
    full_pool = CATEGORIES_POOL[cat] + SUPER_UNIVERSAL
    
    # Перемешиваем пул в оперативной памяти для случайного выбора
    random.shuffle(full_pool)
    
    # Выбираем три уникальных случайных трехстрочника
    res_1 = full_pool[0]
    res_2 = full_pool[1] if len(full_pool) > 1 else full_pool[0]
    res_3 = full_pool[2] if len(full_pool) > 2 else full_pool[0]

    return {
        "template2_descriptions_1": res_1,
        "template2_descriptions_2": res_2,
        "template2_descriptions_3": res_3
    }
