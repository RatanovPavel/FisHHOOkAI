        // 1. Хранилище активных фильтров
        let selectedCategories = [];
        let selectedTools = [];

        // 2. Генерация кнопок-чипов (вызывается внутри loadCatalog)
function renderFilterChips() {
    // 🎯 Проверяем наличие fullData и списка тегов
    if (!window.fullData || !window.fullData.all_tags) return;

    const { groups, all_tags, effects } = window.fullData;
    const catContainer = document.getElementById('category-chips');
    const toolContainer = document.getElementById('tool-chips');
    const lang = localStorage.getItem('lang') || 'ru';
    
    // 1. ОТРИСОВКА КАТЕГОРИЙ (ГРУПП)
    if (catContainer) {
        catContainer.innerHTML = groups.filter(g => g.id !== 'favorites').map(group => {
            const title = (window.i18n && group.title.includes('.')) 
                          ? window.i18n.t(group.title) 
                          : group.title;
            return `
                <button onclick="toggleFilter('category', '${group.id}', this)" 
                        class="filter-chip chip-off px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest border border-slate-800">
                    <span class="symbol">+</span> ${title}
                </button>
            `;
        }).join('');
    }

    // 2. 🎯 ОТРИСОВКА ТЕГОВ (ИНСТРУМЕНТОВ)
    if (toolContainer) {
        toolContainer.innerHTML = all_tags.map(tagId => {
            // Ищем в массиве эффектов первый попавшийся, у которого есть этот тег
            const sourceEffect = effects.find(e => e.tags && e.tags.includes(tagId));
            
            // Пытаемся достать локализованное имя из конфига этого эффекта
            let translatedTag = tagId; // Запасной вариант (ID)
            
            if (sourceEffect && sourceEffect.i18n && sourceEffect.i18n[lang]?.tags_list) {
                translatedTag = sourceEffect.i18n[lang].tags_list[tagId] || tagId;
            }

            return `
                <button onclick="toggleFilter('tool', '${tagId}', this)" 
                        class="filter-chip chip-off px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest border border-slate-800 hover:border-cyan-500/50 transition-all flex items-center gap-2">
                    <span class="symbol">+</span> ${translatedTag}
                </button>
            `;
        }).join('');
    }
}




        // 3. Логика переключения Плюс / Крестик
        function toggleFilter(type, id, el) {
            const list = type === 'category' ? selectedCategories : selectedTools;
            const symbol = el.querySelector('.symbol');
            
            if (list.includes(id)) {
                // УДАЛЯЕМ ИЗ ФИЛЬТРА
                list.splice(list.indexOf(id), 1);
                el.classList.remove('chip-on');
                el.classList.add('chip-off');
                symbol.innerText = '+';
            } else {
                // ДОБАВЛЯЕМ В ФИЛЬТР
                list.push(id);
                el.classList.remove('chip-off');
                el.classList.add('chip-on');
                symbol.innerText = '×';
            }
            
            updateFilterCounter();
        }

        // 4. Счетчик и сброс
        function updateFilterCounter() {
            const count = selectedCategories.length + selectedTools.length;
            const label = document.getElementById('active-filter-count');
            label.innerText = `Выбрано: ${count}`;
            label.style.opacity = count > 0 ? "1" : "0";
        }

        // catalog.js или carousel.js

window.renderSearchResults = function(results) {
    console.log("🔍 [SYSTEM]: Отрисовка результатов поиска...");
    
    const catalogContainer = document.getElementById('catalog-container');
    if (!catalogContainer) {
        console.error("❌ [SYSTEM]: Контейнер #catalog-container не найден!");
        return;
    }

    // 1. Если поиск пустой
    if (results.length === 0) {
        // Подтягиваем перевод из i18n напрямую для надежности
        const msg = (window.i18n && typeof i18n.t === 'function') ? i18n.t("filter.t1") : "Ничего не найдено в базе SKULLA";
        const btnText = (window.i18n && typeof i18n.t === 'function') ? i18n.t("filter.t2") : "Сбросить фильтры";

        catalogContainer.innerHTML = `
            <div class="search-view-marker max-w-6xl mx-auto px-4 py-40 text-center border-2 border-dashed border-slate-900 rounded-[3rem] animate-fadeIn">
                <p class="text-slate-700 text-[10px] font-black uppercase tracking-[0.5em]">${msg}</p>
                <!-- ФИКС: Вызываем resetFilters() вместо renderCatalog() -->
                <button onclick="window.resetFilters()" class="mt-6 text-cyan-500 text-[10px] font-black uppercase tracking-widest hover:text-white transition-colors outline-none cursor-pointer">
                    ${btnText}
                </button>
            </div>`;
        return;
    }

    // 2. Рисуем сетку (добавляем маркер поиска для i18n)
    catalogContainer.innerHTML = `
        <div class="search-view-marker max-w-6xl mx-auto px-4 pb-40 animate-fadeIn">
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-8 justify-center justify-items-center">
                ${results.map(eff => `
                    <div class="w-full max-w-[340px]">
                        ${window.createCard(eff)}
                    </div>
                `).join('')}
            </div>
        </div>
    `;
    
    window.scrollTo({ top: catalogContainer.offsetTop - 100, behavior: 'smooth' });
};

