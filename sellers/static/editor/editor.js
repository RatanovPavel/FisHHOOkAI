// editor.js - Мозги AI STUDIO SKULLA 💀
// Глобальный объект состояния юзера
window.userState = {
    // Получаем свежий объект из памяти хедера
    get data() {
        const saved = localStorage.getItem('skulla_user');
        return (saved && saved !== "undefined") ? JSON.parse(saved) : null;
    },

    // Геттеры для костей и скаллов (теперь они лезут в объект юзера)
    get bones() {
        return this.data ? (this.data.bones || 0) : 0;
    },
    get skulls() {
        return this.data ? (this.data.skulls || 0) : 0;
    },

    // Метод обновления (вызываем после успешного экспорта)
    update: function(newBones, newSkulls) {
        let current = this.data;
        if (!current) return;

        // 1. Обновляем данные в объекте
        current.bones = newBones;
        current.skulls = newSkulls;

        // 2. Сохраняем обратно в тот же ключ, который читает хедер
        localStorage.setItem('skulla_user', JSON.stringify(current));

        // 3. Вызываем функцию синхронизации из твоего header.js (если она видна)
        if (typeof syncHeader === 'function') {
            // Подменяем глобальную переменную user, чтобы syncHeader её увидел
            window.user = current; 
            syncHeader();
        } else {
            // Если функции нет, просто обновим цифры вручную для подстраховки
            const bEl = document.getElementById('user-bones-count');
            const sEl = document.getElementById('user-skulls-count');
            if (bEl) bEl.innerText = newBones;
            if (sEl) sEl.innerText = newSkulls;
        }
        console.log("💎 [STATE]: Баланс в skulla_user обновлен:", {newBones, newSkulls});
    }
};


// ==============================================================================
// 🦴 1. ФУНКЦИЯ ДЛЯ СТАНДАРТНОГО ЭКСПОРТА (За Промо-Боны)
// ==============================================================================
window.downloadWithBones = async function() {
    const t = (key) => (window.i18n ? window.i18n.t(key) : key);
    const effect = window.currentEffect;
    if (!effect) return;

    // Считываем фиксированную промо-цену бонов напрямую из нового B2B конфига
    const econ = effect.economy || { price_bones: 10 };
    const totalCost = econ.price_bones !== undefined ? econ.price_bones : 10;
    
    // Проверка баланса промо-валюты пользователя
    const userBones = window.userState ? (window.userState.bones || 0) : 0;
    if (userBones < totalCost) {
        alert(t("editor.err_no_bones") || "Недостаточно костей 🦴 для промо-скачивания");
        return;
    }

    console.log(`🦴 [B2B EXPORT]: Запуск скачивания за фиксированные ${totalCost} бонов`);

    // 🎯 Отправляем на экспорт чистый флаг 'bones' без мусорных чекбоксов
    executeExport('bones', { 
        cost: totalCost 
    });
};

// ==============================================================================
// 💀 2. ФУНКЦИЯ ДЛЯ ПРЕМИУМ ЭКСПОРТА (За Реальные Скаллы)
// ==============================================================================
window.downloadWithSkulls = async function() {
    const t = (key) => (window.i18n ? window.i18n.t(key) : key);
    const effect = window.currentEffect;
    if (!effect) return;

    // Считываем фиксированную цену скаллов из нового B2B конфига
    const econ = effect.economy || { price_skulls: 5 };
    const configPrice = econ.price_skulls !== undefined ? econ.price_skulls : 5;
    
    // Поддержка динамической цены для видеообложек, если в конфиге пусто
    const skullsPrice = configPrice > 0 ? configPrice : (window.currentVideoPrice || 15);
    
    // Проверка баланса основной валюты пользователя
    const userSkulls = window.userState ? (window.userState.skulls || 0) : 0;
    if (userSkulls < skullsPrice) {
        alert(t("editor.err_no_skulls") || "Недостаточно скаллов 💀 для премиум-скачивания");
        return;
    }

    console.log(`💎 [B2B EXPORT]: Запуск скачивания за фиксированные ${skullsPrice} 💀`);
    
    // 🎯 Отправляем на экспорт чистый флаг 'skulls' без мусорных чекбоксов
    executeExport('skulls', { 
        cost: skullsPrice 
    });
};


