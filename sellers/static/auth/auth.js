// 🔥 ЛОВИМ БЛОГЕРА ИЗ URL (например: skulla.ru/register?ref=pavel)
(function() {
    const urlParams = new URLSearchParams(window.location.search);
    const refBlogger = urlParams.get('ref');
    
    if (refBlogger) {
        // Сохраняем маленькими буквами без пробелов, чтобы база не спотыкалась
        localStorage.setItem('skulla_ref_blogger', refBlogger.toLowerCase().trim());
        console.log(`[Рефералка]: Запомнили блогера: ${refBlogger}`);
    }
})();


function showError(input, message) {
    if (!input) return;
    
    // 1. Подсветка рамки
    input.classList.add('border-red-500', 'animate-shake');
    
    // 2. Получаем текст ошибки
    const errorText = (window.i18n && typeof window.i18n.t === 'function') 
        ? window.i18n.t(message) 
        : message;

    // 3. Создаем или находим блок для текста
    let errorDiv = input.parentElement.querySelector('.error-msg-popup');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'error-msg-popup text-[8px] text-red-500 mt-1 uppercase font-black tracking-widest animate-fadeIn';
        input.insertAdjacentElement('afterend', errorDiv);
    }
    errorDiv.innerText = errorText;

    console.warn(`⚠️ [AUTH_VALIDATION]: ${errorText}`);

    // 4. Удаляем всё через 3 секунды
    setTimeout(() => {
        input.classList.remove('border-red-500', 'animate-shake');
        if (errorDiv) errorDiv.remove();
    }, 3000);
}



// 3. Функция выхода (ПОЛНАЯ ОЧИСТКА)
// // 3. Функция выхода (ПОЛНАЯ ОЧИСТКА)
// 🎯 СКАЛЛА-ФИКС: Делаем функцию асинхронной (async), чтобы Хром успел дождаться бэкенда!
async function handleLogout() {
    console.log("📡 [SKULLA LOGOUT]: Запускаем уничтожение сессии селлера...");

    try {
        // 🔥 ГЛАВНЫЙ СНАЙПЕРСКИЙ ВЫСТРЕЛ: Шлем скрытый запрос бэкенду, чтобы он стёр куку из Хрома!
        // Роут /api/auth/logout сотрет skulla_token на уровне ядра сервера!
        await fetch('/api/auth/logout', { method: 'POST' });
    } catch (e) {
        console.warn("⚠️ Сервер не ответил на логаут, чистим фронтенд принудительно...", e);
    }

    // Твой оригинальный рабочий код со скриншота без изменений:
    localStorage.removeItem('skulla_user');
    user = { isLoggedIn: false, email: '', tokens: 0, is_verified: false };
    
    if (typeof syncHeader === 'function') syncHeader();
    if (typeof showLoginForm === 'function') showLoginForm();
    console.log("SYSTEM: Сессия полностью стерта.");

    // 🎯 ФИНАЛЬНЫЙ СУПЕР-ХАК: Принудительно обновляем корень сайта!
    // Теперь, когда кука на бэке стёрта, а localStorage чист — Хром при перезагрузке
    // упрётся в наш новый кордон, жестко заблокирует сайт размытием и выкинет auth-modal!
    window.location.href = "/";
}



function validateAuth(fields) {
    let isValid = true;
    
    // Хелпер для безопасного получения перевода
    const getT = (key) => {
        return (window.i18n && typeof window.i18n.t === 'function') 
            ? window.i18n.t(key) 
            : key; // Если перевода нет, вернет сам ключ (типа "auth.t12")
    };

    fields.forEach(fieldId => {
        const input = document.getElementById(fieldId);
        if (!input) return;

        const existingError = input.parentElement.querySelector('.error-msg');
        if (existingError) existingError.remove();

        const value = input.value.trim();

        // 1. Проверка на пустоту
        if (!value) {
            showError(input, getT('auth.t12'));
            isValid = false;
        } 
        // 2. Проверка Email
        else if (fieldId.includes('email') && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
            showError(input, getT('auth.t13'));
            isValid = false;
        }
        // 3. Проверка Пароля
        else if (fieldId.includes('pass') && value.length < 6) {
            showError(input, getT('auth.t14'));
            isValid = false;
        }
    });
    
    return isValid;
}

async function resendCode(email) {
    const fd = new FormData();
    fd.append('email', email); 

    try {
        // 🎯 Стучимся в новый эндпоинт
        const response = await fetch('/api/auth/resend_verify', { 
            method: 'POST', 
            body: fd 
        });
        
        if (response.ok) {
            alert("📩 КОД АКТИВАЦИИ ОТПРАВЛЕН!");
            showVerifyForm(email);
        }
    } catch (e) {
        console.error("Resend_Error:", e);
    }
}

function showVerifyForm(email) {
    const container = document.getElementById('auth-content');
    if (!container) return;

    // Безопасный хелпер перевода
    const t = (key) => (window.i18n && i18n.t ? i18n.t(key) : key);

    container.innerHTML = `
        <h2 class="logo-neon text-2xl mb-6 uppercase" data-i18n="auth.t17">${t('auth.t17')}</h2>
        <p class="text-[10px] text-slate-400 mb-6 uppercase tracking-widest leading-relaxed">
            <span data-i18n="auth.t1">${t('auth.t1')}</span> <br>
            <span id="display-email" class="text-cyan-400">${email}</span>
        </p>
        <div class="space-y-4">
            <!-- 🎯 Поле для кода -->
            <input type="text" id="verify-code" maxlength="6" placeholder="${t('auth.t18')}" 
                class="auth-input text-center text-xl tracking-[0.5em] font-black">
            
            <!-- 🎯 Кнопка теперь передает email надежнее -->
            <button onclick="handleVerify('${email.trim()}')" 
                    id="verify-btn"
                    data-i18n="auth.t2" 
                    class="w-full bg-cyan-600 hover:bg-cyan-500 text-slate-950 py-3 rounded-xl font-black uppercase text-[10px] tracking-widest transition-all shadow-[0_0_20px_rgba(34,211,238,0.3)]">
                ${t('auth.t2')}
            </button>
        </div>
    `;
    console.log(`🛠 [UI]: Форма верификации отрисована для ${email}`);
}


