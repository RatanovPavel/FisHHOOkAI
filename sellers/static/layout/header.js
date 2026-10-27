// header.js
// 1. Инициализация объекта
window.user = JSON.parse(localStorage.getItem('skulla_user')) || {
    isLoggedIn: false,
    email: '',
    bones: 0,
    skulls: 0,
    is_verified: false
};

// 2. Функция СИНХРОНИЗАЦИИ (Отрисовка данных на экране)
function syncHeader() {
    const balanceDisplay = document.getElementById('token-balance-display');
    const bonesCount = document.getElementById('user-bones-count');
    const skullsCount = document.getElementById('user-skulls-count');
    const userLabel = document.getElementById('header-user-label');

    // ПРОВЕРКА: Юзер в системе?
    const isLoggedIn = window.user && window.user.isLoggedIn && window.user.email;

    if (isLoggedIn) {
        // --- РЕЖИМ ЮЗЕРА ---
        if (balanceDisplay) {
            balanceDisplay.classList.remove('hidden');
            balanceDisplay.style.display = 'flex'; 
        }
        if (bonesCount) bonesCount.innerText = window.user.bones || 0;
        if (skullsCount) skullsCount.innerText = window.user.skulls || 0;

        if (userLabel) {
            const emailStr = String(window.user.email);
            const namePart = emailStr.split('@')[0];
            userLabel.innerText = namePart.toUpperCase();
            userLabel.classList.remove('text-slate-500');
            userLabel.classList.add('text-white');
            
            // 🎯 УДАЛЯЕМ атрибут, чтобы i18n не затирал имя при смене языка
            userLabel.removeAttribute('data-i18n');
        }
    } else {
        // --- РЕЖИМ ГОСТЯ ---
        if (balanceDisplay) {
            balanceDisplay.classList.add('hidden');
            balanceDisplay.style.display = 'none';
        }
        if (userLabel) {
            userLabel.classList.add('text-slate-500');
            userLabel.classList.remove('text-white');
            
            // 🎯 ВОЗВРАЩАЕМ атрибут, чтобы i18n мог переводить слово "Авторизация"
            userLabel.setAttribute('data-i18n', 'index.t1');
            
            // Запускаем разовый перевод, если i18n уже готов
            if (window.i18n && typeof i18n.t === 'function') {
                userLabel.innerText = i18n.t('index.t1');
            }
        }
    }
}


// 🎯 ГЛАВНЫЙ ХАК: Перехватываем работу i18n
// Когда i18n меняет язык, он затирает имя. Мы сразу возвращаем его на место.
const originalI18nApply = window.i18n ? window.i18n.apply : null;
if (window.i18n) {
    window.i18n.apply = function() {
        // 1. Сначала даем i18n сделать свою работу
        if (originalI18nApply) originalI18nApply.call(window.i18n);
        // 2. Сразу после этого возвращаем имя юзера
        syncHeader();
    };
}


// 3. Функция ОБНОВЛЕНИЯ
function updateUser(newData) {
    window.user = { ...window.user, ...newData };
    localStorage.setItem('skulla_user', JSON.stringify(window.user));
    syncHeader(); 
}

// 4. Функция ПРОВЕРКИ БОНУСА
async function checkDailyBones() {
    if (!window.user || !window.user.isLoggedIn || !window.user.email) return;
    const fd = new FormData();
    fd.append("email", window.user.email);
    try {
        const resp = await fetch('/api/economy/check_daily', { method: 'POST', body: fd });
        const data = await resp.json();
        if (data.status === "success") {
            updateUser({ bones: data.bones, skulls: data.skulls });
        }
    } catch (e) { console.error("❌ [ECONOMY]:", e); }
}

// 5. ИНИЦИАЦИЯ ПРИ ЗАГРУЗКЕ
function initHeader() {
    const savedData = localStorage.getItem('skulla_user');
    if (savedData && savedData !== "undefined") {
        try { window.user = JSON.parse(savedData); } 
        catch (e) { localStorage.removeItem('skulla_user'); }
    }
    syncHeader();
    //checkDailyBones();

    if (window.user && window.user.isLoggedIn && typeof checkSkullaActiveActions === 'function') {
        checkSkullaActiveActions();
    }
}

document.addEventListener('DOMContentLoaded', initHeader);
