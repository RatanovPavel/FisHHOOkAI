
window.favorites = JSON.parse(localStorage.getItem('fav_effects') || '[]');
window.fullData = null;

async function loadCatalog() {
    // Находим контейнер ПРЯМО ПЕРЕД использованием
    const catalogContainer = document.getElementById('catalog-container');
    if (!catalogContainer) return;

    try {
        console.log("📡 [SYSTEM]: Запрос к ядру /api/catalog...");
        const resp = await fetch('/api/catalog');
        window.fullData = await resp.json();
        
        console.log("📦 [SYSTEM]: Данные получены, начинаю рендер...");
        renderCatalog();
        if (typeof renderFilterChips === 'function') renderFilterChips();
    } catch (e) { 
        console.error("💀 [SYSTEM_ERROR]:", e);
        catalogContainer.innerHTML = `<div class="text-center py-20 text-slate-800 uppercase font-black text-[10px]">Ошибка связи с ядром.</div>`; 
    }
}

// БЕЗОПАСНЫЙ ЗАПУСК (Ждем, пока HTML прогрузится)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadCatalog);
} else {
    loadCatalog();
}


window.renderCatalog = function() {
    const catalogContainer = document.getElementById('catalog-container');
    if (!window.fullData || !catalogContainer) return;

    window.favorites = JSON.parse(localStorage.getItem('fav_effects') || '[]');
    
    catalogContainer.innerHTML = "";
    const { groups, effects } = window.fullData;

    groups.forEach(group => {
        let groupEffects = (group.id === 'favorites') 
            ? effects.filter(e => window.favorites.includes(e.id))
            : effects.filter(e => e.groups && e.groups.includes(group.id));

        if (groupEffects.length === 0) return;

        let translatedTitle = group.title;
        if (window.i18n && typeof window.i18n.t === 'function') {
            if (group.id === 'favorites') {
                translatedTitle = window.i18n.t('groups.favorites');
            } else {
                // 🎯 АБСОЛЮТНЫЙ ИИ-ВЗЛОМ ШЕФА: Стучимся в локализацию напрямую по ID группы (style_neon_cyberpunk)!
                // Это на 100% находит строку "💥 НЕОН / КИБЕРПАНК" в JSON и полностью игнорирует косяки бэкенда с точками! [INDEX]
                translatedTitle = window.i18n.t(`groups.${group.id}`) || group.title;
            }
        }


        const section = document.createElement('div');
        section.className = 'group-section relative mb-16 px-4 animate-fadeIn';
        section.innerHTML = `
            <div class="flex justify-between items-end mb-6">
                <h2 class="text-cyan-400 text-[11px] font-black uppercase tracking-[0.4em]">${translatedTitle}</h2>
                <button onclick="window.showGroupDetailed('${group.id}')" 
                        class="text-[9px] text-slate-600 hover:text-cyan-500 font-bold uppercase tracking-widest transition-all">
                    ${window.i18n ? window.i18n.t("carousel.t1") : "VIEW ALL"}
                </button>
            </div>
            
            <!-- 🎯 ДОБАВЛЕНА ОБЕРТКА ДЛЯ КНОПОК И ГРИДА -->
            <div class="relative group/carousel">
                <!-- Левая кнопка -->
                <button onclick="scrollGrid('${group.id}', -1)"
                        class="carousel-nav-btn btn-left absolute left-[-25px] top-1/2 -translate-y-1/2 z-50 transition-all select-none">
                    ‹
                </button>


                <!-- Контейнер скролла -->
                <div id="grid-${group.id}" 
                     class="carousel-container overflow-x-auto scrollbar-hide flex gap-6 scroll-smooth"
                     onscroll="updateArrows('${group.id}')">
                    ${groupEffects.map(eff => createCard(eff, 'carousel-item')).join('')}
                </div>

                <!-- Правая кнопка -->
                <button onclick="scrollGrid('${group.id}', 1)"
                        class="carousel-nav-btn btn-right absolute right-[-25px] top-1/2 -translate-y-1/2 z-50 transition-all select-none">
                    ›
                </button>

            </div>
        `;
        catalogContainer.appendChild(section);
        
        // 🎯 АБСОЛЮТНЫЙ ФИКС ШЕФА: Исправили синтаксис скобок и дали Хрому время на рендеринг!
        // Теперь стрелочки перемотки загорятся СРАЗУ при загрузке страницы, если карусель не влазит в экран!
        setTimeout(() => {
            if (typeof updateArrows === 'function') {
                updateArrows(group.id);
            }
        }, 300);

    });
};