async function handleVerify(email) {
    const codeInput = document.getElementById('verify-code');
    const code = codeInput.value.trim();

    const formData = new FormData();
    formData.append('email', email);
    formData.append('code', code);

    try {
        const response = await fetch('/api/auth/verify', { 
            method: 'POST', 
            body: formData 
        });
        
        const data = await response.json();

        if (response.ok) {
            // 1. Уведомление (используем данные из ответа, если сервер прислал бонус)
            alert(`🔥 ${i18n.t('auth.t16')}`);
            
            // 2. ОБНОВЛЯЕМ ДАННЫЕ В ПАМЯТИ
            if (window.user) {
                window.user.is_verified = true;
                
                // Записываем новые значения Bones и Skulls, которые прислал бэкенд
                if (data.bones !== undefined) window.user.bones = data.bones;
                if (data.skulls !== undefined) window.user.skulls = data.skulls;

                localStorage.setItem('skulla_user', JSON.stringify(window.user));
            }

            // 3. СИНХРОНИЗИРУЕМ ЭКРАН (теперь цифры изменятся в шапке и кабинете)
            if (typeof syncHeader === 'function') syncHeader();
            //if (typeof showDashboard === 'function') showDashboard();

            // 4. Закрываем модалку
            const modal = document.getElementById('auth-modal');
            if (modal) {
                modal.classList.add('hidden');
            }
        } else {
            showError(codeInput, i18n.t('auth.t15')); 
        }
    } catch (e) {
        console.error("❌ [VERIFY_ERROR]:", e);
    }
}





// --- РЕГИСТРАЦИЯ ---
async function handleRegister(btnElement) {
    const emailInput = document.getElementById('reg-email');
    const passInput = document.getElementById('reg-pass');
    // Находим кнопку, чтобы она не "залипала"
    const regBtn = btnElement || document.querySelector('button[onclick*="handleRegister"]');

    if (!validateAuth(['reg-email', 'reg-pass'])) return;

    // 1. Блокируем кнопку на время запроса
    if (regBtn) {
        regBtn.disabled = true;
        regBtn.style.opacity = '0.5';
    }

    const formData = new FormData();
    formData.append('email', emailInput.value.trim()); // Триммим пробелы
    formData.append('password', passInput.value);
    // Вытаскиваем блогера из памяти, если селлер пришел по его ссылке
    const savedBlogger = localStorage.getItem('skulla_ref_blogger');
    if (savedBlogger) {
        formData.append('ref_from_url', savedBlogger);
    }

    try {
        const response = await fetch('/api/auth/register', { method: 'POST', body: formData });
        
        // Проверяем статус ответа
        // Проверяем статус ответа от Бэкенда Питона (Юзер успешно создан)
        if (response.ok) {
            const regData = await response.json();
            console.log("🍏 [SKULLA REG SUCCESS]: Юзер создан! Запускаем нативную цепочку бонусов...");

            // Нативно забираем email прямо из текстового инпута формы регистрации Павла
            const finalEmail = emailInput ? emailInput.value.trim() : "";

            // 1. Сначала СТРОГО и ЖЕСТКО записываем первичный стейт селлера в память Хрома
            // Это нужно, чтобы функция checkDailyBones() прошла свою проверку на строке 84!
            const userData = {
                isLoggedIn: true,
                email: finalEmail,
                bones: 0,
                skulls: 0,
                is_verified: false,
                token: "session_registered_auto",
                role: "user",
                partner_balance: (regData && regData.user && regData.user.partner_balance) || 0.0
            };

            window.user = userData;
            localStorage.setItem('skulla_user', JSON.stringify(userData));
            // Аккаунт создан, реферальный след можно убрать из памяти браузера
            localStorage.removeItem('skulla_ref_blogger');


            // Обновляем базовый заголовок
            if (typeof syncHeader === 'function') syncHeader();

            // 2. 🔥 ГЛАВНЫЙ СНАЙПЕРСКИЙ ВЫСТРЕЛ ВЕКА: Вызываем твою асинхронную функцию из header.js!
            // Мы пишем ключевое слово await, чтобы Хром сначала железно дождался ответа от бэкенда экономики,
            // закинул приветственные боны в updateUser() на строке 91, и перерисовал правый угол страницы!
            if (typeof checkDailyBones === 'function') {
                //await checkDailyBones();
                console.log("🍏 [SKULLA ECONOMY]: Нативный метод checkDailyBones() успешно отработал!");
            }

            // 3. 🎯 ФИНАЛ: Только теперь, когда балансы Павла нативно перерисованы на экране, гасим модалку!
            const modal = document.getElementById('auth-modal');
            if (modal) {
                modal.style.display = 'none';
                modal.classList.add('hidden');
                console.log("🏆 [SKULLA DOM SUCCESS]: Форма auth-modal полностью скрыта!");
            }
            document.querySelectorAll('.modal-backdrop, .modal-bg').forEach(el => el.remove());

            if (typeof checkSkullaActiveActions === 'function') {
                console.log("💥 [SKULLA]: Запускаем акцию на живую для нового селлера!");
                await checkSkullaActiveActions(userData.email);
            }
        } else {
            const data = await response.json();
            // Показываем ошибку (например, "Email занят")
            showError(emailInput, data.detail || i18n.t('auth.t20'));
        }
    } catch (e) {
        console.error("Critical_Reg_Error:", e);
        alert(i18n.t('auth.t22')); // "Ошибка связи с ядром"
    } finally {
        // 3. Разблокируем кнопку в любом случае
        if (regBtn) {
            regBtn.disabled = false;
            regBtn.style.opacity = '1';
        }
    }
}


