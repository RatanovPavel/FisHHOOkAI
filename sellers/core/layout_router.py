import os
import math
from PIL import Image, ImageFont
from core.vision import draw_universal_badge  # Наш эталонный попиксельный движок плашек

class SkullaLayoutRouter:
    @staticmethod
    def distribute_badges(
        canvas, font_path, font_size, raw_text, shape, padding, radius, skew_px,
        bg_color, bg_alpha, border_color, border_alpha, border_width, text_color,
        layout_type="vertical_stack", side_position="left", margin_bounds=95
    ):
        """
        Интеллектуальный роутер авто-расстановки плашек Студии Skulla Core.
        🎯 СИНХРОНИЗАЦИЯ СЕТКИ: Всегда рассчитывает шаги и координаты в Full HD масштабе 900x1200!
        🎯 ЗАЩИТА ОТ ОБРЕЗКИ: Автоматически масштабирует шаги для превью холста!
        """
        # 1. Парсим и чистим список текстов селлера
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        if not lines:
            return

        # Замеряем физический размер целевого холста (450x600 или 900x1200)
        CURRENT_W, CURRENT_H = canvas.size
        is_preview = (CURRENT_W == 450)

        # 📐 РОУТЕР ВСЕГДА ВЫЧИСЛЯЕТ ФИЗИКУ СЕТКИ В FULL HD КAЧEСТВE!
        W, H = 900, 1200
        
        # Зазоры и стартовые привязки всегда эталонные Full HD
        start_y = int(H * 0.18) 
        gap_y = 30 

        # Коэффициент обратного сжатия координат для вызова ядра: 0.5 на превью, 1.0 на фулле
        scale_coord = 0.5 if is_preview else 1.0

        # 🎯 РЕЖИМ 1: ВЕРТИКАЛЬНЫЙ СТЕК (Классика: плашки друг под другом слева или справа)
        if layout_type == "vertical_stack":
            align_x = "left_bound" if side_position == "left" else "right_bound"
            
            for text_line in lines:
                # Делим start_y на 2 на превью, чтобы ядро правильно поняло координату посадки
                badge_info = draw_universal_badge(
                    canvas=canvas, text=text_line.upper(), font_path=font_path, font_size=font_size,
                    position=(0, int(start_y * scale_coord)), align_x=align_x, align_y="absolute",
                    padding=padding, shape=shape, radius=radius, skew_px=skew_px,
                    bg_color=bg_color, bg_alpha=bg_alpha, border_color=border_color,
                    border_alpha=border_alpha, border_width=border_width, text_color=text_color,
                    margin_bounds=margin_bounds
                )
                # Из-за того, что ядро вернуло адаптированные габариты, для HD шага роутера восстанавливаем масштаб!
                badge_h_hd = int(badge_info["height"] * 2) if is_preview else int(badge_info["height"])
                start_y += int(badge_h_hd + gap_y)

        # 🎯 РЕЖИМ 2: ШАХМАТНЫЙ ЗИГЗАГ (Плашки прыгают: лево -> право -> лево)
        elif layout_type == "zigzag":
            current_side = side_position if side_position in ["left", "right"] else "left"
            
            for text_line in lines:
                align_x = "left_bound" if current_side == "left" else "right_bound"
                
                badge_info = draw_universal_badge(
                    canvas=canvas, text=text_line.upper(), font_path=font_path, font_size=font_size,
                    position=(0, int(start_y * scale_coord)), align_x=align_x, align_y="absolute",
                    padding=padding, shape=shape, radius=radius, skew_px=skew_px,
                    bg_color=bg_color, bg_alpha=bg_alpha, border_color=border_color,
                    border_alpha=border_alpha, border_width=border_width, text_color=text_color,
                    margin_bounds=margin_bounds
                )
                badge_h_hd = int(badge_info["height"] * 2) if is_preview else int(badge_info["height"])
                start_y += int(badge_h_hd + gap_y)
                current_side = "right" if current_side == "left" else "left"

        # 🎯 РЕЖИМ 3: ФОКУС-ЦЕНТР (Плашки ложатся строго по центру, выстраивая мощный инфо-столб)
        elif layout_type == "center_pillar":
            for text_line in lines:
                badge_info = draw_universal_badge(
                    canvas=canvas, text=text_line.upper(), font_path=font_path, font_size=font_size,
                    position=(0, int(start_y * scale_coord)), align_x="center", align_y="absolute",
                    padding=padding, shape=shape, radius=radius, skew_px=skew_px,
                    bg_color=bg_color, bg_alpha=bg_alpha, border_color=border_color,
                    border_alpha=border_alpha, border_width=border_width, text_color=text_color,
                    margin_bounds=margin_bounds
                )
                badge_h_hd = int(badge_info["height"] * 2) if is_preview else int(badge_info["height"])
                start_y += int(badge_h_hd + gap_y)

        # ==============================================================================
        # 🎯 РЕЖИМ 4: УЛЬТРА-МАТРИЦА КВАНТОВОГО ВЫРАВНИВАНИЯ ЗНАЧКOВ И ТЕКСТА 3Х3
        # ==============================================================================
        elif layout_type == "bottom_icon_grid":
            b2b_icon_names = ["star", "truck", "gift", "shield", "bolt", "cube", "award", "heart", "leaf", "fire", "tag", "percent", "shirt", "crown", "thumbs_up"]
            is_icon_mode = any(line.lower().strip() in b2b_icon_names for line in lines)

            badge_size = 82
            gap_space = 20
            
            if is_icon_mode:
                obj_w, obj_h = 82, 82
                fa_font_path = "assets/fonts/font_awesome.otf"
                if not os.path.exists(fa_font_path): 
                    fa_font_path = font_path
            else:
                obj_h = int(font_size * 1.5)
                obj_w = int(W * 0.45) 
                fa_font_path = font_path

            # Разбираем массив активных ячеек из строки фронтенда
            active_dots = [int(d) for d in str(side_position).split(",") if d.strip().isdigit()]
            if not active_dots:
                active_dots = [8]

            # Попиксельная карта координат центров 9 зон на макете СТРОГО в Full HD 900x1200!
            zone_coords = {
                1: (margin_bounds + obj_w//2, int(H * 0.18)),
                2: (W // 2, int(H * 0.18)),
                3: (W - margin_bounds - obj_w//2, int(H * 0.18)),
                
                4: (margin_bounds + obj_w//2, int(H * 0.50)),
                5: (W // 2, int(H * 0.50)),
                6: (W - margin_bounds - obj_w//2, int(H * 0.50)),
                
                7: (margin_bounds + obj_w//2, int(H * 0.76)),
                8: (W // 2, int(H * 0.76)),
                9: (W - margin_bounds - obj_w//2, int(H * 0.76))
            }

            is_row_1 = all(d in active_dots for d in [1, 2, 3])
            is_row_2 = all(d in active_dots for d in [4, 5, 6])
            is_row_3 = all(d in active_dots for d in [7, 8, 9])
            
            is_col_1 = all(d in active_dots for d in [1, 4, 7])
            is_col_2 = all(d in active_dots for d in [2, 5, 8])
            is_col_3 = all(d in active_dots for d in [3, 6, 9])

            # 🗺️ СЦЕНАРИЙ А: ГОРИЗОНТАЛЬНЫЙ СТРЕТЧ (Выделена строка)
            if (is_row_1 or is_row_2 or is_row_3) and not (is_col_1 or is_col_2 or is_col_3):
                if is_row_1: grid_y = zone_coords[1][1]
                elif is_row_2: grid_y = zone_coords[4][1]
                else: grid_y = zone_coords[7][1]
                
                usable_width = W - (margin_bounds * 2)
                step_x = (usable_width - obj_w) / (len(lines) - 1) if len(lines) > 1 else 0
                start_x = margin_bounds
                
                for text_line in lines:
                    draw_universal_badge(
                        canvas=canvas, text=text_line.strip().lower() if is_icon_mode else text_line.strip().upper(),
                        font_path=fa_font_path, font_size=font_size,
                        position=(int(start_x * scale_coord), int((grid_y - obj_h//2) * scale_coord)), align_x="absolute", align_y="absolute",
                        padding=padding, shape=shape, radius=radius, skew_px=skew_px if not is_icon_mode else 0,
                        bg_color=bg_color, bg_alpha=bg_alpha, border_color=border_color,
                        border_alpha=border_alpha, border_width=border_width, text_color=text_color, margin_bounds=0
                    )
                    start_x += step_x

            # 🗺️ СЦЕНАРИЙ Б: ВЕРТИКАЛЬНЫЙ СТРЕТЧ (Выделен столбец — лента по высоте)
            elif (is_col_1 or is_col_2 or is_col_3) and not (is_row_1 or is_row_2 or is_row_3):
                if is_col_1: align_x = "left_bound"
                elif is_col_3: align_x = "right_bound"
                else: align_x = "center"
                
                start_y = int(H * 0.20)
                usable_height = H - start_y - int(H * 0.15)
                step_y = (usable_height - obj_h) / (len(lines) - 1) if len(lines) > 1 else 0
                
                for idx, text_line in enumerate(lines):
                    badge_y = start_y + (idx * step_y)
                    draw_universal_badge(
                        canvas=canvas, text=text_line.strip().lower() if is_icon_mode else text_line.strip().upper(),
                        font_path=fa_font_path, font_size=font_size,
                        position=(0, int(badge_y * scale_coord)), align_x=align_x, align_y="absolute",
                        padding=padding, shape=shape, radius=radius, skew_px=skew_px if not is_icon_mode else 0,
                        bg_color=bg_color, bg_alpha=bg_alpha, border_color=border_color,
                        border_alpha=border_alpha, border_width=border_width, text_color=text_color, margin_bounds=margin_bounds
                    )

            # 🗺️ СЦЕНАРИЙ В: ИНТЕЛЛЕКТУАЛЬНЫЙ КЛУСТЕРНЫЙ МЕШ (Любая хаотичная комбинация)
            else:
                sum_x = sum(zone_coords[d][0] for d in active_dots)
                sum_y = sum(zone_coords[d][1] for d in active_dots)
                avg_center_x = sum_x // len(active_dots)
                avg_center_y = sum_y // len(active_dots)
                
                icons_in_row = 3 if (is_icon_mode and len(lines) > 4) else (1 if not is_icon_mode else len(lines))
                if icons_in_row == 0: 
                    icons_in_row = 1
                
                rows_count = math.ceil(len(lines) / icons_in_row)
                block_w = (icons_in_row * obj_w) + ((icons_in_row - 1) * gap_space)
                block_h = (rows_count * obj_h) + ((rows_count - 1) * gap_space)
                
                start_block_x = avg_center_x - (block_w // 2)
                start_block_y = avg_center_y - (block_h // 2)
                
                start_block_x = max(margin_bounds, min(W - block_w - margin_bounds, start_block_x))
                start_block_y = max(int(H * 0.05), min(H - block_h - margin_bounds, start_block_y))
                
                for idx, text_line in enumerate(lines):
                    row_idx = idx // icons_in_row
                    col_idx = idx % icons_in_row
                    
                    badge_x = start_block_x + (col_idx * (obj_w + gap_space))
                    badge_y = start_block_y + (row_idx * (obj_h + gap_space))
                    
                    final_align_x = "absolute"
                    if not is_icon_mode:
                        if avg_center_x < int(W * 0.4): 
                            final_align_x = "left_bound"
                        elif avg_center_x > int(W * 0.6): 
                            final_align_x = "right_bound"
                        else: 
                            final_align_x = "center"
                    
                    draw_universal_badge(
                        canvas=canvas, 
                        text=text_line.strip().lower() if is_icon_mode else text_line.strip().upper(),
                        font_path=fa_font_path, 
                        font_size=font_size,
                        position=(int(badge_x * scale_coord), int(badge_y * scale_coord)), 
                        align_x=final_align_x, 
                        align_y="absolute",
                        padding=padding, 
                        shape=shape, 
                        radius=radius, 
                        skew_px=skew_px if not is_icon_mode else 0,
                        bg_color=bg_color, 
                        bg_alpha=bg_alpha, 
                        border_color=border_color,
                        border_alpha=border_alpha, 
                        border_width=border_width, 
                        text_color=text_color, 
                        margin_bounds=margin_bounds
                    )

    @staticmethod
    def execute_stack_layout_old(canvas, session_path, badge_stack, layout_type, side_position, margin_bounds=54, is_icon_mode=False):
        """
        🎯 ДИРЕКТИВА ШЕФА: Универсальный Диспетчер Компоновщика.
        Переваривает стек хэш-кубиков, вычисляет Full HD координаты меша 3х3 без пересечений,
        и пастит нужные ассеты (_preview или _hd) на холст Студии.
        """
        CURRENT_W, CURRENT_H = canvas.size
        is_preview_mode = (CURRENT_W == 450)
        
        W_hd, H_hd = 900, 1200
        suffix = "_preview.png" if is_preview_mode else "_hd.png"
        scale_factor = 0.5 if is_preview_mode else 1.0
        
        if not badge_stack:
            return

        # --------------------------------------------------------------------------
        # 🗺️ СЦЕНАРИЙ №1: КЛАССИЧЕСКИЙ ВЕРТИКАЛЬНЫЙ СТEК (Сверху вниз)
        # --------------------------------------------------------------------------
        if layout_type == "vertical_stack":
            start_y_hd = int(H_hd * 0.18)
            gap_y_hd = 30
            align_x = "left" if side_position == "left" else "right"
            
            for badge in badge_stack:
                b_hash = badge["id"]
                b_w_hd = badge["width"]
                b_h_hd = badge["height"]
                
                x_hd = margin_bounds if align_x == "left" else (W_hd - b_w_hd - margin_bounds)
                
                final_x = int(x_hd * scale_factor)
                final_y = int(start_y_hd * scale_factor)
                
                badge_file_path = os.path.join(session_path, f"badge_{b_hash}{suffix}")
                if os.path.exists(badge_file_path):
                    with Image.open(badge_file_path).convert("RGBA") as b_img:
                        canvas.paste(b_img, (final_x, final_y), b_img)
                start_y_hd += (b_h_hd + gap_y_hd)

        # --------------------------------------------------------------------------
        # 🗺️ СЦЕНАРИЙ №2: УЛЬТРА-МАТРИЦА КВАНТОВОГО МЕША 3Х3 (Горизонт, Вертикаль, Кластер)
        # --------------------------------------------------------------------------
        elif layout_type == "bottom_icon_grid":
            active_dots = [int(d) for d in str(side_position).split(",") if d.strip().isdigit()]
            if not active_dots: active_dots = [8]

            gap_space_hd = 20
            
            # Парсим зажженные линии 3х3
            is_row_1 = all(d in active_dots for d in [1, 2, 3])
            is_row_2 = all(d in active_dots for d in [4, 5, 6])
            is_row_3 = all(d in active_dots for d in [7, 8, 9])
            is_col_1 = all(d in active_dots for d in [1, 4, 7])
            is_col_2 = all(d in active_dots for d in [2, 5, 8])
            is_col_3 = all(d in active_dots for d in [3, 6, 9])

            # Мапим центры 9 зон строго на Full HD холсте 900x1200
            # Чтобы узнать средний obj_w_hd, берем среднюю ширину плашек из нашего стека!
            avg_obj_w_hd = sum(b["width"] for b in badge_stack) // len(badge_stack)
            avg_obj_h_hd = sum(b["height"] for b in badge_stack) // len(badge_stack)

            zone_coords_hd = {
                1: (margin_bounds + avg_obj_w_hd//2, int(H_hd * 0.18)),
                2: (W_hd // 2, int(H_hd * 0.18)),
                3: (W_hd - margin_bounds - avg_obj_w_hd//2, int(H_hd * 0.18)),
                4: (margin_bounds + avg_obj_w_hd//2, int(H_hd * 0.50)),
                5: (W_hd // 2, int(H_hd * 0.50)),
                6: (W_hd - margin_bounds - avg_obj_w_hd//2, int(H_hd * 0.50)),
                7: (margin_bounds + avg_obj_w_hd//2, int(H_hd * 0.76)),
                8: (W_hd // 2, int(H_hd * 0.76)),
                9: (W_hd - margin_bounds - avg_obj_w_hd//2, int(H_hd * 0.76))
            }

            # А. ГОРИЗОНТАЛЬНЫЙ СТРЕТЧ
            if (is_row_1 or is_row_2 or is_row_3) and not (is_col_1 or is_col_2 or is_col_3):
                grid_y_hd = zone_coords_hd[1][1] if is_row_1 else (zone_coords_hd[4][1] if is_row_2 else zone_coords_hd[7][1])
                usable_width_hd = W_hd - (margin_bounds * 2)
                
                # Считаем точную суммарную ширину всех плашек из стека, чтобы шаг был без пересечений!
                total_badges_w_hd = sum(b["width"] for b in badge_stack)
                remaining_space_hd = usable_width_hd - total_badges_w_hd
                step_gap_hd = remaining_space_hd / (len(badge_stack) - 1) if len(badge_stack) > 1 else 0
                
                current_x_hd = margin_bounds
                for badge in badge_stack:
                    final_x = int(current_x_hd * scale_factor)
                    final_y = int((grid_y_hd - badge["height"]//2) * scale_factor)
                    
                    badge_file_path = os.path.join(session_path, f"badge_{badge['id']}{suffix}")
                    if os.path.exists(badge_file_path):
                        with Image.open(badge_file_path).convert("RGBA") as b_img:
                            canvas.paste(b_img, (final_x, final_y), b_img)
                    current_x_hd += badge["width"] + step_gap_hd

            # Б. ВЕРТИКАЛЬНЫЙ СТРЕТЧ
            elif (is_col_1 or is_col_2 or is_col_3) and not (is_row_1 or is_row_2 or is_row_3):
                align_x = "left" if is_col_1 else ("right" if is_col_3 else "center")
                start_y_hd = int(H_hd * 0.20)
                usable_height_hd = H_hd - start_y_hd - int(H_hd * 0.15)
                
                total_badges_h_hd = sum(b["height"] for b in badge_stack)
                remaining_height_hd = usable_height_hd - total_badges_h_hd
                step_gap_hd = remaining_height_hd / (len(badge_stack) - 1) if len(badge_stack) > 1 else 0
                
                current_y_hd = start_y_hd
                for badge in badge_stack:
                    if align_x == "left": x_hd = margin_bounds
                    elif align_x == "right": x_hd = W_hd - badge["width"] - margin_bounds
                    else: x_hd = (W_hd - badge["width"]) // 2
                    
                    final_x = int(x_hd * scale_factor)
                    final_y = int(current_y_hd * scale_factor)
                    
                    badge_file_path = os.path.join(session_path, f"badge_{badge['id']}{suffix}")
                    if os.path.exists(badge_file_path):
                        with Image.open(badge_file_path).convert("RGBA") as b_img:
                            canvas.paste(b_img, (final_x, final_y), b_img)
                    current_y_hd += badge["height"] + step_gap_hd

            # В. ИНТЕЛЛЕКТУАЛЬНЫЙ КЛУСТЕРНЫЙ МЕШ (Сетка по хэшам)
            else:
                sum_x = sum(zone_coords_hd[d][0] for d in active_dots)
                sum_y = sum(zone_coords_hd[d][1] for d in active_dots)
                avg_center_x = sum_x // len(active_dots)
                avg_center_y = sum_y // len(active_dots)
                
                icons_in_row = 3 if (is_icon_mode and len(badge_stack) > 4) else (1 if not is_icon_mode else len(badge_stack))
                if icons_in_row == 0: icons_in_row = 1
                
                rows_count = math.ceil(len(badge_stack) / icons_in_row)
                block_w = (icons_in_row * avg_obj_w_hd) + ((icons_in_row - 1) * gap_space_hd)
                block_h = (rows_count * avg_obj_h_hd) + ((rows_count - 1) * gap_space_hd)
                
                start_block_x = avg_center_x - (block_w // 2)
                start_block_y = avg_center_y - (block_h // 2)
                
                start_block_x = max(margin_bounds, min(W_hd - block_w - margin_bounds, start_block_x))
                start_block_y = max(int(H_hd * 0.05), min(H_hd - block_h - margin_bounds, start_block_y))
                
                for idx, badge in enumerate(badge_stack):
                    row_idx = idx // icons_in_row
                    col_idx = idx % icons_in_row
                    
                    badge_x_hd = start_block_x + (col_idx * (avg_obj_w_hd + gap_space_hd))
                    badge_y_hd = start_block_y + (row_idx * (avg_obj_h_hd + gap_space_hd))
                    
                    final_x = int(badge_x_hd * scale_factor)
                    final_y = int(badge_y_hd * scale_factor)
                    
                    badge_file_path = os.path.join(session_path, f"badge_{badge['id']}{suffix}")
                    if os.path.exists(badge_file_path):
                        with Image.open(badge_file_path).convert("RGBA") as b_img:
                            canvas.paste(b_img, (final_x, final_y), b_img)

import os
import math
import random
from PIL import Image

class SkullaLayoutRouter:
    # Глобальная карта занятых окон (зон) на Full HD холсте 900x1200 для предотвращения пересечений наборов
    # Формат элементов: {"x1":, "y1":, "x2":, "y2":, "priority":}
    occupied_bounds = []

    @staticmethod
    def reset_layout_manager():
        """Очищает карту занятых окон перед каждым новым рендером карточки"""
        SkullaLayoutRouter.occupied_bounds = []

    @staticmethod
    def register_occupied_zone(x1, y1, x2, y2, priority=0):
        """Резервирует зону на Full HD макете, предотвращая наложение следующих наборов графики"""
        SkullaLayoutRouter.occupied_bounds.append({
            "x1": int(x1), "y1": int(y1), 
            "x2": int(x2), "y2": int(y2), 
            "priority": priority
        })

    @staticmethod
    def find_free_y_slot(start_y, height, needed_width, W_hd=900, margin=54):
        """Интеллектуальный поиск свободного вертикального окна, если зоны перекрываются"""
        current_y = start_y
        loop_guard = 0
        
        while loop_guard < 50:
            overlap = False
            for zone in SkullaLayoutRouter.occupied_bounds:
                # Проверяем пересечение по вертикали и горизонтали
                if not (current_y + height <= zone["y1"] or current_y >= zone["y2"]):
                    # Если пересекается с зарезервированной зоной
                    overlap = True
                    current_y = zone["y2"] + 20  # Сдвигаем на 20px ниже занятого окна
                    break
            if not overlap:
                break
            loop_guard += 1
            
        return current_y

    @staticmethod
    def execute_stack_layout(canvas, session_path, badge_stack, layout_type, side_position, margin_bounds=54, is_icon_mode=False, priority_level=2, base_y_hd=192, gravity="top"):
        """
        🎯 АБСОЛЮТНАЯ ДИРЕКТИВА ШЕФА: Двухпроходной линейный роутер.
        Просто берёт готовую координату base_y_hd и расставляет элементы по сценариям 1х3.
        Возвращает реальную высоту всего сгенерированного блока плашек.
        """
        if not badge_stack:
            return 0

        CURRENT_W, CURRENT_H = canvas.size
        is_preview_mode = (CURRENT_W == 450)
        
        W_hd, H_hd = 900, 1200
        suffix = "_preview.png" if is_preview_mode else "_hd.png"
        scale_factor = 0.5 if is_preview_mode else 1.0

        # Парсим активные кнопки из строки фронтенда
        active_dots = sorted(list(set([int(d) for d in str(side_position).split(",") if d.strip().isdigit()])))
        if not active_dots:
            active_dots = [2]

        gap_x_hd = 15
        gap_y_hd = 20

        # Ссылки на координаты отрисовки
        final_coords_hd = []
        avg_w_hd = sum(b["width"] for b in badge_stack) // len(badge_stack)
        avg_h_hd = sum(b["height"] for b in badge_stack) // len(badge_stack)

        # ==============================================================================
        # 🧩 ВЫЧИСЛЕНИЕ ПОПИКСЕЛЬНЫХ КОOРДИНАТ НА ОСНОВЕ ПЕРЕДАННОГО base_y_hd
        # ==============================================================================

        # 🗺️ СЦЕНАРИЙ А: ОДИН СТОЛБЕЦ (1, 2 или 3)
        if len(active_dots) == 1:
            target = active_dots[0]
            current_y = base_y_hd
            
            for badge in badge_stack:
                if target == 1:   x_hd = margin_bounds
                elif target == 3: x_hd = W_hd - badge["width"] - margin_bounds
                else:             x_hd = (W_hd - badge["width"]) // 2
                    
                final_coords_hd.append((x_hd, current_y))
                current_y += badge["height"] + gap_y_hd
            
            total_block_height = current_y - base_y_hd - gap_y_hd

        # 🗺️ СЦЕНАРИЙ Б: ДВА СТОЛБЦА СЛЕВА И СПРАВА (1, 3)
        elif active_dots == [1, 3]:
            left_y = base_y_hd
            right_y = base_y_hd
            
            for idx, badge in enumerate(badge_stack):
                if idx % 2 == 0:
                    x_hd = margin_bounds
                    final_coords_hd.append((x_hd, left_y))
                    left_y += badge["height"] + gap_y_hd
                else:
                    x_hd = W_hd - badge["width"] - margin_bounds
                    final_coords_hd.append((x_hd, right_y))
                    right_y += badge["height"] + gap_y_hd
            
            total_block_height = max(left_y, right_y) - base_y_hd - gap_y_hd

        # 🗺️ СЦЕНАРИЙ В: МНОГОСТРОЧНЫЙ GRID WRAP (1,2,3 / 1,2 / 2,3)
        else:
            usable_w_hd = W_hd - (margin_bounds * 2)
            rows = []
            current_row = []
            current_row_w = 0
            
            for badge in badge_stack:
                badge_total_w = badge["width"] + (gap_x_hd if current_row else 0)
                if current_row_w + badge_total_w > usable_w_hd:
                    rows.append((current_row, current_row_w))
                    current_row = [badge]
                    current_row_w = badge["width"]
                else:
                    current_row.append(badge)
                    current_row_w += badge_total_w
            if current_row:
                rows.append((current_row, current_row_w))

            current_y_hd = base_y_hd
            for row_badges, row_w in rows:
                if active_dots == [1, 2, 3]: start_x_hd = margin_bounds + (usable_w_hd - row_w) // 2
                elif active_dots == [1, 2]: start_x_hd = margin_bounds
                else:                         start_x_hd = W_hd - margin_bounds - row_w
                
                max_row_h = 0
                for badge in row_badges:
                    final_coords_hd.append((start_x_hd, current_y_hd))
                    start_x_hd += badge["width"] + gap_x_hd
                    if badge["height"] > max_row_h:
                        max_row_h = badge["height"]
                        
                current_y_hd += max_row_h + gap_y_hd
            
            total_block_height = current_y_hd - base_y_hd - gap_y_hd

        # ==============================================================================
        # 🎨 НАКАТ АССЕТОВ С КВАНТОВАНИЕМ ПОД ПРЕВЬЮ
        # ==============================================================================
        for idx, badge in enumerate(badge_stack):
            b_hash = badge["id"]
            x_hd, y_hd = final_coords_hd[idx]
            
            x_hd = max(5, min(W_hd - badge["width"] - 5, x_hd))
            y_hd = max(5, min(H_hd - badge["height"] - 5, y_hd))
            
            final_x = int(x_hd * scale_factor)
            final_y = int(y_hd * scale_factor)
            
            badge_file_path = os.path.join(session_path, f"badge_{b_hash}{suffix}")
            if os.path.exists(badge_file_path):
                with Image.open(badge_file_path).convert("RGBA") as b_img:
                    canvas.paste(b_img, (final_x, final_y), b_img)

        # Возвращаем РЕАЛЬНУЮ физическую высоту сгенерированного блока
        return total_block_height


    @staticmethod
    def find_free_y_slot_bottom(target_y, height, needed_width, W_hd=900, margin=54):
        """Интеллектуальный поиск свободного окна снизу вверх для гравитации bottom"""
        current_y = target_y
        loop_guard = 0
        
        while loop_guard < 50:
            overlap = False
            for zone in SkullaLayoutRouter.occupied_bounds:
                # Если блок пересекает уже занятую зону
                if not (current_y + height <= zone["y1"] or current_y >= zone["y2"]):
                    overlap = True
                    # Силой выталкиваем элемент ВВЕРХ над занятым окном
                    current_y = zone["y1"] - height - 20
                    break
            if not overlap:
                break
            loop_guard += 1
            
        return current_y