window.resetFilters = function() {
    console.log("♻️ [SYSTEM]: Полный сброс фильтров и поиск...");
    
    // 1. Чистим массивы в памяти
    selectedCategories = [];
    selectedTools = [];

    // 2. Сбрасываем визуальное состояние чипсов (вызываем рендер заново для чистоты)
    if (window.renderFilterChips) {
        window.renderFilterChips(); 
    } else {
        const allChips = document.querySelectorAll('.filter-chip');
        allChips.forEach(chip => {
            chip.classList.remove('chip-on');
            chip.classList.add('chip-off');
            const symbol = chip.querySelector('.symbol');
            if (symbol) symbol.innerText = '+';
        });
    }

    // 3. Обнуляем счетчик
    if (window.updateFilterCounter) updateFilterCounter();

    // 4. Очищаем поле поиска
    const searchInput = document.getElementById('effect-search');
    if (searchInput) searchInput.value = "";

    // 5. ПЕРЕЗАПУСКАЕМ КАРУСЕЛИ
    renderCatalog(); 
    
    // 6. Обновляем стрелки
    setTimeout(() => {
        if (window.fullData && window.fullData.groups && window.updateArrows) {
            window.fullData.groups.forEach(g => updateArrows(g.id));
        }
    }, 150);
};

window.applySmartFilter = function() {
    console.log("🚀 [SYSTEM]: Запуск фильтрации...");
    
    const catalogContainer = document.getElementById('catalog-container');
    
    // Проверка на наличие данных, чтобы не словить ошибку
    if (!window.fullData || !window.fullData.effects || !catalogContainer) {
        console.error("❌ [SYSTEM]: Данные каталога или контейнер не найдены!");
        return;
    }

    // 1. Если фильтры не выбраны — возвращаем обычный вид с каруселями
    if (selectedCategories.length === 0 && selectedTools.length === 0) {
        console.log("♻️ [SYSTEM]: Фильтры пусты, возвращаем карусели");
        if (typeof renderCatalog === 'function') {
            renderCatalog();
        }
        return;
    }

    const { effects } = window.fullData;

    // 2. ФИЛЬТРАЦИЯ
    const filteredResults = effects.filter(eff => {
        // Проверка по категориям (Groups)
        const hasCategory = selectedCategories.length === 0 || 
            (eff.groups && selectedCategories.some(cat => eff.groups.includes(cat)));

        // 🎯 ФИКС: Переключено с .tools на .tags (как в твоем CONFIG)
        const hasTag = selectedTools.length === 0 || 
            (eff.tags && selectedTools.some(tag => eff.tags.includes(tag)));

        // Эффект должен подходить под выбранную категорию И под выбранный тег
        return hasCategory && hasTag;
    });

    console.log(`🔍 [SYSTEM]: Найдено совпадений: ${filteredResults.length}`);

    // 3. ОТРИСОВКА
    if (typeof renderSearchResults === 'function') {
        renderSearchResults(filteredResults);
    }

    // 4. ПЛАВНЫЙ СКРОЛЛ
    // Используем небольшой отступ сверху (100px), чтобы заголовок не прилипал к краю экрана
    const yOffset = -100; 
    const y = catalogContainer.getBoundingClientRect().top + window.pageYOffset + yOffset;
    
    window.scrollTo({
        top: y,
        behavior: 'smooth'
    });
};