// --- ВХОД ---
async function handleLogin(btnElement) {
    const emailInput = document.getElementById('auth-email');
    const passInput = document.getElementById('auth-pass');

    // // 1. Улучшенный поиск кнопки (ищем именно ту, по которой кликнули)
    const loginBtn = btnElement || document.querySelector('#auth-content button');

    const t = (key) => (window.i18n && typeof i18n.t === 'function' ? i18n.t(key) : key);

    // // 2. ВАЛИДАЦИЯ (Если пароль < 6 символов, функция прервется ТУТ)
    if (!validateAuth(['auth-email', 'auth-pass'])) return;

    // // 3. БЛОКИРОВКА КНОПКИ (Только после успешной валидации)
    if (loginBtn) {
        loginBtn.disabled = true;
        loginBtn.style.opacity = "0.5";
        loginBtn.style.cursor = "not-allowed";
        loginBtn.innerText = t('editor.t5'); // // "ОЖИДАНИЕ..."
    }

    try {
        const formData = new FormData();
        formData.append('email', emailInput.value.trim());
        formData.append('password', passInput.value);

        const response = await fetch('/api/auth/login', { method: 'POST', body: formData });
        const data = await response.json();
        if (response.ok) {
            const userData = {
                isLoggedIn: true,
                email: data.user.email,
                bones: data.user.bones || 0,
                skulls: data.user.skulls || 0,
                is_verified: data.user.is_verified,
                token: data.user.token,
                role: data.user.role || "user",
                partner_balance: data.user.partner_balance || 0.0
            };

            window.user = userData;
            localStorage.setItem('skulla_user', JSON.stringify(userData));

            checkSkullaAccessBorder();
            // 🔥 ГЛАВНЫЙ СНАЙПЕРСКИЙ ВЫСТРЕЛ ДЛЯ МГНОВЕННОГО ОТКРЫТИЯ ЛК:
            // Дублируем запись токена в куки через фронтенд нативно! 
            // Это ликвидирует асинхронный лаг Хрома и сделает сессию живой в ту же миллисекунду!
            if (data.user.token) {
                document.cookie = `skulla_token=${data.user.token}; path=/; max-age=31536000; samesite=lax; secure`;
                console.log("🍏 [SKULLA COOKIE]: Сессионный токен мгновенно запечатан в куки фронтенда!");
            }

            // На лету перерисовываем шапку и балансы Павла
            if (typeof syncheader === 'function') syncheader();
            
            // Если у тебя в проекте за открытие ЛК отвечает метод initHeader — дергаем и его для синхронизации
            if (typeof initHeader === 'function') initHeader();

            // Схлопываем модалку auth-modal по официальному ID!
            const modal = document.getElementById('auth-modal');
            if (modal) {
                modal.style.display = 'none';
                modal.classList.add('hidden');
                console.log("🏆 [SKULLA LOGIN SUCCESS]: Модалка auth-modal скрыта!");
            }

            // Нативно вырезаем темные подложки бэкдропа
            document.querySelectorAll('.modal-backdrop, .modal-bg').forEach(el => el.remove());

            // 🎯 СНИМАЕМ БЛОКИРОВКИ С ИНТЕРФЕЙСА: Сразу открываем полный доступ к ЛК и кнопкам сайта!
            const appContainer = document.getElementById('app-container') || document.querySelector('.main-app');
            if (appContainer) {
                appContainer.style.display = 'block';
                appContainer.style.pointerEvents = 'auto'; // Силой разрешаем клики по кнопке ЛК!
                appContainer.style.filter = 'none';         // Снимаем размытие кордона лендинга
            }

            if (typeof checkSkullaActiveActions === 'function') {
                console.log("💥 [SKULLA]: Запускаем акцию на живую для нового селлера!");
                await checkSkullaActiveActions(userData.email);
            }
        } else {
            // // ОШИБКА: Неверный пароль (INVALID_CREDENTIALS)
            const errorKey = data.detail === "INVALID_CREDENTIALS" ? 'auth.t23' : 'auth.t20';
            showError(passInput, errorKey);
        }
    } catch (e) {
        console.error("❌ Login_Error:", e);
        alert(t('auth.t24'));
    } finally {
        // // 4. ОЖИВЛЯЕМ КНОПКУ (Выполнится всегда при ошибке сервера/сети)
        // Проверяем стейт авторизации напрямую из локальной переменной Хрома, без обращений к window.user
        const isLogged = window.user && window.user.isLoggedIn;

        if (loginBtn && !isLogged) {
            loginBtn.disabled = false;
            loginBtn.style.opacity = "1";
            loginBtn.style.cursor = "pointer";
            loginBtn.innerText = t('auth.t3'); // Возвращаем текст "ВХОД" / "АВТОРИЗАЦИЯ"
        }
    }
}




// Универсальный оживитель кнопок
function resetBtn(btn, text) {
    if (!btn) return;
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.innerText = text;
}


// --- ИНИЦИАЛИЗАЦИЯ ---
window.onload = function() {
    // Тексты в консоли оставляем на английском (это для разработчика)
    console.log("SKULLA_SYSTEM: Terminal initialization...");
    
    if (window.user && user.isLoggedIn) {
        syncHeader();
    } else {
        syncHeader();
    }
};

function openAuthModal() {
    const modal = document.getElementById('auth-modal');
    if (modal) {
        // 🔥 СКАЛЛА-ФИКС ОТКРЫТИЯ: Включаем flex через инлайн-стиль!
        modal.style.display = 'flex';
        modal.classList.remove('hidden');
    }
    
    // Твой оригинальный рабочий тернарник выбора экрана:
    user.isLoggedIn ? showDashboard() : showLoginForm();
    
    console.log("🍏 [SKULLA DOM]: Окно auth-modal успешно переключено в режим отображения.");
}

function closeAuthModal() {
    console.log("📡 [SKULLA DOM]: Клик по крестику зафиксирован. Гасим окно...");
    
    const modal = document.getElementById('auth-modal');
    if (modal) {
        // 🔥 СКАЛЛА-ФИКС ЗАКРЫТИЯ: Силой выжигаем инлайн-стиль в none, ликвидируя конфликт!
        modal.style.display = 'none';
        modal.classList.add('hidden');
    }
    
    // Вырезаем темные подложки бэкдропа, чтобы полностью разблокировать сайт для работы
    document.querySelectorAll('.modal-backdrop, .modal-bg').forEach(el => el.remove());
}