window.createCard = function(eff, extraClass = "") {
    const isFav = favorites.includes(eff.id);
    const starColor = isFav ? 'text-yellow-400' : 'text-slate-700 hover:text-slate-300';
    const displayUsages = eff.usages || 0;
    const lang = localStorage.getItem('lang') || 'ru';
    const local = eff.i18n ? eff.i18n[lang] : null;
    
    const title = local && local.title ? local.title : eff.title;
    const desc = local && local.desc ? local.desc : eff.desc;
    const labelApplied = local && local.applied ? local.applied : (lang === 'en' ? 'APPLIED:' : 'ПРИМЕНЕН:');

    return `
        <div class="effect-card ${extraClass} group relative bg-slate-900/90 border border-slate-800 rounded-[2.5rem] p-8 transition-all duration-500 hover:border-cyan-500/30 hover:bg-slate-800/90 shadow-2xl flex flex-col" 
             style="height: 350px; min-height: 350px; box-sizing: border-box;" draggable="false">
            
            <!-- 1. Иконка и Звезда (Абсолют) -->
            <div class="absolute top-8 left-8 text-5xl transform transition-all duration-700 group-hover:scale-110 pointer-events-none z-20">
                ${eff.icon}
            </div>

            <button onclick="toggleFav('${eff.id}', event)" 
                    class="absolute top-8 right-8 z-50 transition-all duration-300 ${starColor} outline-none border-none bg-transparent cursor-pointer text-xl opacity-80 hover:opacity-100">
                ★
            </button>

            <!-- 2. Основная ссылка - ТЕПЕРЬ ОНА РАСТЯНУТА (flex-grow) -->
            <a href="/editor?style=${eff.id}" target="_blank" 
               class="flex flex-col flex-grow no-underline w-full" draggable="false">
                
                <!-- Блок текста (Центрируется в оставшемся пространстве) -->
                <div class="flex-grow flex flex-col items-center justify-center text-center mt-12">
                    <h3 class="text-xl font-bold mb-2 tracking-tight text-white group-hover:text-cyan-400 transition-colors uppercase italic leading-tight">
                        ${title}
                    </h3>
                    
                    <p class="text-slate-400 text-[10px] font-medium uppercase tracking-widest leading-relaxed opacity-80 group-hover:opacity-100 px-2 whitespace-normal break-words">
                        ${desc}
                    </p>
                </div>
            </a>
        </div>
    `;
};







        function scrollGrid(groupId, direction) {
            const grid = document.getElementById(`grid-${groupId}`);
            if (!grid) return;
            const scrollAmount = 304; 
            grid.scrollBy({ left: direction * scrollAmount, behavior: 'smooth' });
        }

        function updateArrows(groupId) {
            const grid = document.getElementById(`grid-${groupId}`);
            if (!grid) return;
            const leftBtn = grid.parentElement.querySelector('.btn-left');
            const rightBtn = grid.parentElement.querySelector('.btn-right');
            if (!leftBtn || !rightBtn) return;
            
            grid.scrollLeft > 10 ? leftBtn.classList.remove('nav-hidden') : leftBtn.classList.add('nav-hidden');
            const isAtEnd = grid.scrollLeft + grid.clientWidth >= grid.scrollWidth - 15;
            isAtEnd ? rightBtn.classList.add('nav-hidden') : rightBtn.classList.remove('nav-hidden');
        }

function toggleFav(id, e) {
    // 1. Блокируем прыжки и срабатывание клика по самой карточке
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // 2. Логика localStorage
    let currentFavs = JSON.parse(localStorage.getItem('fav_effects') || '[]');
    const index = currentFavs.indexOf(id);
    
    if (index > -1) {
        currentFavs.splice(index, 1);
    } else {
        currentFavs.push(id);
    }
    
    // Обновляем глобальную переменную и память
    window.favorites = currentFavs; 
    localStorage.setItem('fav_effects', JSON.stringify(currentFavs));

    // 3. ТОЧЕЧНОЕ ОБНОВЛЕНИЕ ЦВЕТА (Исправленный поиск)
    const isNowFav = currentFavs.includes(id);
    
    // Ищем все кнопки, у которых в onclick есть этот ID
    const allButtons = document.querySelectorAll('button');
    allButtons.forEach(btn => {
        const onclickAttr = btn.getAttribute('onclick') || '';
        if (onclickAttr.includes(`toggleFav('${id}'`) || onclickAttr.includes(`toggleFav("${id}"`)) {
            if (isNowFav) {
                btn.classList.add('text-yellow-400', 'opacity-100');
                btn.classList.remove('text-slate-500', 'opacity-80');
            } else {
                btn.classList.remove('text-yellow-400', 'opacity-100');
                btn.classList.add('text-slate-500', 'opacity-80');
            }
        }
    });

    console.log(`⭐ [FAV]: ${id} теперь ${isNowFav ? 'в избранном' : 'удален'}`);
}


        window.addEventListener('resize', () => {
            if (fullData) fullData.groups.forEach(g => updateArrows(g.id));
        });