// 🎯 3. УНИВЕРСАЛЬНЫЙ B2B ОТПРАВИТЕЛЬ СИНХРОНИЗИРОВАННЫЙ С FastAPI ЯДРОМ
let isExporting = false;   // Блокировка на время сетевого запроса
let isResultPaid = false;  // Статус оплаты текущей генерации

async function executeExport(mode, options) {
    // 1. ЗАЩИТА: От спам-кликов
    if (isExporting) return;

    const t = (key) => (window.i18n ? window.i18n.t(key) : key);

    // 2. ЗАЩИТА: От повторной покупки
    if (isResultPaid) {
        alert(t("editor.already_paid_msg") || "Этот результат уже сохранен. Нажмите 'Применить', чтобы создать новый.");
        return;
    }

    const loader = document.getElementById('loader');
    const processBtn = document.getElementById('process-btn');
    
    let originalLoaderText = "";
    if (loader) {
        const loaderTextEl = loader.querySelector('p') || loader;
        originalLoaderText = loaderTextEl.innerText;
        
        // Текст лоадера под MVP-стандарт рендера 900x1200
        loaderTextEl.innerText = mode === 'skulls' ? "Сборка премиум-оригинала 900x1200..." : "Подготовка коммерческого файла...";
        loader.classList.remove('hidden'); 
    }

    try {
        isExporting = true;

        // Синхронизация селекторов: хватаем наши новые жесткие ID кнопок
        const btnBones = document.getElementById('bones-download-btn');
        const btnSkulls = document.getElementById('skulls-download-btn');
        
        if (btnBones) btnBones.style.opacity = "0.5";
        if (btnSkulls) btnSkulls.style.opacity = "0.5";
        
        if (processBtn) processBtn.disabled = true;

        const savedData = localStorage.getItem('skulla_user');
        const token = savedData ? JSON.parse(savedData).token : null;
        const sessionId = (typeof window.currentSessionId !== 'undefined') ? window.currentSessionId : null;
        const currentStyleId = (typeof styleId !== 'undefined') ? styleId : new URLSearchParams(window.location.search).get('style');

        const params = {};
        document.querySelectorAll('[data-id]').forEach(el => { 
            params[el.dataset.id] = el.value; 
        });
        params["style_key"] = (window.category_id || "cat_undefined").trim();

        params["is_preview_mode"] = false;
        // 🎯 СИНХРОНИЗАЦИЯ ТЕЛА ЗАПРОСА (Все комментарии строго через //)
        const requestBody = {
            payment_type: mode, // Передаем строго "bones" или "skulls" в ожидаемом сервером ключе
            session_id: sessionId,
            style_id: currentStyleId,
            params: params, // Отдаем плоский объект параметров
            ...options
        };

        const response = await fetch('/api/studio/export', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}` 
            },
            body: JSON.stringify(requestBody)
        });

        const result = await response.json();

        if (result.status === 'success') {
            isResultPaid = true; 
            
            if (window.userState?.update) {
                window.userState.update(result.new_balance.bones, result.new_balance.skulls);
            }

            // Мгновенный триггер скачивания готового PNG 900x1200
            if (result.download_url) {
                const link = document.createElement('a');
                link.href = result.download_url;
                link.download = `skulla_infographic_${Date.now()}.png`; 
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }
            
            if (btnBones) {
                btnBones.style.opacity = "0.3";
                btnBones.style.cursor = "default";
            }
            if (btnSkulls) {
                btnSkulls.style.opacity = "0.3";
                btnSkulls.style.cursor = "default";
            }

        } else {
            // Обработка ошибок баланса
            if (result.detail === "INSUFFICIENT_BONES") {
                alert(t("editor.err_no_bones") || "Недостаточно костей Bone для промо-экспорта");
            } 
            else if (result.detail === "INSUFFICIENT_SKULLS") {
                alert(t("editor.err_no_skulls") || "Недостаточно скаллов Skull для премиум-экспорта");
            } 
            else {
                alert(result.detail || t("editor.err_generic") || "Ошибка транзакции списания");
            }

            if (btnBones) btnBones.style.opacity = "1";
            if (btnSkulls) btnSkulls.style.opacity = "1";
        }

    } catch (e) {
        console.error("💀 [EXPORT_CRITICAL]:", e);
        alert(t("editor.err_network") || "Ошибка связи с сервером экспорта");
    } finally {
        isExporting = false; 
        
        if (loader) {
            loader.classList.add('hidden'); 
            const loaderTextEl = loader.querySelector('p') || loader;
            loaderTextEl.innerText = originalLoaderText; 
        }
        if (processBtn) {
            processBtn.disabled = false;
            processBtn.classList.remove('opacity-50');
        }
    }
}



document.addEventListener('DOMContentLoaded', () => {
    const checkboxes = document.querySelectorAll('#export-bones-panel input[type="checkbox"]');
    const bonesBtn = document.querySelector('#export-bones-panel button');

    const t = (key) => (window.i18n ? window.i18n.t(key) : key);

    window.updatePriceDisplay = () => {
        const effect = window.currentEffect; 
        if (!effect) return;

        const t = (key) => (window.i18n ? window.i18n.t(key) : key);

        // Считываем чистые плоские ключи из CONFIG эффекта карточки
        const econ = effect.economy || { price_bones: 10, price_skulls: 5 };
        const priceBones = econ.price_bones !== undefined ? econ.price_bones : 10;
        const priceSkulls = econ.price_skulls !== undefined ? econ.price_skulls : 5;

        const bonesBtn = document.getElementById('bones-download-btn');
        const skullsBtn = document.getElementById('skulls-download-btn');

        // Насильно прописываем текст и цены внутрь кнопок с сохранением структуры стилей
        if (bonesBtn) {
            bonesBtn.innerHTML = `${t("editor.t18") || "ЗАГРУЗИТЬ ЗА"} <span class="text-cyan-400 font-black text-[14px]">${priceBones} 🦴</span>`;
        }
        if (skullsBtn) {
            skullsBtn.innerHTML = `${t("editor.t18") || "ЗАГРУЗИТЬ ЗА"} <span class="text-purple-400 font-black text-[14px]">${priceSkulls} 💀</span>`;
        }
    };




    checkboxes.forEach(el => el.addEventListener('change', window.updatePriceDisplay));
    window.addEventListener('languageChanged', window.updatePriceDisplay);
    window.updatePriceDisplay();
});



// 🎯 ПОСИМВОЛЬНЫЙ ДВИЖОК ИИ-КНОПКИ (УЛЬТРА-ЧИСТАЯ MVP ВЕРСИЯ: БЕЗ ШТОРКИ СРАВНЕНИЯ)
// 🎯 ПОСИМВОЛЬНЫЙ ДВИЖОК ИИ-КНОПКИ С РАЗДЕЛЕНИЕМ НА ПРЕВЬЮ И СКАЧИВАНИЕ ПО ЗАПРОСУ
document.addEventListener('DOMContentLoaded', () => {
    const processBtn = document.getElementById('process-btn');
    if (!processBtn) return;

    const t = (key) => (window.i18n ? window.i18n.t(key) : key);

    // 🎯 ВЫНОСИМ ЛОГИКУ В ЕДИНЫЙ КВАНТОВЫЙ МЕТОД ГЕНЕРАЦИИ (Доступен для кнопок скачивания снаружи!)
    window.runSkullaStudioRender = async (isPreviewMode = true) => {
        const userData = window.userState ? window.userState.data : null;
        const token = userData ? userData.token : null;

        if (!window.currentSessionId) return alert(t("editor.t5"));

        const loader = document.getElementById('loader');
        const result = document.getElementById('result');
        const procImg = document.getElementById('res-proc'); 
        
        if (procImg) {
            // 🎯 ЖЕЛЕЗНЫЙ ТРИГГЕР ШЕФА: Скроллим строго ПОСЛЕ того, как картинка полностью прогрузится в пикселях!
            procImg.onload = function() {
                console.log("📸 [SKULLA UI]: Картинка полностью отрисовалась. Врубаем снайперский скролл!");
                
                // Легкий таймаут, чтобы верстка окончательно успокоилась в DOM
                setTimeout(() => {
                    window.scrollTo({
                        top: document.body.scrollHeight, // Теперь высота посчитается идеально с учетом картинки!
                        behavior: 'smooth'               // Плавный кинематографичный съезд вниз
                    });
                }, 50);
            };
        }
        // 1. ЗАМОРОЗКА ИНТЕРФЕЙСА ПЕРЕД СБОРКОЙ
        processBtn.disabled = true;
        processBtn.innerText = isPreviewMode ? (t("editor.t6") || "ГЕНЕРАЦИЯ...") : "ВЫГРУЗКА HD..."; 
        processBtn.classList.add('opacity-50');
        if (loader) loader.classList.remove('hidden');
        if (result) result.classList.add('hidden');

        // Сбор динамических параметров карточки со страницы (ползунки, матрицы 3х3, иконки)
        const params = {};
        document.querySelectorAll('[data-id]').forEach(el => { 
            params[el.dataset.id] = el.value; 
        });
        params["style_key"] = (window.category_id || "cat_undefined").trim();

        // Вшиваем наш главный флаг стратегии внутрь params для передачи на Python бэкенд!
        params["is_preview_mode"] = isPreviewMode;

        const fd = new FormData();
        fd.append("session_id", window.currentSessionId);
        fd.append("style_id", styleId); 
        fd.append("params", JSON.stringify(params));

        try {
            const resp = await fetch('/api/studio/apply', { 
                method: 'POST', 
                headers: { 'Authorization': `Bearer ${token}` },
                body: fd 
            });

            if (!resp.ok) throw new Error("Server Error");
            const data = await resp.json();
            const timestamp = Date.now();
            
            // Если это был режим РЕНДЕРА ПРЕВЬЮ карточки (кнопка Создать)
            if (isPreviewMode) {
                // СБРОС СТАТУСА ОПЛАТЫ И ВОЗВРАТ ЯРКОСТИ КНОПОК
                if (typeof isResultPaid !== 'undefined') isResultPaid = false;
                
                const btnBones = document.getElementById('bones-download-btn');
                const btnSkulls = document.getElementById('skulls-download-btn');
                if (btnBones) btnBones.style.opacity = "1";
                if (btnSkulls) btnSkulls.style.opacity = "1";

                const isVideoEffect = data.is_video === true;
                const afterUrl = `/api/studio/preview/${window.currentSessionId}/after?t=${timestamp}`;

                // 🎯 ОБРАБОТКА МЕДИА ПРЕВЬЮ ДЛЯ ВИДЕО-ОБЛОЖЕК
                if (isVideoEffect) {
                    if (procImg) procImg.style.display = 'none';
                    let videoEl = document.getElementById('res-proc-video');
                    
                    if (!videoEl) {
                        const wrap = document.getElementById('res-proc-wrap');
                        if (wrap) {
                            videoEl = document.createElement('video');
                            videoEl.id = 'res-proc-video';
                            videoEl.className = 'w-full h-full object-contain rounded-2xl';
                            videoEl.autoplay = true;
                            videoEl.loop = true;
                            videoEl.muted = true;
                            videoEl.setAttribute('playsinline', '');
                            videoEl.setAttribute('webkit-playsinline', '');
                            wrap.appendChild(videoEl);
                        }
                    }
                    if (videoEl) {
                        videoEl.style.display = 'block';
                        videoEl.src = `${afterUrl}&v=${timestamp}`;
                        videoEl.type = 'video/mp4';
                        videoEl.load();
                        videoEl.play().catch(e => console.log("MP4 Autoplay forced retry...", e));
                    }

                    if (loader) loader.classList.add('hidden');
                    if (result) { result.classList.remove('hidden'); result.style.display = 'block'; }
                    
                    processBtn.disabled = false;
                    processBtn.innerText = t("editor.t15") || "СОЗДАТЬ КАРТОЧКУ";
                    processBtn.classList.remove('opacity-50');

                    if (data.price_skulls) {
                        window.currentVideoPrice = data.price_skulls;
                        const seconds = data.duration ? Number(data.duration).toFixed(1) : "0.0";
                        const price = Number(data.price_skulls) || 15;
                        if (btnSkulls) {
                            const baseText = t("editor.t13") || "ЗАГРУЗИТЬ ЗА";
                            btnSkulls.innerHTML = `${baseText} <span class="text-purple-400 font-black text-[14px]">${price} 💀</span> <span class="text-[10px] opacity-60">• (${seconds}s)</span>`;
                        }
                    }

                } else {
                    // 📸 ЧИСТЫЙ ВЫВОД ГОТОВОЙ КАРТИНКИ КАРТОЧКИ (Сжатое 450х600 с ватермарком)
                    const videoEl = document.getElementById('res-proc-video');
                    if (videoEl) videoEl.style.display = 'none';
                    
                    if (procImg) {
                        procImg.style.display = 'block';
                        procImg.src = afterUrl;
                        procImg.style.width = "100%";
                        procImg.style.height = "auto";
                        procImg.style.maxHeight = "70vh"; 
                    }
                    
                    const tempImg = new Image();
                    tempImg.src = afterUrl;
                    
                    tempImg.decode().then(() => {
                        if (loader) loader.classList.add('hidden');
                        if (result) { result.classList.remove('hidden'); result.style.display = 'block'; }
                        
                        processBtn.disabled = false;
                        processBtn.innerText = t("editor.t15") || "СОЗДАТЬ КАРТОЧКУ";
                        processBtn.classList.remove('opacity-50');

                        if (window.updatePriceDisplay) window.updatePriceDisplay();
                    });
                }
                
                // Обновляем баланс пользователя на лету после легкого рендера
                if (data.new_balance && window.userState && window.userState.update) {
                    window.userState.update(data.new_balance.bones, data.new_balance.skulls);
                }

            } else {
                // 🎯 СЦЕНАРИЙ СКАЧИВАНИЯ БОЕВОГО Full HD ОРИГИНАЛА 900x1200 ЗА ВАЛЮТУ!
                // Размораживаем кнопку Создать
                if (loader) loader.classList.add('hidden');
                if (result) { result.classList.remove('hidden'); result.style.display = 'block'; }
                processBtn.disabled = false;
                processBtn.innerText = t("editor.t15") || "СОЗДАТЬ КАРТОЧКУ";
                processBtn.classList.remove('opacity-50');

                // 🎯 АБСОЛЮТНЫЙ ФИКС ШЕФА НА ФРОНТЕНДЕ:
                // Больше никакого хардкода after_full! Скрипт берет чистейшую, готовую HD-ссылку,
                // которую бэкенд-роутер сгенерировал и прислал в переменной data.download_url! [INDEX]
                const downloadUrl = data.download_url;
                
                if (downloadUrl) {
                    const link = document.createElement('a');
                    link.href = downloadUrl;
                    
                    // Формируем красивое имя для скачивания селлеру (берем имя стиля карточки)
                    const styleId = document.getElementById('ctrl-style_id')?.value || 'infographics';
                    link.download = `${styleId}_full_hd_cover.png`;
                    
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                } else {
                    console.error("❌ [FRONTEND EXPORT ERROR]: Бэкенд не прислал download_url в ответе!");
                }
                
                // Обновляем баланс кошелька, с которого Python списал 10 бонов или 5 черепов
                if (data.new_balance && window.userState && window.userState.update) {
                    window.userState.update(data.new_balance.bones, data.new_balance.skulls);
                }
                console.log("🏆 [SKULLA DRM]: Кристальный Full HD оригинал успешно отдан в Загрузки!");
            }

            window.toggleSkullaEditorMode(true);
            if (typeof window.stopSkullaAiGenerationLoader === 'function') {
                window.stopSkullaAiGenerationLoader();
            }
            if (typeof ym === 'function') ym(108990860, 'reachGoal', 'ai_start');

        } catch (err) {
            console.error("❌ [STUDIO_PROCESS_CRASH]: Ошибка обработки медиа-запроса:", err);
            if (loader) loader.classList.add('hidden');
            processBtn.disabled = false;
            processBtn.innerText = t("editor.t16") || "ОШИБКА";
            processBtn.classList.remove('opacity-50');
        }
    };

    // Нажатие на базовую кнопку "Создать карточку" силой вызывает рендер в режиме превью!
    processBtn.onclick = () => window.runSkullaStudioRender(true);

});