function showLoginForm() {
    const container = document.getElementById('auth-content');
    if (!container) {
        console.error("🚨 [SKULLA AUTH]: Контейнер div#auth-content не найден в DOM-дереве!");
        return;
    }

    // Хелпер безопасной локализации ключей (b2b-инкапсуляция)
    const t = (key) => (window.i18n && typeof i18n.t === 'function' ? i18n.t(key) : key);

    console.log("📡 [SKULLA AUTH]: Сборка и рендеринг b2b-формы авторизации...");

    // Генерируем стерильный, симметричный Cyberpunk-интерфейс
    let html = `
        <div class="w-full space-y-6 text-left animate-fadeIn">
            
            <!-- Заголовок окна -->
            <div class="space-y-1 text-center">
                <h3 class="text-xl font-black text-purple-400 uppercase tracking-widest drop-shadow-[0_0_10px_rgba(168,85,247,0.2)]">
                    Вход в систему
                </h3>
                <p class="text-[11px] text-slate-500 uppercase font-bold tracking-wider">
                    Личный кабинет пользователя Skulla
                </p>
            </div>

            <!-- Форма авторизации -->
            <form onsubmit="event.preventDefault(); handleLogin();" class="space-y-4">
                
                <!-- Поле ввода Email -->
                <div class="space-y-1.5">
                    <label for="auth-email" class="text-[9px] text-slate-500 uppercase font-black tracking-widest block">
                        Ваш Email
                    </label>
                    <div class="relative">
                        <input type="email" id="auth-email" required autocomplete="email" placeholder="example@company.com" 
                            class="w-full bg-slate-950/60 border border-slate-900 focus:border-purple-500/50 rounded-xl px-4 py-3.5 text-sm text-slate-100 placeholder-slate-700 outline-none transition-all duration-150">
                    </div>
                </div>

                <!-- Поле ввода Пароля -->
                <div class="space-y-1.5">
                    <div class="flex justify-between items-center">
                        <label for="auth-pass" class="text-[9px] text-slate-500 uppercase font-black tracking-widest block">
                            Пароль аккаунта
                        </label>
                        <!-- Опционально: кнопка восстановления пароля в b2b стиле -->
                        <a href="javascript:void(0)" onclick="if(typeof showResetForm === 'function') showResetForm();" class="text-[9px] text-slate-600 hover:text-purple-400 font-bold uppercase tracking-wider transition-colors">
                            Забыли пароль?
                        </a>
                    </div>
                    <div class="relative">
                        <input type="password" id="auth-pass" required autocomplete="current-password" placeholder="••••••••" 
                            class="w-full bg-slate-950/60 border border-slate-900 focus:border-purple-500/50 rounded-xl px-4 py-3.5 text-sm text-slate-100 placeholder-slate-700 outline-none transition-all duration-150">
                    </div>
                </div>

                <!-- Главная управляющая кнопка входа -->
                <div class="pt-2">
                    <button type="button" onclick="handleLogin(this)" class="w-full py-4 text-xs font-black text-white uppercase tracking-widest bg-gradient-to-r from-purple-600 to-pink-600 border border-purple-500/20 rounded-xl shadow-[0_4px_20px_rgba(168,85,247,0.15)] hover:scale-[1.01] active:scale-[0.99] transition-all duration-150 cursor-pointer">
                        Авторизоваться
                    </button>
                </div>
            </form>

            <!-- Блок переключения на форму быстрой регистрации -->
            <div class="text-center">
                <p class="text-xs text-slate-500 font-medium">
                    Нет профиля? 
                    <button onclick="if(typeof showRegisterForm === 'function') { showRegisterForm(); } else if(typeof showRegister === 'function') { showRegister(); }" class="text-purple-400 hover:text-purple-300 font-bold uppercase tracking-wider ml-1 cursor-pointer transition-colors bg-transparent border-none p-0">
                        Создать новый аккаунт
                    </button>
                </p>
            </div>

            <!-- Разделитель для шлюзов сторонней авторизации -->
            <div class="relative flex py-2 items-center">
                <div class="flex-grow border-t border-slate-900"></div>
                <span class="flex-shrink mx-4 text-[9px] font-black text-slate-600 uppercase tracking-widest">или вход через партнеров</span>
                <div class="flex-grow border-t border-slate-900"></div>
            </div>

            <div class="space-y-3">
                <!-- Контейнер бесшовного входа VK OneTap -->
                <div id="VkIdSdkOneTap" class="w-full min-h-[44px] bg-slate-950/20 rounded-xl border border-slate-900/40 overflow-hidden"></div>
                
                <!-- 🎯 СКАЛЛА-ФИКС ЯНДЕКСА: Возвращаем каноничный ID, который ищет твой скрипт initSkullaYandexSuggest! -->
                <div id="yandex-auth-container" class="w-full min-h-[44px] bg-slate-950/20 rounded-xl border border-slate-900/40 overflow-hidden"></div>
            </div>

            <!-- === СИСТЕМНЫЙ B2B-ФУТЕР АВТОРИЗАЦИИ SKULLA === -->
            <div class="pt-5 border-t border-slate-900 text-center space-y-3">
                <p class="text-[10px] text-slate-600 font-medium tracking-wide uppercase leading-normal">
                    Авторизация подтверждает согласие с регламентами платформы
                </p>
                
                <!-- Симметричная сетка правовых ссылок с неоновым откликом -->
                <div class="flex items-center justify-center gap-4 text-[10px] font-black uppercase tracking-widest text-slate-500">
                    <a href="javascript:void(0)" onclick="if(typeof openLegal === 'function') openLegal('privacy')" class="hover:text-purple-400 hover:drop-shadow-[0_0_8px_rgba(168,85,247,0.4)] transition-all duration-150 flex items-center gap-1.5">
                        🔒 Конфиденциальность
                    </a>
                    <span class="text-slate-900 font-normal">|</span>
                    <a href="javascript:void(0)" onclick="if(typeof openLegal === 'function') openLegal('terms')" class="hover:text-pink-400 hover:drop-shadow-[0_0_8px_rgba(236,72,153,0.4)] transition-all duration-150 flex items-center gap-1.5">
                        📄 Соглашение
                    </a>
                </div>
            </div>

        </div>
    `;

    // Инжектируем собранный каркас в DOM-дерево
    container.innerHTML = html;

    // Включаем безопасную отложенную инициализацию внешних SDK шлюзов
    // Безопасная отложенная инициализация внешних шлюзов
    setTimeout(() => {
        try {
            // Если в твоем проекте функция называется просто initYandex — подправь имя тут:
            window.initSkullaYandexSuggest();
            window.initSkullaVkOneTap();
        } catch (e) {
            console.warn("⚠️ [SKULLA YANDEX SDK]: Ошибка рендеринга виджета:", e);
        }

    }, 50);


    // Подгружаем языковые константы, если модуль локализации активен в рантайме
    if (window.i18n && typeof i18n.apply === 'function') {
        i18n.apply();
    }
}
// --- ЭКРАН: ВХОД ---
function showLoginForm2() {
    const container = document.getElementById('auth-content');
    container.innerHTML = `
        <h2 class="logo-neon text-2xl mb-6 uppercase" data-i18n="auth.t25">${i18n.t('auth.t25')}</h2>
        <div class="space-y-4">
            <input type="email" id="auth-email" placeholder="${i18n.t('auth.t26')}" class="auth-input">
            <input type="password" id="auth-pass" placeholder="${i18n.t('auth.t27')}" class="auth-input">
            
            <!-- Родная кнопка входа по паролю -->
            <button onclick="handleLogin()" data-i18n="auth.t3" class="w-full bg-cyan-600 hover:bg-cyan-500 text-slate-950 py-3 rounded-xl font-black uppercase text-[10px] tracking-widest transition-all shadow-[0_0_15px_rgba(6,182,212,0.15)]">
                ${i18n.t('auth.t3')}
            </button>

            <!-- Разделитель ИЛИ -->
            <div class="flex items-center my-3 select-none">
                <div class="flex-1 border-t border-slate-800/80"></div>
                <span class="px-3 text-[9px] font-black tracking-widest text-slate-600 uppercase">или войти через</span>
                <div class="flex-1 border-t border-slate-800/80"></div>
            </div>

            <div id="yandex-auth-container" class="w-full flex justify-center"></div>

            <div id="VkIdSdkOneTap" class="w-full flex justify-center"></div>


            <div class="flex justify-between text-[9px] font-bold uppercase tracking-tighter text-slate-500 pt-2">
                <button onclick="showRegisterForm()" data-i18n="auth.t4" class="hover:text-cyan-400 text-left">${i18n.t('auth.t4')}</button>
                <button onclick="showForgotForm()" data-i18n="auth.t5" class="hover:text-cyan-400 text-right">${i18n.t('auth.t5')}</button>
            </div>
        </div>
    `;

    // 🎯 ЗАПУСКАЕМ ИНИЦИАЛИЗАЦИЮ ЯНДЕКСА СРАЗУ ПОСЛЕ НАДУВАНИЯ HTML ФОРМЫ!
    setTimeout(() => {
        window.initSkullaYandexSuggest();
        window.initSkullaVkOneTap();
    }, 50);
}