window.showGroupDetailed = function(groupId) {
    window.lastOpenedCategory = groupId;
    const catalogContainer = document.getElementById('catalog-container');
    if (!window.fullData || !catalogContainer) return;

    const { groups, effects } = window.fullData;
    const group = groups.find(g => g.id === groupId);
    
    // 1. ОПРЕДЕЛЯЕМ ЯЗЫК И АБСОЛЮТНО АВТОНОМНО ПЕРЕВОДИМ ЗАГОЛОВОК ОТ ШЕФА
    const lang = localStorage.getItem('lang') || 'ru';
    let translatedTitle = groupId; // Фолбек на сырой ID, если всё упадет

    if (window.i18n && typeof window.i18n.t === 'function') {
        if (groupId === 'favorites') {
            translatedTitle = window.i18n.t('groups.favorites');
        } else {
            // 🎯 СНАЙПЕРСКИЙ ИИ-ПЕРЕХВАТ ШЕФА: Стучимся напрямую в JSON локализации по ID группы!
            // Это полностью игнорирует косяки groups.find и выведет "💥 НЕОН / КИБЕРПАНК" в любой ситуации!
            translatedTitle = window.i18n.t(`groups.${groupId}`) || (group ? group.title : groupId);
        }
    } else if (group) {
        translatedTitle = group.title;
    }

    // Если группа не нашлась в массиве, мы всё равно НЕ ПАДАЕМ, а даём коду отрендерить сетку карточек!
    // Фильтр отработает по массиву e.groups, который мы уже инжектировали на бэкенде!



    // Текст для кнопки "Назад"
    const backText = (window.i18n) ? i18n.t("carousel.t3") : (lang === 'en' ? "Back" : "Назад");

    let filtered = [];
    if (groupId === 'favorites') {
        filtered = effects.filter(e => window.favorites.includes(e.id));
    } else {
        filtered = effects.filter(e => e.groups && e.groups.includes(groupId));
    }

    // 2. РИСУЕМ СЕТКУ
    catalogContainer.innerHTML = `
        <div class="detailed-view-marker hidden"></div>
        <div class="max-w-6xl mx-auto px-4 mb-16 animate-fadeIn">
            <!-- 🎯 Добавили ID "detailed-start" для точного прицела -->
            <div id="detailed-start" class="flex items-center gap-6 mb-12">
                <button onclick="renderCatalog()" class="relative z-50 group flex items-center gap-2 text-cyan-500 hover:text-white transition-all text-[10px] font-black uppercase tracking-widest outline-none">
                    <span class="text-lg">←</span> ${backText}
                </button>
                <div class="h-px bg-slate-900/50 flex-grow"></div>
                <h2 class="text-slate-400 text-[11px] font-black uppercase tracking-[0.4em]">${translatedTitle}</h2>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-x-6 gap-y-12 justify-items-center">
                ${filtered.map(eff => `
                    <div class="w-full max-w-[304px]">
                        ${createCard(eff)}
                    </div>
                `).join('')}
            </div>
        </div>
    `;

    // 🎯 СКРОЛЛ С ОТСТУПОМ (чтобы шапка не прилипала к авторизации)
    setTimeout(() => {
        const target = document.getElementById('detailed-start');
        if (target) {
            // Вычисляем позицию элемента относительно верха страницы
            const elementPosition = target.getBoundingClientRect().top + window.pageYOffset;
            
            // Вычитаем отступ (например, 100px), чтобы оставить место под баланс и авторизацию
            const offsetPosition = elementPosition - 100;

            window.scrollTo({
                top: offsetPosition,
                behavior: 'smooth'
            });
        }
    }, 50); // Увеличил задержку до 50мс для стабильности на мобилках
};



document.addEventListener('DOMContentLoaded', () => {
    syncHeader(); // Инициализация при старте
});
initApp();