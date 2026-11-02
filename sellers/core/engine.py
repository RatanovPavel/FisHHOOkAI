import os
import math
import colorsys
from PIL import Image
from core.layout_router import SkullaLayoutRouter

class SkullaRenderEngine:
    @staticmethod
    def execute_two_pass_render(
        canvas, s_path, controls_config, params, theme_colors, 
        font_path, f_size, title_f_size, icon_shape, b_shape, margin_bounds=95
    ):
        """
        🪐 ЕДИНЫЙ ГРАФИЧЕСКИЙ ДВИЖОК СТУДИИ SKULLA CORE.
        Полностью инкапсулирует двухпроходную линейную гравитацию Шефа
        с автоматическим кэшированием CAS, иерархией слоев и мастер-калибровкой.
        """
        from core.vision import save_decoupl_badge_assets, save_decoupl_frame_assets
        
        W_hd, H_hd = 900, 1200
        is_preview = (canvas.size[0] == 450)
        scale_factor = 0.5 if is_preview else 1.0
        suffix = "_preview.png" if is_preview else "_hd.png"

        # Извлекаем сырые строки параметров фронтенда
        main_title = params.get("main_title", "").upper()
        badges_list_raw = params.get("badges_list", "")
        bottom_icons_raw = params.get("bottom_icons", "")
        p_tag = params.get("promo_tag", "").upper()

        # Матрицы
        anchor_matrix_text = params.get("text_layout_matrix", "1,2,3")
        anchor_matrix_icons = params.get("icon_anchor_matrix", "2")
        title_matrix = params.get("title_layout_matrix", "2")
        promo_matrix = params.get("promo_layout_matrix", "3")

        # Цвета темы из словаря
        style_bg_color = theme_colors["bg"]
        style_bg_alpha = theme_colors.get("bg_alpha", 215)
        style_border_color = theme_colors["border"]
        style_text_color = theme_colors["text"]
        style_border_width = theme_colors.get("border_width", 2)
        # 🎯 ШЕФ-ИНЖЕКТ: Вытягиваем раздельный шрифт и цвет заголовка из params и theme_colors
        title_font_resolved = params.get("title_font_resolved_path", font_path)
        title_text_color_rgb = theme_colors.get("title_text", style_text_color)

        # Инициализируем пустые стеки для защиты от UnboundLocalError
        icon_badge_stack = []
        text_badge_stack = []
        title_badge_stack = []
        
        master_icon_w, master_icon_h = 0, 0
        master_text_h = 0
        user_scale_pct = float(params.get("product_scale", 100)) / 100.0

        # ==============================================================================
        # 🛠️ ПРОХОД №1: СВЕРХУ ВНИЗ (TOP ГРАВИТАЦИЯ)
        # ==============================================================================
        # Начинаем с эталонных 6% высоты сверху холста
        current_top_y_hd = int(H_hd * 0.06)

        for ctrl in controls_config:
            ctrl_id = ctrl["id"]

            # 👑 1. Главный заголовок (Проход TOP)
            if ctrl_id == "main_title":
                title_grav = next((c.get("default", "top") for c in controls_config if c["id"] == "title_gravity"), "top")
                if title_grav != "top" or not main_title.strip(): 
                    continue
                
                title_badge_stack = []
                # 🎯 АБСОЛЮТНЫЙ ГЕОМЕТРИЧЕСКИЙ ФИКС ШЕФА ДЛЯ СТРОКИ 70:
                # Передаем s_path и main_title первыми двумя позиционными аргументами без ключевого слова path!
                hd_dim = save_decoupl_badge_assets(
                    s_path, main_title, font_path=title_font_resolved, font_size=title_f_size,
                    shape="rect", padding=0, radius=0, skew_px=0, bg_color=(0,0,0), bg_alpha=0,
                    border_color=(0,0,0), border_alpha=0, border_width=0, 
                    text_color=title_text_color_rgb, text_alpha=255
                )

                title_badge_stack.append(hd_dim)
                
                block_h = SkullaLayoutRouter.execute_stack_layout(
                    canvas=canvas, session_path=s_path, badge_stack=title_badge_stack,
                    layout_type="bottom_icon_grid", side_position=title_matrix, margin_bounds=margin_bounds,
                    is_icon_mode=False, priority_level=1, base_y_hd=current_top_y_hd, gravity="top"
                )
                current_top_y_hd += block_h + 90

            # 📝 2. АТОМАРНАЯ ПОДМЕНА ШЕФА: Динамический Max-Сплит Характеристик (Проход TOP)
            # 📝 2. АТОМАРНАЯ ПОДМЕНА ШЕФА: Динамический Max-Сплит Характеристик (Проход TOP)
            elif ctrl_id == "features_flow_gravity":
                flow_grav = ctrl.get("default", "top")
                if flow_grav != "top": 
                    continue
                
                # Считываем 3 текстовые характеристики
                f_texts = [
                    params.get("feature_1", ""), 
                    params.get("feature_2", ""), 
                    params.get("feature_3", "")
                ]
                # Считываем 3 имени файлов картинок, очищенных роутером при загрузке
                f_photos = [
                    "original.png", 
                    params.get("extra_photo_1", ""), 
                    params.get("extra_photo_2", "")
                ]
                
                frame_shape = params.get("frame_shape", "circle")
                show_text_border = params.get("show_text_border", "false") == "true"
                show_photo_border = params.get("show_photo_border", "true") == "true"
                
                # 🎯 СУПЕР-ФИКС ШЕФА: Собираем массив трех независимых тумблеров направлений!
                row_directions = [
                    params.get("row_1_direction", "text_first"),
                    params.get("row_2_direction", "text_first"),
                    params.get("row_3_direction", "text_first")
                ]
                
                for i in range(3):
                    txt = f_texts[i]
                    photo_name = f_photos[i]
                    if not txt.strip(): 
                        continue
                    
                    # Извлекаем индивидуальное направление для текущего этажа
                    current_row_order = row_directions[i]
                    
                    # 🔬 Настраиваем альфа-каналы прозрачности рамочек по правилам Шефа
                    txt_alpha_bg = style_bg_alpha if show_text_border else 0
                    txt_alpha_border = 255 if show_text_border else 0
                    photo_alpha_border = 255 if show_photo_border else 0
                    
                    # Предварительный замер высоты текста (force_height=None)
                    raw_txt_dim = save_decoupl_badge_assets(
                        session_path=s_path, text=txt, font_path=font_path, font_size=f_size, shape=b_shape, 
                        padding=30, radius=16, skew_px=22, bg_color=style_bg_color, bg_alpha=txt_alpha_bg, 
                        border_color=style_border_color, border_alpha=txt_alpha_border, border_width=style_border_width, 
                        text_color=style_text_color, text_alpha=255
                    )
                    
                    # Предварительный замер высоты фото-фрейма (force_height=None)
                    raw_frame_dim = save_decoupl_frame_assets(
                        session_path=s_path, img_filename=photo_name, frame_shape=frame_shape,
                        border_color=style_border_color, border_alpha=photo_alpha_border, border_width=style_border_width,
                        scale_pct=user_scale_pct
                    )
                    
                    # 🎯 ВЫЧИСЛЯЕМ МАКСИМАЛЬНУЮ ВЫСОТУ СТРОКИ ДЛЯ УНИФИКАЦИИ
                    master_row_h = max(int(raw_txt_dim["height"] * 1.1), raw_frame_dim["height"])
                    
                    # 🔬 Чистовой рендеринг ассетов с динамическим зажатием в Мастер-Высоту строки
                    final_txt_badge = save_decoupl_badge_assets(
                        session_path=s_path, text=txt, font_path=font_path, font_size=f_size, shape=b_shape, 
                        padding=30, radius=16, skew_px=22, bg_color=style_bg_color, bg_alpha=txt_alpha_bg, 
                        border_color=style_border_color, border_alpha=txt_alpha_border, border_width=style_border_width, 
                        text_color=style_text_color, text_alpha=255, force_height=master_row_h
                    )
                    
                    final_frame_badge = save_decoupl_frame_assets(
                        session_path=s_path, img_filename=photo_name, frame_shape=frame_shape, 
                        border_color=style_border_color, border_alpha=photo_alpha_border, border_width=style_border_width, 
                        scale_pct=user_scale_pct if 'user_scale_pct' in locals() else 1.0, force_height=master_row_h
                    )
                    
                    # 🎯 АБСОЛЮТНЫЙ РАСЧЕТ X ДЛЯ СВОБОДНОГО ЗЕРКАЛИРОВАНИЯ СТРОК ОДНОВРЕМЕННО
                    # 🎯 ТОЧЕЧНЫЙ ФИКС ШЕФА: Передаем кнопки матрицы "1" и "3" вместо сырых пикселей X!
                    if current_row_order == "text_first":
                        pos_text = "1"  # Текст улетает ВЛЕВО (Кнопка 1)
                        pos_photo = "3" # Фото улетает ВПРАВО (Кнопка 3)
                    else:
                        pos_photo = "1" # Фото улетает ВЛЕВО (Кнопка 1)
                        pos_text = "3"  # Текст улетает ВПРАВО (Кнопка 3)
                    
                    # Отрисовка текстовой плашки строки
                    # ==============================================================================
                    # 🪐 АБСОЛЮТНЫЙ БЕСКОНСТАНТНЫЙ ЧЕРТЁЖНЫЙ РАСЧЁТ ШЕФА V24 (СТРОГО ПО КЛЮЧАМ СЛОВАРЯ)
                    # Мы полностью исцелили расчет! Переменные final_badge являются словарями dict.
                    # Вытаскиваем живую ширину напрямую по ключам ["width"] без всяких .size!
                    # Текст встанет пуля в пулю идеально по центру свободного места при любых масштабах!
                    # ==============================================================================
                    resolved_txt_margin = margin_bounds
                    try:
                        # Снайперски забираем живые пиксели ширины из словарей Питона!
                        photo_w = int(final_frame_badge.get("width", 360)) if final_frame_badge else 360
                        text_w = int(final_txt_badge.get("width", 250)) if final_txt_badge else 250
                        
                        if current_row_order == "photo_first":
                            # 👉 Фото СЛЕВА (pos_photo == "1"), Текст СПРАВА (pos_text == "3")
                            # Правый край фото = левое поле карточки (54) + реальная ширина картинки фото фрейма
                            photo_right_edge = margin_bounds + photo_w
                            canvas_right_edge = 900 - margin_bounds # 846px
                            
                            # Находим точный геометрический中心 свободного коридора справа между краем фото и краем поля
                            free_space_center = photo_right_edge + ((canvas_right_edge - photo_right_edge) // 2)
                            
                            # Точечно компенсируем вычитание text_w на строке 477 твоего движка layout_router.py
                            resolved_txt_margin = 900 - free_space_center - (text_w // 2)
                        else:
                            # 👉 Текст СЛЕВА (pos_text == "1"), Фото СПРАВА (pos_photo == "3")
                            # Левый край фото = ширина холста (900) - реальная ширина картинки фото - правое поле карточки (54)
                            photo_left_edge = 900 - photo_w - margin_bounds
                            canvas_left_edge = margin_bounds # 54px
                            
                            # Находим точный геометрический центр свободного коридора слева между полем и краем фото
                            free_space_center = canvas_left_edge + ((photo_left_edge - canvas_left_edge) // 2)
                            
                            # Для левой стороны (строка 476) маргин равен точке старта левого края плашки
                            resolved_txt_margin = free_space_center - (text_w // 2)
                            
                        print(f"📐 [SKULLA GEOMETRY SUCCESS V24]: photo_w={photo_w} | text_w={text_w} | margin={resolved_txt_margin}")
                    except Exception as e:
                        print(f"❌ [SKULLA GEOMETRY CRASH V24]: {e}")
                        resolved_txt_margin = margin_bounds

                    # Отрисовка текстовой плашки строки со снайперским динамическим отступом полей
                    SkullaLayoutRouter.execute_stack_layout(
                        canvas=canvas,
                        session_path=s_path,
                        badge_stack=[final_txt_badge],
                        layout_type="bottom_icon_grid",
                        side_position=pos_text,
                        margin_bounds=int(resolved_txt_margin), # Инжектировали идеальный бесконстантный маргин!
                        is_icon_mode=False,
                        priority_level=2,
                        base_y_hd=current_top_y_hd,
                        gravity="top"
                    )




                    
                    # Отрисовка фото-фрейма строки
                    SkullaLayoutRouter.execute_stack_layout(
                        canvas=canvas, session_path=s_path, badge_stack=[final_frame_badge],
                        layout_type="bottom_icon_grid", side_position=pos_photo, margin_bounds=margin_bounds,
                        is_icon_mode=False, priority_level=4, base_y_hd=current_top_y_hd, gravity="top"
                    )

                    
                    # Сдвигаем линию верхнего потока вниз на реальную высоту строки + зазор!
                    current_top_y_hd += master_row_h + 35


            # 📝 3. Список плашек УТП (Проход TOP)
            elif ctrl_id == "badges_list":
                text_grav = next((c.get("default", "top") for c in controls_config if c["id"] == "text_gravity"), "top")
                if text_grav != "top" or not badges_list_raw.strip(): 
                    continue
                
                # 🎯 СУПЕР-ПЕРЕХВАТ ШЕФА: Сдвигаем стартовую ось под нижний срез фото! [INDEX]
                if "current_top_y_hd_override" in params:
                    current_top_y_hd = int(params["current_top_y_hd_override"])

                text_badge_stack = []
                
                # 🎯 АБСОЛЮТНЫЙ ИИ-ВЗЛОМ КОНВЕЙЕРА: Если прилетел готовый монолитный пресет от Слайда 3 — 
                # полностью блокируем построчные сплиты и берем готовый кубик Шефа! [INDEX]
                if "badges_list_preset" in params:
                    text_badge_stack = params["badges_list_preset"]
                else:
                    # Старый проверенный построчный фолбек для классического Слайда 2
                    lines_text = [line.strip() for line in badges_list_raw.split("\n") if line.strip()]
                    for idx, txt in enumerate(lines_text):
                        if idx == 0:
                            hd_dim = save_decoupl_badge_assets(s_path, txt, font_path, f_size, b_shape, 30, 16, 22, style_bg_color, style_bg_alpha, style_border_color, 255, style_border_width, style_text_color, 255)
                            master_text_h = int(hd_dim["height"] * 1.1)
                            hd_dim = save_decoupl_badge_assets(s_path, txt, font_path, f_size, b_shape, 30, 16, 22, style_bg_color, style_bg_alpha, style_border_color, 255, style_border_width, style_text_color, 255, force_height=master_text_h)
                        else:
                            hd_dim = save_decoupl_badge_assets(s_path, txt, font_path, f_size, b_shape, 30, 16, 22, style_bg_color, style_bg_alpha, style_border_color, 255, style_border_width, style_text_color, 255, force_height=master_text_h)
                        text_badge_stack.append(hd_dim)

                block_h = SkullaLayoutRouter.execute_stack_layout(
                    canvas=canvas, session_path=s_path, badge_stack=text_badge_stack,
                    layout_type="bottom_icon_grid", side_position=anchor_matrix_text, margin_bounds=margin_bounds,
                    is_icon_mode=False, priority_level=2, base_y_hd=current_top_y_hd, gravity="top"
                )
                current_top_y_hd += block_h + 20

            # 🛠️ 4. Про-значки нижней ленты (Проход TOP)
            elif ctrl_id == "bottom_icons":
                icons_grav = next((c.get("default", "bottom") for c in controls_config if c["id"] == "icons_gravity"), "bottom")
                if icons_grav != "top" or not bottom_icons_raw.strip(): 
                    continue
                
                lines_icons = [line.strip() for line in bottom_icons_raw.split("\n") if line.strip()]
                icon_badge_stack = []
                
                for idx, icon_txt in enumerate(lines_icons):
                    if idx == 0:
                        hd_dim = save_decoupl_badge_assets(s_path, icon_txt, font_path, f_size, icon_shape, 18, 18, 0, style_bg_color, style_bg_alpha, style_border_color, 255, style_border_width, style_text_color, 255)
                        master_icon_w = int(hd_dim["width"] * 1.1)
                        master_icon_h = int(hd_dim["height"] * 1.1)
                        hd_dim = save_decoupl_badge_assets(s_path, icon_txt, font_path, f_size, icon_shape, 18, 18, 0, style_bg_color, style_bg_alpha, style_border_color, 255, style_border_width, style_text_color, 255, force_width=master_icon_w, force_height=master_icon_h)
                    else:
                        hd_dim = save_decoupl_badge_assets(
                            session_path=s_path, text=icon_txt, font_path=font_path, font_size=f_size, 
                            shape=icon_shape, padding=18, radius=18, skew_px=0, 
                            bg_color=style_bg_color, bg_alpha=style_bg_alpha, border_color=style_border_color, 
                            border_alpha=255, border_width=style_border_width, text_color=style_text_color, text_alpha=255, 
                            force_width=master_icon_w, force_height=master_icon_h
                        )
                    icon_badge_stack.append(hd_dim)

                block_h = SkullaLayoutRouter.execute_stack_layout(
                    canvas=canvas, session_path=s_path, badge_stack=icon_badge_stack,
                    layout_type="bottom_icon_grid", side_position=anchor_matrix_icons, margin_bounds=margin_bounds,
                    is_icon_mode=True, priority_level=3, base_y_hd=current_top_y_hd, gravity="top"
                )
                current_top_y_hd += block_h + 20

            # 💥 5. Промо-тег скидки (Проход TOP)
            elif ctrl_id == "promo_tag":
                promo_grav = next((c.get("default", "bottom") for c in controls_config if c["id"] == "promo_gravity"), "bottom")
                if promo_grav != "top" or not p_tag.strip():
                    continue

                # Нарезаем Full HD ассет промо-ленты по нашим динамическим цветам и шрифту плашек
                promo_dim = save_decoupl_badge_assets(
                    s_path, p_tag, font_path, f_size, b_shape, 30, 16, 22,
                    style_bg_color, style_bg_alpha, style_border_color, 255,
                    style_border_width, style_text_color, 255
                )
                
                promo_badge_stack = [promo_dim]

                # 🎯 РОДНОЙ СТАНДАРТ ШЕФА: Передаем плашку в универсальный роутер компоновщика макетов!
                # Он сам распарсит промо_matrix ("1", "2" или "3"), высчитает X и нативно нанесет на холст!
                block_h = SkullaLayoutRouter.execute_stack_layout(
                    canvas=canvas, session_path=s_path, badge_stack=promo_badge_stack,
                    layout_type="bottom_icon_grid", side_position=promo_matrix, margin_bounds=margin_bounds,
                    is_icon_mode=False, priority_level=5, base_y_hd=current_top_y_hd, gravity="top"
                )
                current_top_y_hd += block_h + 20


        # ==============================================================================
        # 🛠️ ПРОХОД №2: СНИЗУ ВВЕРХ (BOTTOM ГРАВИТАЦИЯ) [INDEX]
        # ==============================================================================
        # Стартовая донная линия — прижата к нижнему полю макета
        current_bottom_y_hd = int(H_hd - margin_bounds)

        for ctrl in reversed(controls_config):
            ctrl_id = ctrl["id"]

            # 💥 1. Промо-тег скидки (Проход BOTTOM)
            if ctrl_id == "promo_tag":
                promo_grav = next((c.get("default", "bottom") for c in controls_config if c["id"] == "promo_gravity"), "bottom")
                if promo_grav != "bottom" or not p_tag.strip():
                    continue

                promo_dim = save_decoupl_badge_assets(
                    s_path, p_tag, font_path, f_size, b_shape, 30, 16, 22,
                    style_bg_color, style_bg_alpha, style_border_color, 255,
                    style_border_width, style_text_color, 255
                )
                
                promo_badge_stack = [promo_dim]

                # 🎯 РОДНОЙ СТАНДАРТ ШЕФА ДЛЯ ПОДВАЛА (Проход BOTTOM):
                block_h = SkullaLayoutRouter.execute_stack_layout(
                    canvas=canvas, session_path=s_path, badge_stack=promo_badge_stack,
                    layout_type="bottom_icon_grid", side_position=promo_matrix, margin_bounds=margin_bounds,
                    is_icon_mode=False, priority_level=5, base_y_hd=current_bottom_y_hd - 50, gravity="bottom"
                )
                current_bottom_y_hd -= (block_h + 20)


            # 🛠️ 2. Про-значки нижней ленты (Проход BOTTOM)
            elif ctrl_id == "bottom_icons":
                icons_grav = next((c.get("default", "bottom") for c in controls_config if c["id"] == "icons_gravity"), "bottom")
                if icons_grav != "bottom" or not bottom_icons_raw.strip(): 
                    continue
                
                lines_icons = [line.strip() for line in bottom_icons_raw.split("\n") if line.strip()]
                icon_badge_stack = []
                
                for idx, icon_txt in enumerate(lines_icons):
                    if idx == 0:
                        hd_dim = save_decoupl_badge_assets(
                            session_path=s_path, text=icon_txt, font_path=font_path, font_size=f_size, 
                            shape=icon_shape, padding=18, radius=18, skew_px=0, 
                            bg_color=style_bg_color, bg_alpha=style_bg_alpha, border_color=style_border_color, 
                            border_alpha=255, border_width=style_border_width, text_color=style_text_color, text_alpha=255
                        )
                        master_icon_w = int(hd_dim["width"] * 1.1)
                        master_icon_h = int(hd_dim["height"] * 1.1)
                        hd_dim = save_decoupl_badge_assets(
                            session_path=s_path, text=icon_txt, font_path=font_path, font_size=f_size, 
                            shape=icon_shape, padding=18, radius=18, skew_px=0, 
                            bg_color=style_bg_color, bg_alpha=style_bg_alpha, border_color=style_border_color, 
                            border_alpha=255, border_width=style_border_width, text_color=style_text_color, text_alpha=255, 
                            force_width=master_icon_w, force_height=master_icon_h
                        )
                    else:
                        hd_dim = save_decoupl_badge_assets(
                            session_path=s_path, text=icon_txt, font_path=font_path, font_size=f_size, 
                            shape=icon_shape, padding=18, radius=18, skew_px=0, 
                            bg_color=style_bg_color, bg_alpha=style_bg_alpha, border_color=style_border_color, 
                            border_alpha=255, border_width=style_border_width, text_color=style_text_color, text_alpha=255, 
                            force_width=master_icon_w, force_height=master_icon_h
                        )
                    icon_badge_stack.append(hd_dim)

                active_dots = sorted(list(set([int(d) for d in str(anchor_matrix_icons).split(",") if d.strip().isdigit()])))
                if len(active_dots) == 1: 
                    estimated_rows = len(icon_badge_stack)
                # 🎯 СУПЕР-ФИКС ШЕФА: Вшили пропущенный массив сплит-системы [1, 3]!
                elif active_dots == [1, 3]: 
                    estimated_rows = math.ceil(len(icon_badge_stack) / 2)
                else: 
                    estimated_rows = math.ceil(len(icon_badge_stack) * master_icon_w / (900 - 108))
                    
                estimated_block_h = (estimated_rows * master_icon_h) + ((estimated_rows - 1) * 20)
                current_bottom_y_hd -= estimated_block_h
                
                SkullaLayoutRouter.execute_stack_layout(
                    canvas=canvas, session_path=s_path, badge_stack=icon_badge_stack,
                    layout_type="bottom_icon_grid", side_position=anchor_matrix_icons, margin_bounds=margin_bounds,
                    is_icon_mode=True, priority_level=3, base_y_hd=current_bottom_y_hd, gravity="bottom"
                )
                current_bottom_y_hd -= 20

            # 📝 3. АТОМАРНАЯ ПОДМЕНА ШЕФА: Динамический Max-Сплит Характеристик (Проход BOTTOM)
            # 📝 3. АТОМАРНАЯ ПОДМЕНА ШЕФА: Динамический Max-Сплит Характеристик (Проход BOTTOM)
            elif ctrl_id == "features_flow_gravity":
                flow_grav = ctrl.get("default", "top")
                # 🎯 ФИКС ШЕФА: Если гравитация TOP — жёстко пропускаем этот блок во 2-м проходе,
                # блокируя наложение нижнего потока на верхний воздух!
                if flow_grav == "top" or flow_grav != "bottom": 
                    continue

                
                f_texts = [
                    params.get("feature_1", ""), 
                    params.get("feature_2", ""), 
                    params.get("feature_3", "")
                ]
                f_photos = [
                    "original.png", 
                    params.get("extra_photo_1", ""), 
                    params.get("extra_photo_2", "")
                ]
                
                frame_shape = params.get("frame_shape", "circle")
                show_text_border = params.get("show_text_border", "false") == "true"
                show_photo_border = params.get("show_photo_border", "true") == "true"
                
                # Снаряжаем массив трех независимых тумблеров направлений строк
                row_directions = [
                    params.get("row_1_direction", "text_first"),
                    params.get("row_2_direction", "text_first"),
                    params.get("row_3_direction", "text_first")
                ]
                
                # Покомпонентно сканируем строки в обратном порядке (снизу вверх)
                for i in reversed(range(3)):
                    txt = f_texts[i]
                    photo_name = f_photos[i]
                    if not txt.strip(): 
                        continue
                    
                    # Извлекаем индивидуальный тумблер для текущей нижней строки
                    current_row_order = row_directions[i]
                    
                    txt_alpha_bg = style_bg_alpha if show_text_border else 0
                    txt_alpha_border = 255 if show_text_border else 0
                    photo_alpha_border = 255 if show_photo_border else 0
                    
                    # Замер высоты текста (force_height=None)
                    raw_txt_dim = save_decoupl_badge_assets(
                        session_path=s_path, text=txt, font_path=font_path, font_size=f_size, shape=b_shape, 
                        padding=30, radius=16, skew_px=22, bg_color=style_bg_color, bg_alpha=txt_alpha_bg, 
                        border_color=style_border_color, border_alpha=txt_alpha_border, border_width=style_border_width, 
                        text_color=style_text_color, text_alpha=255
                    )
                    
                    # Замер высоты фрейма фото (force_height=None)
                    raw_frame_dim = save_decoupl_frame_assets(
                        session_path=s_path, img_filename=photo_name, frame_shape=frame_shape, 
                        border_color=style_border_color, border_alpha=photo_alpha_border, border_width=style_border_width, 
                        scale_pct=user_scale_pct
                    )
                    
                    # Вычисляем точную Мастер-Высоту строки
                    master_row_h = max(int(raw_txt_dim["height"] * 1.1), raw_frame_dim["height"])
                    
                    # Заранее выталкиваем донную координату Y вверх на высоту текущей обрабатываемой строки
                    current_bottom_y_hd -= master_row_h
                    
                    # Чистовой рендеринг ассетов, зажатых в единый калибр высоты строки
                    final_txt_badge = save_decoupl_badge_assets(
                        session_path=s_path, text=txt, font_path=font_path, font_size=f_size, shape=b_shape, 
                        padding=30, radius=16, skew_px=22, bg_color=style_bg_color, bg_alpha=txt_alpha_bg, 
                        border_color=style_border_color, border_alpha=txt_alpha_border, border_width=style_border_width, 
                        text_color=style_text_color, text_alpha=255, force_height=master_row_h
                    )
                    
                    final_frame_badge = save_decoupl_frame_assets(
                        session_path=s_path, img_filename=photo_name, frame_shape=frame_shape, 
                        border_color=style_border_color, border_alpha=photo_alpha_border, border_width=style_border_width, 
                        scale_pct=user_scale_pct if 'user_scale_pct' in locals() else 1.0, force_height=master_row_h
                    )
                    
                    # 🎯 ТОЧЕЧНЫЙ ФИКС ШЕФА: Передаем кнопки матрицы "1" и "3" вместо сырых пикселей X!
                    if current_row_order == "text_first":
                        pos_text = "1"
                        pos_photo = "3"
                    else:
                        pos_photo = "1"
                        pos_text = "3"
                    
                    # Отрисовка текстовой плашки строки Снизу Вверх
                    SkullaLayoutRouter.execute_stack_layout(
                        canvas=canvas, session_path=s_path, badge_stack=[final_txt_badge],
                        layout_type="bottom_icon_grid", side_position=pos_text, margin_bounds=margin_bounds,
                        is_icon_mode=False, priority_level=2, base_y_hd=current_bottom_y_hd, gravity="bottom"
                    )
                    
                    # Отрисовка фото-фрейма строки Снизу Вверх
                    SkullaLayoutRouter.execute_stack_layout(
                        canvas=canvas, session_path=s_path, badge_stack=[final_frame_badge],
                        layout_type="bottom_icon_grid", side_position=pos_photo, margin_bounds=margin_bounds,
                        is_icon_mode=False, priority_level=4, base_y_hd=current_bottom_y_hd, gravity="bottom"
                    )

                    
                    # Подаем донную линию еще выше на величину межстрочного зазора для следующего этажа
                    current_bottom_y_hd -= 35


            # 📝 4. Список плашек УТП (Проход BOTTOM)
            elif ctrl_id == "badges_list":
                text_grav = next((c.get("default", "top") for c in controls_config if c["id"] == "text_gravity"), "top")
                if text_grav != "bottom" or not badges_list_raw.strip(): 
                    continue
                
                lines_text = [line.strip() for line in badges_list_raw.split("\n") if line.strip()]
                text_badge_stack = []
                
                for idx, txt in enumerate(lines_text):
                    if idx == 0:
                        hd_dim = save_decoupl_badge_assets(
                            session_path=s_path, text=txt, font_path=font_path, font_size=f_size, shape=b_shape, 
                            padding=30, radius=16, skew_px=22, bg_color=style_bg_color, bg_alpha=style_bg_alpha, 
                            border_color=style_border_color, border_alpha=255, border_width=style_border_width, text_color=style_text_color, text_alpha=255
                        )
                        master_text_h = int(hd_dim["height"] * 1.1)
                        hd_dim = save_decoupl_badge_assets(
                            session_path=s_path, text=txt, font_path=font_path, font_size=f_size, shape=b_shape, 
                            padding=30, radius=16, skew_px=22, bg_color=style_bg_color, bg_alpha=style_bg_alpha, 
                            border_color=style_border_color, border_alpha=255, border_width=style_border_width, text_color=style_text_color, text_alpha=255, 
                            force_height=master_text_h
                        )
                    else:
                        hd_dim = save_decoupl_badge_assets(
                            session_path=s_path, text=txt, font_path=font_path, font_size=f_size, shape=b_shape, 
                            padding=30, radius=16, skew_px=22, bg_color=style_bg_color, bg_alpha=style_bg_alpha, 
                            border_color=style_border_color, border_alpha=255, border_width=style_border_width, text_color=style_text_color, text_alpha=255, 
                            force_height=master_text_h
                        )
                    text_badge_stack.append(hd_dim)

                active_dots = sorted(list(set([int(d) for d in str(anchor_matrix_text).split(",") if d.strip().isdigit()])))
                if len(active_dots) == 1: 
                    estimated_rows = len(text_badge_stack)
                elif active_dots == [1, 3]: 
                    estimated_rows = math.ceil(len(text_badge_stack) / 2)
                else: 
                    estimated_rows = math.ceil(len(text_badge_stack) * avg_w_hd / (900 - 108))
                    
                estimated_block_h = (estimated_rows * master_text_h) + ((estimated_rows - 1) * 20)
                current_bottom_y_hd -= estimated_block_h
                
                SkullaLayoutRouter.execute_stack_layout(
                    canvas=canvas, session_path=s_path, badge_stack=text_badge_stack,
                    layout_type="bottom_icon_grid", side_position=anchor_matrix_text, margin_bounds=margin_bounds,
                    is_icon_mode=False, priority_level=2, base_y_hd=current_bottom_y_hd, gravity="bottom"
                )
                current_bottom_y_hd -= 20

            # 👑 5. Главный заголовок (Проход BOTTOM)
            elif ctrl_id == "main_title":
                title_grav = next((c.get("default", "top") for c in controls_config if c["id"] == "title_gravity"), "top")
                if title_grav != "bottom" or not main_title.strip(): 
                    continue
                
                title_badge_stack = []
                # 🎯 АБСОЛЮТНЫЙ ГЕОМЕТРИЧЕСКИЙ ФИКС ШЕФА ДЛЯ ПОДВАЛА:
                hd_dim = save_decoupl_badge_assets(
                    s_path, main_title, font_path=title_font_resolved, font_size=title_f_size,
                    shape="rect", padding=0, radius=0, skew_px=0, bg_color=(0,0,0), bg_alpha=0,
                    border_color=(0,0,0), border_alpha=0, border_width=0, 
                    text_color=title_text_color_rgb, text_alpha=255
                )

                title_badge_stack.append(hd_dim)
                
                current_bottom_y_hd -= hd_dim["height"]
                title_matrix = params.get("title_layout_matrix", "2")
                
                SkullaLayoutRouter.execute_stack_layout(
                    canvas=canvas, session_path=s_path, badge_stack=title_badge_stack,
                    layout_type="bottom_icon_grid", side_position=title_matrix, margin_bounds=margin_bounds,
                    is_icon_mode=False, priority_level=1, base_y_hd=current_bottom_y_hd, gravity="bottom"
                )
                current_bottom_y_hd -= 20