// --- ЭКРАН: РЕГИСТРАЦИЯ ---
function showRegisterForm() {
    const container = document.getElementById('auth-content');
    if (!container) return console.error("❌ Не нашел auth-content!");

    const t = (key) => (window.i18n && typeof i18n.t === 'function' ? i18n.t(key) : key);

    container.innerHTML = `
        <h2 class="logo-neon text-2xl mb-6 uppercase">${t('auth.t28')}</h2>
        <div class="space-y-4">
            <!-- 🎯 ПРОВЕРЬ ЭТИ ID: -->
            <input type="email" id="reg-email" placeholder="${t('auth.t29')}" class="auth-input">
            <input type="password" id="reg-pass" placeholder="${t('auth.t30')}" class="auth-input">
            
            <button onclick="handleRegister(this)" class="w-full bg-purple-600 hover:bg-purple-500 text-white py-3 rounded-xl font-black uppercase text-[10px] tracking-widest transition-all">
                ${t('auth.t6')}
            </button>
            
            <button onclick="showLoginForm()" class="w-full text-[9px] text-slate-500 font-bold uppercase tracking-widest mt-4">
                ${t('auth.t7')}
            </button>
        </div>
    `;
    console.log("✅ Форма регистрации отрисована с ID: reg-email, reg-pass");
}


// --- ЭКРАН: ВОССТАНОВЛЕНИЕ ---
function showForgotForm() {
    const container = document.getElementById('auth-content');
    container.innerHTML = `
        <h2 class="logo-neon text-2xl mb-6 uppercase" data-i18n="auth.t31">${i18n.t('auth.t31')}</h2>
        <div class="space-y-4">
            <input type="email" id="reset-email" placeholder="${i18n.t('auth.t26')}" class="auth-input">
            <button onclick="handleForgotRequest()" data-i18n="auth.t8" class="w-full bg-cyan-600 py-3 rounded-xl font-black uppercase text-[10px] tracking-widest transition-all">
                ${i18n.t('auth.t8')}
            </button>
            <button onclick="showLoginForm()" data-i18n="auth.t9" class="w-full text-[9px] text-slate-500 font-bold uppercase">
                ${i18n.t('auth.t9')}
            </button>
        </div>
    `;
}

function showResetForm(email) {
    const container = document.getElementById('auth-content');
    container.innerHTML = `
        <h2 class="logo-neon text-2xl mb-6 uppercase" data-i18n="auth.t32">${i18n.t('auth.t32')}</h2>
        <p class="text-[9px] text-slate-400 mb-6 uppercase tracking-widest leading-relaxed">
            <span data-i18n="auth.t10">${i18n.t('auth.t10')}</span> <br>
            <span class="text-cyan-400">${email}</span>
        </p>
        <div class="space-y-4">
            <input type="text" id="reset-code" placeholder="${i18n.t('auth.t33')}" 
                class="auth-input text-center font-black tracking-widest">
            <input type="password" id="new-password" placeholder="${i18n.t('auth.t34')}" 
                class="auth-input">
            <button onclick="handleResetPassword('${email}')" 
                    data-i18n="auth.t11" class="w-full bg-purple-600 hover:bg-purple-500 text-white py-3 rounded-xl font-black uppercase text-[10px] tracking-widest transition-all">
                ${i18n.t('auth.t11')}
            </button>
        </div>
    `;
}



async function handleForgotRequest() {
    const email = document.getElementById('reset-email').value;
    const formData = new FormData();
    formData.append('email', email);

    const response = await fetch('/api/auth/forgot_password', { method: 'POST', body: formData });
    if (response.ok) {
        showResetForm(email);
    }
}

async function handleResetPassword(email) {
    const code = document.getElementById('reset-code').value;
    const pass = document.getElementById('new-password').value;
    
    const formData = new FormData();
    formData.append('email', email);
    formData.append('code', code);
    formData.append('new_password', pass);

    const response = await fetch('/api/auth/reset_password', { method: 'POST', body: formData });
    if (response.ok) {
        alert(i18n.t('auth.t35')); // Пароль изменен
        showLoginForm();
    } else {
        alert(i18n.t('auth.t36')); // Неверный код
    }
}

async function updatePassword() {
    const p1 = document.getElementById('new-pass');
    const p2 = document.getElementById('confirm-pass');

    if (!validateAuth(['new-pass', 'confirm-pass'])) return;

    if (p1.value !== p2.value) {
        showError(p2, i18n.t('auth.t37')); // Пароли не совпадают
        return;
    }

    const formData = new FormData();
    // Берем email текущего авторизованного бро
    formData.append('email', window.user.email); 
    formData.append('new_password', p1.value);

    try {
        const response = await fetch('/api/auth/update_password', { method: 'POST', body: formData });
        if (response.ok) {
            alert(i18n.t('auth.t38')); // Успешно обновлен
            p1.value = ""; 
            p2.value = "";
        } else {
            const data = await response.json();
            alert(i18n.t('auth.t43') + (data.detail || "ERR")); // Ошибка: текст
        }
    } catch (e) {
        console.error("Update_Pass_Error:", e);
        alert(i18n.t('auth.t39')); // Ошибка связи
    }
}

function confirmDeleteAccount() {
    if (confirm(i18n.t('auth.t40'))) { // Внимание: удаление
        handleLogout();
        alert(i18n.t('auth.t41')); // Identity Deleted
    }
}

// =====================================================================
// 🧠 ОФИЦИАЛЬНЫЙ СКАЛЛА-ИНЖЕКТОР СТРОГО ПО ДОКУМЕНТАЦИИ ЯНДЕКСА
// =====================================================================

