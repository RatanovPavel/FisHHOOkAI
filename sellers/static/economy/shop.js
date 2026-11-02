function showDashboard(tab = 'store') {
    const container = document.getElementById('auth-content');
    if (!container) return;

    // Используем глобальный объект user
    const currentUser = window.user || {};
    const t = (key) => (window.i18n ? window.i18n.t(key) : key);

    let html = `
        <div class="relative w-full h-full pt-8">
            <button onclick="closeAuthModal()" 
                    class="absolute -top-6 -right-4 z-50 p-2 text-slate-500 hover:text-cyan-400 text-3xl transition-all duration-300 hover:rotate-90">
                ✕
            </button>
            <!-- ВЕРХНЯЯ ЗОНА: ВСЁ ПРИЖАТО ВПРАВО ПРИ ПЕРЕНОСЕ -->
            <div class="flex flex-wrap justify-end items-center gap-3 mb-6 px-1">
                
                <!-- Заголовок: на мобилке при переносе тоже уедет вправо из-за justify-end -->
                <h2 class="logo-neon text-xl uppercase tracking-tighter shrink-0 mr-auto sm:mr-0">
                    ${t('shop.t15')}
                </h2>
                
                <!-- Баланс: всегда прижат вправо -->
                <div class="flex items-center gap-4 bg-slate-950/40 px-4 py-2 rounded-2xl border border-slate-800/50 shrink-0">
                    <div class="flex items-center gap-2">
                        <span class="text-sm">🦴</span>
                        <span class="text-xs font-black text-white font-mono">${currentUser.bones || 0}</span>
                    </div>
                    <div class="w-px h-3 bg-slate-800"></div>
                    <div class="flex items-center gap-2">
                        <span class="text-sm">💀</span>
                        <span class="text-xs font-black text-cyan-400 font-mono">${currentUser.skulls || 0}</span>
                    </div>
                </div>
            </div>

            <!-- ТАБЫ (ВЕРНУЛ КАК БЫЛО) -->
            <div class="flex border-b border-slate-800 mb-6">
                <button onclick="showDashboard('store')" 
                        class="tab-btn py-3 px-6 text-[9px] font-black uppercase tracking-widest transition-all ${tab === 'store' ? 'text-cyan-400 border-b-2 border-cyan-400' : 'text-slate-600 hover:text-slate-400'}">
                    ${t('shop.t1')}
                </button>
                <button onclick="showDashboard('settings')" 
                        class="tab-btn py-3 px-6 text-[9px] font-black uppercase tracking-widest transition-all ${tab === 'settings' ? 'text-cyan-400 border-b-2 border-cyan-400' : 'text-slate-600 hover:text-slate-400'}">
                    ${t('shop.t2')}
                </button>
                ${(currentUser && (currentUser.role === 'blogger' || currentUser.role === 'admin')) ? `
                    <button onclick="showDashboard('referrals')"
                            class="tab-btn py-3 px-6 text-[9px] font-black uppercase tracking-widest transition-all ${tab === 'referrals' ? 'text-cyan-400 border-b-2 border-cyan-400' : 'text-slate-500 hover:text-slate-300'}">
                        ${t('shop.t20')}
                    </button>
                ` : ''}
            </div>
        </div>
    `;


    if (tab === 'store') {
        // 🎯 Это вызовет твой renderStoreView, который подхватит скидки из window.currentPrices
        html += typeof renderStoreView === 'function' ? renderStoreView() : ''; 
    }else if (tab === 'referrals') {

        const refCount = currentUser.referralsCount || 0;
        const refEarned = currentUser.referralsEarned || 0;
        const history = currentUser.referralsHistory || [];
    
        html +=  `
        <!-- Стили для кастомного скроллбара (применяются только внутри этого блока) -->
        <style>
            .custom-scroll::-webkit-scrollbar {
                width: 3px;
            }
            .custom-scroll::-webkit-scrollbar-track {
                background: transparent;
            }
            .custom-scroll::-webkit-scrollbar-thumb {
                background: #1e293b; /* Цвет slate-800 в тон вашей рамки */
                border-radius: 9999px;
            }
            .custom-scroll::-webkit-scrollbar-thumb:hover {
                background: #0ea5e9; /* Подсветка голубым при наведении */
            }
        </style>
    
        <!-- Основной контейнер БЕЗ общего скролла -->
        <div class="space-y-5 p-6 h-full flex flex-col">
            <!-- Заголовок -->
            <h2 class="text-[9px] font-black uppercase tracking-widest text-cyan-400 border-b border-slate-800 pb-3 shrink-0">
                Реферальная система
            </h2>
            
            <!-- Поле с реферальной ссылкой -->
            <div class="bg-slate-900 border border-slate-800 p-4 rounded shrink-0">
                <span class="text-[9px] font-black text-slate-500 block uppercase tracking-widest mb-2">Ваша ссылка для приглашения:</span>
                <div class="flex gap-2">
                    <input type="text" id="refLinkInput" readonly value="https://skulla.ru?ref=${window.user && window.user.email ? window.user.email : ''}"
                        class="w-full bg-black border border-slate-800 p-2.5 rounded text-white text-[10px] font-mono focus:outline-none select-all">
                    
                    <button onclick="
                        const input = document.getElementById('refLinkInput');
                        input.select();
                        navigator.clipboard.writeText(input.value);
                        
                        const btn = this;
                        const origText = btn.innerHTML;
                        btn.innerHTML = 'Скопировано!';
                        btn.classList.remove('text-cyan-400', 'border-slate-800');
                        btn.classList.add('text-emerald-400', 'border-emerald-500/30', 'bg-emerald-950/20');
                        btn.disabled = true;
                        
                        setTimeout(() => {
                            btn.innerHTML = origText;
                            btn.classList.add('text-cyan-400', 'border-slate-800');
                            btn.classList.remove('text-emerald-400', 'border-emerald-500/30', 'bg-emerald-950/20');
                            btn.disabled = false;
                        }, 2000);
                    " class="px-4 bg-black border border-slate-800 rounded text-[9px] font-black uppercase tracking-widest text-cyan-400 hover:text-white hover:border-cyan-500/50 transition-all shrink-0">
                        Копировать
                    </button>
                </div>
            </div>
    
            <!-- Карточки статистики -->
            <div class="grid grid-cols-2 gap-4 shrink-0">
                <!-- КАРТОЧКА 1: ЗАРЕГИСТРИРОВАНО -->
                <div class="p-5 bg-slate-900/40 border border-slate-800 rounded-2xl text-center">
                    <p class="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1">Зарегистрировано</p>
                    <!-- 🔥 ДОБАВИЛИ id="realtime-ref-count" -->
                    <p id="realtime-ref-count" class="text-3xl font-black text-cyan-400 font-mono mb-1">
                        ${window.user && window.user.referrals_count ? window.user.referrals_count : 0}
                    </p>
                    <p class="text-[9px] font-medium text-slate-500">чел.</p>
                </div>

                <!-- КАРТОЧКА 2: БАЛАНС -->
                <div class="p-5 bg-slate-900/40 border border-slate-800 rounded-2xl text-center">
                    <p class="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1">Всего начислено</p>
                    <!-- 🔥 ДОБАВИЛИ id="realtime-ref-balance" -->
                    <p id="realtime-ref-balance" class="text-3xl font-black text-emerald-400 font-mono mb-1">
                        ${window.user && window.user.partner_balance ? window.user.partner_balance : 0}
                    </p>
                    <p class="text-[9px] font-medium text-slate-500">руб.</p>
                </div>
            </div>
    
            <!-- ИСТОРИЯ НАЧИСЛЕНИЙ С КАСТОРМНЫМ СКРОЛЛОМ -->
            <div class="space-y-2 flex flex-col flex-1 min-h-0">
                <h3 class="text-[9px] font-black text-slate-500 uppercase tracking-widest shrink-0">История начислений</h3>
                
                <!-- Ограничиваем высоту этого блока и включаем скролл с нашим классом -->
                <div id="realtime-ref-history" class="custom-scroll border border-slate-800 rounded bg-slate-900/50 divide-y divide-slate-800 overflow-y-auto max-h-[180px] flex-1">
                    ${history.length === 0 ? `
                        <div class="p-6 text-center text-[9px] text-slate-600 font-black uppercase tracking-widest">
                            У вас пока нет реферальных начислений
                        </div>
                    ` : history.map(item => `
                        <div class="flex justify-between items-center p-3 text-[10px]">
                            <div class="space-y-0.5">
                                <div class="text-slate-300 font-bold uppercase tracking-wider">${item.username || 'Реферал'}</div>
                                <div class="text-[9px] text-slate-600 font-mono">${item.date || ''}</div>
                            </div>
                            <div class="text-emerald-400 font-black tracking-wider">
                                +${item.amount || 0} руб.
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
        `;
        setTimeout(() => {
            window.startReferralRealtimeTicker();
        }, 100);
    }
     else {
        const verifySection = currentUser.is_verified 
            ? `<span class="text-[7px] text-green-500 border border-green-500/30 px-2 py-1 rounded font-black tracking-widest uppercase">${t('shop.t3')}</span>`
            : `<button onclick="resendCode('${currentUser.email}')" class="text-[7px] text-yellow-500 border border-yellow-500/30 px-2 py-1 rounded font-black tracking-widest uppercase hover:bg-yellow-500/10 transition-all">${t('shop.t4')}</button>`;

        html += `
            <div class="space-y-8 animate-fadeIn">
                <div>
                    <label class="text-[8px] text-slate-500 uppercase font-black tracking-widest mb-2 block">${t('shop.t16')}</label>
                    <div class="auth-input opacity-70 flex justify-between items-center bg-slate-950/30 border border-slate-800 px-4 py-3 rounded-xl">
                        <span class="truncate pr-4 text-xs font-mono text-slate-300">${currentUser.email}</span>
                        ${verifySection}
                    </div>
                </div>
                <div class="space-y-4">
                    <label class="text-[8px] text-slate-500 uppercase font-black tracking-widest block">${t('shop.t17')}</label>
                    <div class="space-y-3">
                        <input type="password" id="new-pass" placeholder="${t('shop.t18')}" class="auth-input w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-xs font-mono">
                        <input type="password" id="confirm-pass" placeholder="${t('shop.t19')}" class="auth-input w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-xs font-mono">
                    </div>
                    <button onclick="updatePassword()" class="w-full border border-cyan-500/30 hover:border-cyan-400 text-cyan-400 py-4 rounded-xl font-black uppercase text-[10px] tracking-widest transition-all hover:bg-cyan-400/5 active:scale-95">
                        ${t('shop.t5')}
                    </button>
                </div>
            </div>
        `;
    }

    html += `<button onclick="handleLogout()" class="w-full text-[9px] text-slate-800 hover:text-red-500 font-black uppercase tracking-[0.5em] transition-colors py-10">${t('shop.t7')}</button>`;
    
    container.innerHTML = html;
    if (window.i18n) i18n.apply();
}


// Инициализируем глобальные переменные при загрузке
window.currentPrices = null;
window.activeDiscount = 0;
window.lastEnteredPromo = "";

window.renderStoreView = function() {
    const t = (key) => (window.i18n ? window.i18n.t(key) : key);
    
    if (!window.currentPrices || window.currentPrices.length === 0) {
        return `<div class="p-20 text-center animate-pulse text-cyan-500">💀 LOADING...</div>`;
    }

    // Считаем базу от оригинальной цены первого пакета
    const first = window.currentPrices[0];
    const baseUnitPrice = (first.old_price || first.current_price) / first.amount;

    let cardsHtml = window.currentPrices.map(t_tier => {
        const displayPrice = t_tier.current_price;
        const oldPrice = t_tier.old_price;
        const hasDiscount = oldPrice !== null && oldPrice !== undefined && oldPrice !== displayPrice;

        const currentUnitPrice = (oldPrice || displayPrice) / t_tier.amount;
        const savePct = Math.round((1 - (currentUnitPrice / baseUnitPrice)) * 100);
        
        return `
        <button onclick="processPayment('${t_tier.id}')" 
        class="price-btn w-full bg-slate-950/40 border border-slate-800 hover:border-cyan-500/50 p-6 flex flex-col gap-5 rounded-[2rem] transition-all group relative">       
            
            <div class="flex justify-between items-center w-full">
                <div class="flex items-center gap-4">
                    <div class="text-3xl filter grayscale group-hover:grayscale-0 transition-all">💀</div>
                    <div class="text-left">
                        <div class="text-[16px] font-black text-white uppercase tracking-widest leading-none">${t_tier.amount}</div>
                        ${savePct > 0 ? `<span class="benefit-tag mt-2 inline-block text-[8px] text-green-400 font-bold"><span data-i18n="shop.t8">${t('shop.t8')}</span> ${savePct}%</span>` : ''}
                    </div>
                </div>
                
                <div class="text-right flex flex-col items-end">
                    ${hasDiscount ? `<span class="old-price line-through text-[10px] text-slate-500 mb-1">${oldPrice}₽</span>` : ''}
                    <span class="text-xl font-black ${hasDiscount ? 'text-green-400' : 'text-cyan-400'}">
                        ${displayPrice}₽
                    </span>
                </div>
            </div>

            <div class="benefits-line flex flex-nowrap justify-between gap-1 opacity-50 group-hover:opacity-100 transition-opacity overflow-hidden border-t border-slate-800/30 pt-4">
                <div class="benefit-pill text-[7px] px-1 whitespace-nowrap"><span>⚡</span> <span data-i18n="shop.t9">${t('shop.t9')}</span></div>
                <div class="benefit-pill text-[7px] px-1 whitespace-nowrap"><span>⚡</span> <span data-i18n="shop.t10">${t('shop.t10')}</span></div>
                <div class="benefit-pill text-[7px] px-1 whitespace-nowrap"><span>⚡</span> <span data-i18n="shop.t11">${t('shop.t11')}</span></div>
                <div class="benefit-pill text-[7px] px-1 whitespace-nowrap"><span>⚡</span> <span data-i18n="shop.t12">${t('shop.t12')}</span></div>
            </div>
        </button>`;
    }).join('');

    return `
        <div class="store-cards-wrapper custom-scrollbar flex flex-col gap-4">
            ${cardsHtml}
        </div>

        <div class="promo-static-footer mt-6">
            <div class="flex gap-2">
                <input type="text" id="store-promo-input" placeholder="PROMO_CODE" 
                    class="auth-input mb-0 flex-1 uppercase font-black text-[10px]"
                    value="${window.lastEnteredPromo || ''}">
                <button onclick="applyStorePromo()" 
                        class="bg-cyan-600/20 hover:bg-cyan-600 text-cyan-400 hover:text-slate-950 px-6 rounded-xl font-black text-[10px] transition-all border border-cyan-600/30">
                    <span data-i18n="shop.t13">${t('shop.t13')}</span>
                </button>
            </div>
            <div id="promo-msg" class="text-[8px] font-black uppercase mt-3 text-center tracking-widest h-2">
                ${(window.activeDiscount > 0) ? `<span data-i18n="shop.t14" class="text-green-500">${t('shop.t14')} -${window.activeDiscount}%</span>` : ''}
            </div>
        </div>
    `;
};



async function applyStorePromo(promo = "") {
    const input = document.getElementById('store-promo-input');
    const finalPromo = (typeof promo === 'string' && promo !== "") ? promo : (input ? input.value.trim() : "");
    
    window.lastEnteredPromo = finalPromo;
    const fd = new FormData();
    fd.append('promo', finalPromo);

    try {
        const response = await fetch('/api/shop/calculate_prices', { method: 'POST', body: fd });
        const data = await response.json();
        
        if (data.status === "success") {
            window.currentPrices = data.tiers; 
            window.activeDiscount = data.active_discount; 

            //showDashboard('store');

            // 3. Возвращаем фокус в инпут, чтобы курсор не прыгал
            setTimeout(() => {
                const ni = document.getElementById('store-promo-input');
                if (ni) {
                    ni.focus();
                    ni.setSelectionRange(ni.value.length, ni.value.length);
                }
            }, 50);
        }
    } catch (e) {
        console.error("Promo error:", e);
    }
}


async function processPayment(tierId) {
    // 1. Проверка юзера
    if (!window.user || !window.user.isLoggedIn) {
        alert(window.i18n ? i18n.t('auth.t26') : "Сначала войди, бро!");
        if (typeof showLoginForm === 'function') showLoginForm();
        return;
    }

    // 🎯 ФИКС: Читаем промокод ДО ТОГО, как обновим innerHTML лоадером
    // Сначала ищем в инпуте, если инпута нет (например, уже нажали) — берем из глобальной переменной
    const promoInput = document.getElementById('store-promo-input');
    const activePromo = promoInput ? promoInput.value.trim() : (window.lastEnteredPromo || "");

    // 2. Лоадер в контент (теперь можно затирать, данные уже в переменной activePromo)
    const container = document.getElementById('auth-content');
    if (container) {
        container.innerHTML = `
            <div class="py-20 text-center animate-pulse">
                <div class="text-4xl mb-4">💀</div>
                <h2 class="logo-neon text-[10px] uppercase tracking-[0.5em]">Generating_Invoice...</h2>
            </div>
        `;
    }

    // 3. Сбор данных
    const fd = new FormData();
    fd.append('tier_id', tierId);
    fd.append('email', window.user.email);
    
    // Отправляем промокод, если он есть
    if (activePromo) {
        fd.append('promo', activePromo.toUpperCase());
        console.log("🎫 [PAYMENT]: Применяю промокод для оплаты:", activePromo.toUpperCase());
    }

    try {
        const response = await fetch('/api/shop/payments/create', { 
            method: 'POST', 
            body: fd 
        });

        if (response.ok) {
            const data = await response.json();
            if (data.confirmation_url) {
                window.location.href = data.confirmation_url;
            }
        } else {
            const errData = await response.json();
            alert("Ошибка шлюза: " + (errData.detail || "ERR"));
            if (typeof showDashboard === 'function') showDashboard('store');
        }
    } catch (e) {
        console.error("🚫 [NETWORK_ERR]:", e);
        if (typeof showDashboard === 'function') showDashboard('store');
    }
}


// Инициализация при загрузке страницы
function initApp() {
    const saved = localStorage.getItem('skulla_user');
    if (saved && saved !== "undefined") {
        try {
            user = JSON.parse(saved);
            console.log("✅ [DEBUG] Сессия восстановлена для:", user.email);
        } catch (e) {
            console.error("❌ Ошибка парсинга:", e);
        }
    }
    syncHeader(); // Отрисовываем состояние (войден или нет)
}

// 🔥 ФУНКЦИЯ ЧЕСТНОГО РЕАЛ-ТАЙМА БЕЗ ПЕРЕЗАХОДОВ
window.startReferralRealtimeTicker = function() {
    if (window.refStatsInterval) clearInterval(window.refStatsInterval);

    // 🚀 Создаем отдельную функцию запроса, чтобы вызвать её без задержки
    async function updateReferralData() {
        const countElem = document.getElementById("realtime-ref-count");
        if (!countElem || !window.user) return;

        try {
            const response = await fetch('/api/auth/referral_stats');
            if (response.ok) {
                const data = await response.json();

                // 1. Мгновенно обновляем циферки на карточках
                document.getElementById("realtime-ref-count").innerText = data.referrals_count;
                document.getElementById("realtime-ref-balance").innerText = data.partner_balance;

                // 2. Синхронизируем локальную память
                window.user.referrals_count = data.referrals_count;
                window.user.partner_balance = data.partner_balance;
                localStorage.setItem('skulla_user', JSON.stringify(window.user));

                // 3. Мгновенно обновляем кастомный скролл истории
                const historyContainer = document.getElementById("realtime-ref-history");
                if (historyContainer) {
                    if (!data.history || data.history.length === 0) {
                        historyContainer.innerHTML = `
                            <div class="p-6 text-center text-[9px] text-slate-600 font-black uppercase tracking-widest">
                                У вас пока нет реферальных начислений
                            </div>
                        `;
                    } else {
                        historyContainer.innerHTML = data.history.map(item => `
                            <div class="flex justify-between items-center p-3 text-[10px]">
                                <div class="space-y-0.5">
                                    <div class="text-slate-300 font-bold uppercase tracking-wider">${item.description || 'Реферал'}</div>
                                    <div class="text-[9px] text-slate-600 font-mono">${item.date || ''}</div>
                                </div>
                                <div class="text-emerald-400 font-black tracking-wider">
                                    +${item.amount || 0} руб.
                                </div>
                            </div>
                        `).join('');
                    }
                }
            } else if (response.status === 403 || response.status === 401) {
                clearInterval(window.refStatsInterval);
                console.warn("[Рефералка]: Доступ заблокирован сервером.");
            }
        } catch (err) {
            console.error("Ошибка автообновления рефералки:", err);
        }
    }

    // 🚀 ВЫЗЫВАЕМ МГНОВЕННО ПРИ ОТКРЫТИИ
    updateReferralData();

    // 🔄 И затем запускаем регулярный повтор каждые 5 секунд
    window.refStatsInterval = setInterval(updateReferralData, 5000);
};


applyStorePromo(""); 