window.initSkullaYandexSuggest = function() {
    console.log("📡 [SKULLA OAUTH]: Запуск сканирования и подготовки YaAuthSuggest...");

    const renderYandexButton = () => {
        if (!window.YaAuthSuggest) {
            console.error("🚨 [SKULLA ERROR]: Объект YaAuthSuggest отсутствует в window!");
            return;
        }

        const currentOrigin = window.location.origin;

        // Инициализируем строго по доке со скриншота (строки 19-41)!
        // Инициализируем строго по официальной токен-структуре Яндекса
        window.YaAuthSuggest.init({
            client_id: "73bfd325031441eba8020ed41eccbbd0", // Твой ID приложения
            response_type: "token",                        // 🔥 ВРУБАЕМ РЕЖИМ ТОКЕНА ПО ДОКЕ С ЭКРАНА!
            redirect_uri: currentOrigin + "/api/auth/yandex/callback"
        },
        currentOrigin,
        {
            view: 'button',
            parentId: 'yandex-auth-container',
            buttonView: 'main',
            buttonTheme: 'dark',
            buttonSize: 'm',
            buttonBorderRadius: 12
        })
        .then(function(result) {
            return result.handler();
        })
        .then(function(data) {
            console.log("✅ [SKULLA OAUTH]: Токен от Яндекса получен:", data);
            
            const finalToken = data.access_token || data.code;

            if (finalToken) {
                console.log("📡 [SKULLA NET]: Отправляем токен на бэк в фоновом режиме...");

                // 2. 🎯 ШЕФ-ФИКС: Стучимся на бэк скрытым фоновым GET-запросом!
                fetch(`/api/auth/yandex/callback?token=${finalToken}`)
                .then(res => {
                    if (!res.ok) throw new Error("Бэкенд отклонил токен Яндекса");
                    return res.json(); // Бэк теперь вернет нам красивый JSON вместо редиректа!
                })
                .then(response => {
                    if (response && response.status === "success") {
                        console.log("🎉 [SKULLA AUTH]: Сессия создана! Плавно переходим в полноценный редактор.");
                        
                        // 3. ТРИУМФАЛЬНЫЙ ПЕРЕХОД: Главное окно само улетает в полноценный конструктор!
                        window.location.href = "/editor?style=skulla_seller_main_cover";
                    }
                })
                .catch(err => {
                    console.error("🚨 [SKULLA ERROR]: Ошибка фоновой авторизации:", err);
                    alert("Не удалось войти через Яндекс ID. Попробуйте еще раз.");
                    // Если сбой — тушим лоадер
                    if (typeof window.stopSkullaAiGenerationLoader === 'function') {
                        window.stopSkullaAiGenerationLoader();
                    }
                });
            }
        })

        .catch(function(error) {
            console.warn("⚠️ [SKULLA OAUTH]: Сбой инициализации или отмена юзером:", error);
        });
    };

    // Динамический хак загрузки: если скрипта еще нет на странице, качаем его сами
    if (!window.YaAuthSuggest) {
        console.log("🛠️ [SKULLA OAUTH]: Скрипт-суггест не найден. На лету качаем полифиллы...");
        
        const script = document.createElement('script');
        script.src = "https://yastatic.net";
        script.async = true;
        
        script.onload = () => {
            console.log("✅ [SKULLA OAUTH]: Скрипт Яндекса в памяти. Отрисовываю кнопку.");
            renderYandexButton();
        };
        
        document.head.appendChild(script);
    } else {
        // Если скрипт уже загружен, просто рендерим кнопку заново
        renderYandexButton();
    }
};

// =====================================================================
// 🍏 ГЛОБАЛЬНЫЙ СЛУШАТЕЛЬ ПАМЯТИ: Обновляет шапку Павла и СРАЗУ тушит модалку!
// =====================================================================
window.addEventListener('storage', function(event) {
    if (event.key === 'skulla_user' && event.newValue) {
        console.log("🏆 [MAIN WINDOW]: Память обновилась! Перерисовываем шапку Павла...");

        try {
            const userData = JSON.parse(event.newValue);
            window.user = userData;

            // 1. 🔥 ОБНОВЛЯЕМ ШАПКУ: Зажигаем имя RATANOVPAVEL, 9212 бонов и 919 скаллов!
            if (typeof syncHeader === 'function') syncHeader();
            if (typeof window.syncHeader === 'function') window.syncHeader();
            
            if (typeof checkSkullaActiveActions === 'function' && userData && userData.email) {
                console.log(`💥 [SKULLA STORAGE EVENT]: Сессия обновлена для ${userData.email}. Мгновенно запрашиваем акцию у Питона!`);
                // Запускаем асинхронный запрос к роуту /api/economy/check_active_action
                checkSkullaActiveActions(userData.email);
            }
            // 2. 🎯 СКАЛЛА-ФИКС: Нативно вызываем закрытие твоей модалки входа!
            if (typeof closeAuthModal === 'function') closeAuthModal();
            if (typeof toggleAuthModal === 'function') toggleAuthModal(false);

            // 3. 🦾 УЛЬТИМАТИВНЫЙ DOM-ХАК: Силой уничтожаем неоновое окно входа, если функции зависли!
            const modal = document.getElementById('authModal') || document.querySelector('.auth-modal') || document.getElementById('loginModal');
            if (modal) {
                modal.style.display = 'none';
                modal.classList.add('hidden');
                console.log("✅ Неоновая модалка авторизации стёрта из DOM!");
            }
            
            // Намертво вырезаем тёмную подложку (backdrop), чтобы полностью разблокировать экран сайта!
            document.querySelectorAll('.modal-backdrop, .modal-bg').forEach(el => el.remove());

            console.log("🏆 Триумф! Шапка зажглась, модалка закрыта. Селлер остался на текущей странице сайта!");
        } catch (e) {
            console.error("🚨 Ошибка разбора памяти на главном экране:", e);
        }
    }
});




// =====================================================================
// 🚀 КРИПТОГРАФИЧЕСКИЙ PKCE-ГЕНЕРАТОР ДЛЯ СХЕМЫ ВК ID OAUTH 2.1
// =====================================================================
function generateRandomString(length) {
    const charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
    let result = '';
    const values = new Uint32Array(length);
    window.crypto.getRandomValues(values);
    for (let i = 0; i < length; i++) {
        result += charset[values[i] % charset.length];
    }
    return result;
}

// =====================================================================
// 🚀 КРИПТОГРАФИЧЕСКИЙ PKCE-ГЕНЕРАТОР ДЛЯ СХЕМЫ ВК ID OAUTH 2.1
// =====================================================================
function generateRandomString(length) {
    const charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
    let result = '';
    const values = new Uint32Array(length);
    window.crypto.getRandomValues(values);
    for (let i = 0; i < length; i++) {
        result += charset[values[i] % charset.length];
    }
    return result;
}

async function generateCodeChallenge(verifier) {
    const encoder = new TextEncoder();
    const data = encoder.encode(verifier);
    const digest = await window.crypto.subtle.digest('SHA-256', data);
    return btoa(String.fromCharCode(...new Uint8Array(digest)))
        .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

// =====================================================================
// 📡 ГЛАВНАЯ ИНИЦИАЛИЗАЦИЯ ИМЕННОЙ КНОПКИ ВК С ПРЯМОЙ PKCE-ГЕНЕРАЦИЕЙ
// =====================================================================
window.initSkullaVkOneTap = async function() {
    console.log("📡 [SKULLA OAUTH]: Сборка PKCE-контекста по схеме ВК...");

    const container = document.getElementById('VkIdSdkOneTap');
    if (!container) return;
    container.innerHTML = '';

    const REAL_VK_APP_ID = 54683991; 

    // 1. 🔥 ГЕНЕРИРУЕМ ВЕРИФИКАТОР СТРОГО ПО СХЕМЕ ВК!
    const codeVerifier = generateRandomString(64);
    const codeChallenge = await generateCodeChallenge(codeVerifier);
    
    // Прячем чистый верификатор в сессию браузера, чтобы вытащить его при колбэке
    sessionStorage.setItem('skulla_vk_verifier', codeVerifier);

    // 2. Инициализируем конфигурацию строго под JSON-обмен схемы
    window.VKIDSDK.Config.init({
        app: REAL_VK_APP_ID, 
        redirectUrl: window.location.origin + '/api/auth/vk/callback',
        responseMode: window.VKIDSDK.ConfigResponseMode.Callback,
        scope: 'email',
        // 🎯 СКАЛЛА-ФИКС: Скармливаем хэш-challenge шлюзу ВК, как нарисовано на схеме!
        codeChallenge: codeChallenge,
        codeChallengeMethod: 'S256'
    });

    const oneTap = new window.VKIDSDK.OneTap();

    // 3. Подписка на триумфальный вход Павла
    oneTap.on(window.VKIDSDK.OneTapInternalEvents.LOGIN_SUCCESS, function(payload) {
        console.log("✅ [SKULLA OAUTH]: ВК вернул код авторизации!", payload);
        
        const finalCode = payload.code;
        const deviceId = payload.device_id; 
        
        // Вытаскиваем сохраненный верификатор обратно из памяти сессии
        const savedVerifier = sessionStorage.getItem('skulla_vk_verifier');

        if (finalCode && deviceId && savedVerifier) {
            // 🚀 СТРОКА СХЕМЫ: Отправляем ВСЕ ТРИ параметра на бэкенд FastAPI!
            window.location.href = `/api/auth/vk/callback?code=${finalCode}&device_id=${deviceId}&code_verifier=${savedVerifier}`;
        } else {
            console.error("🚨 [SKULLA ERROR]: Потеряны PKCE ключи сессии!", payload);
        }
    });

    // 4. Отрендериваем именную синюю кнопку со значком ВК во фрейме
    oneTap.render({
        container: container,
        styles: { borderRadius: 8, theme: 'dark', height: 44 }
    });
};

async function checkSkullaActiveActions(forcedEmail = null) {
    
    // Если email передан аргументом — берем его, иначе нативно читаем из window или localStorage
    let email = forcedEmail;
    
    if (!email && window.user && window.user.email) {
        email = window.user.email;
    }
    
    if (!email) {
        try {
            const saved = localStorage.getItem('skulla_user');
            if (saved) {
                const parsed = JSON.parse(saved);
                if (parsed && parsed.email) email = parsed.email;
            }
        } catch (e) { email = null; }
    }

    // 🔥 БРОНИРОВАННЫЙ КОРДОН: Выходим, только если email вообще нигде физически нет!
    if (!email) {
        console.warn("⚠️ [SKULLA ACTION]: Проверка отменена, email пользователя не найден в системе.");
        return;
    }

    try {
        const fd = new FormData();
        // Засовываем в пакет наш гарантированно найденный email
        fd.append('email', email);

        // 1. Стучимся в Питон за проверкой акций
        const response = await fetch('/api/economy/check_active_action', { method: 'POST', body: fd });
        if (!response.ok) return;
        
        const config = await response.json();
        
        // Если Питон сказал "show_popup: false" — селлер уже все прошел, улетаем
        if (!config || !config.show_popup) return;

        console.log("🔥 [SKULLA ACTION]: Найдена активная акция платформы! Рендерим неоновое окно...");

        // 2. Силой уничтожаем старые дубликаты окон акций, если они зависли
        const oldPopup = document.getElementById('skulla-action-popup');
        if (oldPopup) oldPopup.remove();

        // 3. СОЗДАЕМ КРУТОЕ НЕОНОВОЕ ОКНО В СТИЛЕ SKULLA И ТВОИХ КЛАССОВ TAILWIND!
        const popupHtml = `
            <div id="skulla-action-popup" class="fixed inset-0 z-[150] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
                <div class="w-full max-w-md p-6 bg-slate-900 border-2 border-purple-500 rounded-2xl shadow-[0_0_25px_rgba(168,85,247,0.4)] text-center animate-fade-in animate-duration-200">
                    
                    <!-- Неоновый заголовок -->
                    <h2 class="text-xl font-black text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-500 tracking-wider uppercase mb-4">
                        ${config.title}
                    </h2>
                    
                    <!-- Контент предложения Питона -->
                    <div class="text-sm text-slate-300 font-medium leading-relaxed text-left bg-slate-950 p-4 border border-slate-800 rounded-xl mb-6">
                        ${config.text}
                    </div>

                    <!-- Кнопки решения селлера -->
                    <div class="flex flex-col gap-3">
                        <button id="skulla-action-btn-accept" class="w-full py-3 px-4 font-bold text-white uppercase tracking-wider bg-gradient-to-r from-purple-600 to-pink-600 border border-purple-400 rounded-xl shadow-[0_0_15px_rgba(168,85,247,0.3)] hover:scale-[1.02] active:scale-[0.98] transition-all duration-150">
                            ${config.btn_accept}
                        </button>
                        
                        <button id="skulla-action-btn-decline" class="w-full py-2 px-4 font-bold text-slate-400 text-xs uppercase hover:text-slate-200 transition-colors duration-150">
                            ${config.btn_decline}
                        </button>
                    </div>

                </div>
            </div>
        `;

        // Вживляем собранное неоновое окно прямо в корень страницы!
        document.body.insertAdjacentHTML('beforeend', popupHtml);

        // 4. ПОДПИСЫВАЕМСЯ НА НАЖАТИЯ КНОПОК РЕШЕНИЯ СЕЛЛЕРА
        document.getElementById('skulla-action-btn-accept').onclick = () => submitSkullaAction(config.action_key, 'accepted');
        document.getElementById('skulla-action-btn-decline').onclick = () => submitSkullaAction(config.action_key, 'declined');

    } catch (err) {
        console.error("🚨 Ошибка рендеринга умного поп-апа акций:", err);
    }
}

async function submitSkullaAction(actionKey, decision) {
    console.log(`📡 [SKULLA ACTION]: Селлер выбрал решение -> ${decision}. Отправляем в базу...`);
    
    try {
        const fd = new FormData();
        fd.append('email', window.user.email);
        fd.append('action_key', actionKey);
        fd.append('decision', decision);

        const response = await fetch('/api/economy/submit_action_decision', { method: 'POST', body: fd });
        const data = await response.json();

        if (response.ok && data.status === 'success') {
            console.log("🍏 [SKULLA ACTION SUCCESS]: Решение запечатано базой Питона!", data);

            // Если боны были начислены, пулей скармливаем их твоему родному методу из header.js!
            // Баланс +10 000 костей взлетит в правом углу прямо на твоих глазах без всяких ребутов!
            if (typeof updateUser === 'function') {
                updateUser({ bones: data.bones, skulls: data.skulls });
            }

            // Нативно обновляем стейт в памяти Хрома
            window.user.bones = data.bones;
            window.user.skulls = data.skulls;
            localStorage.setItem('skulla_user', JSON.stringify(window.user));
        }
    } catch (err) {
        console.error("🚨 Сбой отправки решения акции:", err);
    } finally {
        // В финале в любом случае бесшовно стираем поп-ап офера с экрана!
        const popup = document.getElementById('skulla-action-popup');
        if (popup) popup.remove();
    }
}

// =====================================================================
// 🍏 КОНЦЕПЦИЯ ВХОДА: ЖЕСТКИЙ ФРОНТЕНД-КОРДОН SKULLA
// =====================================================================
document.addEventListener('DOMContentLoaded', function() {
    // 1. Проверяем стейт авторизации селлера в LocalStorage
    const savedUser = localStorage.getItem('skulla_user');
    let isLoggedIn = false;

    if (savedUser && savedUser !== "undefined") {
        try {
            const parsed = JSON.parse(savedUser);
            if (parsed && parsed.isLoggedIn) isLoggedIn = true;
        } catch (e) { isLoggedIn = false; }
    }

    // 2. 🎯 ГЛАВНЫЙ СНАЙПЕРСКИЙ ПЕРЕКЛЮЧАТЕЛЬ!
    if (!isLoggedIn) {
        console.log("🔒 [SKULLA ACCESS]: селлер не авторизован. Проверяем маркеры входа...");

        // 🔥 ШЛЮЗ-ФИКС ДЛЯ МОДАЛКИ: Проверяем, прилетел ли селлер с лендинга авторизоваться
        const isLoginIntent = window.location.hash === '#login' || window.location.search.includes('login');
        const landingPage = document.getElementById('skulla-landing-page');
        const appContainer = document.getElementById('app-container') || document.querySelector('.main-app');

        if (isLoginIntent) {
            console.log("📡 [SKULLA AUTH RUNTIME]: Обнаружен флаг входа. Активируем модалку, платформу не гасим!");
            
            // Включаем размытие заднего фона в стиле Skulla, чтобы скрыть конструктор, но оставить модалку рабочей
            if (appContainer) {
                appContainer.style.display = 'block';
                appContainer.style.pointerEvents = 'none';
                appContainer.style.filter = 'blur(5px)';
            }

            // Нативно и силой взрываем твое окно авторизации со сканера ID!
            const modal = document.getElementById('auth-modal');
            if (modal) {
                modal.style.display = 'flex';
                modal.classList.remove('hidden');
                showLoginForm();
                console.log("💥 [SKULLA DOM]: Боевая модалка auth-modal успешно выведена на экран!");
            }
            if (landingPage) landingPage.style.display = 'none';

        } else {
            // СТАНДАРТНЫЙ КЕЙС: Если флагов входа нет — жестко разворачиваем изолированный лендинг
            console.log("🔒 Разворачиваем неоновый лендинг...");
            if (landingPage) {
                landingPage.classList.remove('hidden');
                landingPage.style.display = 'block';
                landingPage.style.position = 'fixed';
                landingPage.style.inset = '0';
                landingPage.style.backgroundColor = '#030712';
                landingPage.style.zIndex = '50';
                if (typeof initLandingScrollAnimations === 'function') initLandingScrollAnimations();
            }
            if (appContainer) appContainer.style.display = 'none';
        }
        
    } else {
        console.log("🍏 [SKULLA]: Селлер авторизован. Доступ к конструктору открыт!");
        const appContainer = document.getElementById('app-container') || document.querySelector('.main-app');
        if (appContainer) {
            appContainer.style.display = 'block';
            appContainer.style.pointerEvents = 'auto';
            appContainer.style.filter = 'none';
        }
        const landingPage = document.getElementById('skulla-landing-page');
        if (landingPage) landingPage.remove();
    }
});

// =====================================================================
// 🍏 КОРДОН БЕЗОПАСНОСТИ SKULLA: Динамический контроль доступа
// =====================================================================
function checkSkullaAccessBorder() {
    const savedUser = localStorage.getItem('skulla_user');
    let isLoggedIn = false;

    if (savedUser && savedUser !== "undefined") {
        try {
            const parsed = JSON.parse(savedUser);
            if (parsed && parsed.isLoggedIn) isLoggedIn = true;
        } catch (e) { isLoggedIn = false; }
    }

    const isLoginIntent = window.location.hash === '#login' || window.location.search.includes('login');
    const landingPage = document.getElementById('skulla-landing-page');
    const appContainer = document.getElementById('app-container') || document.querySelector('.main-app');
    const modal = document.getElementById('auth-modal');

    // ❌ СЦЕНАРИЙ А: Селлер НЕ авторизован
    if (!isLoggedIn) {
        console.log("🔒 [SKULLA ACCESS]: Селлер не авторизован! Активируем кордон...");

        if (isLoginIntent) {
            // Включаем размытие платформы для ввода пароля
            if (appContainer) {
                appContainer.style.display = 'block';
                appContainer.style.pointerEvents = 'none';
                appContainer.style.filter = 'blur(5px)';
            }
            if (modal) {
                modal.style.display = 'flex';
                modal.classList.remove('hidden');
            }
            if (landingPage) landingPage.style.display = 'none';
        } else {
            // Разворачиваем изолированный b2b-лендинг
            if (landingPage) {
                landingPage.classList.remove('hidden');
                landingPage.style.display = 'block';
                landingPage.style.position = 'fixed';
                landingPage.style.inset = '0';
                landingPage.style.backgroundColor = '#030712';
                landingPage.style.zIndex = '50';
                if (typeof initLandingScrollAnimations === 'function') initLandingScrollAnimations();
            }
            if (appContainer) appContainer.style.display = 'none';
        }
    } 
    // 🍏 СЦЕНАРИЙ Б: Селлер ПОЛНОСТЬЮ авторизован (Снимаем все блокировки!)
    else {
        console.log("🍏 [SKULLA ACCESS]: Доступ одобрен! Нативно сносим любые блокировки интерфейса.");
        
        // 🦾 УЛЬТИМАТИВНЫЙ ФИКС: Снимаем размытие, включаем клики по кнопкам ЛК и подвала!
        if (appContainer) {
            appContainer.style.display = 'block';
            appContainer.style.pointerEvents = 'auto'; // Разрешаем тапы по сайту!
            appContainer.style.filter = 'none';         // Выключаем размытие!
        }
        
        // Сносим гостевой лендинг из памяти Хрома
        if (landingPage) landingPage.remove();
    }
}

// Автоматически запускаем проверку кордона при первой загрузке страницы
document.addEventListener('DOMContentLoaded', checkSkullaAccessBorder);
