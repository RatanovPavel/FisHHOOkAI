window.i18n = {
    currentLang: localStorage.getItem('lang') || 'ru',
    data: {},
    isReady: null,

    async init() {
        if (this.isReady) return this.isReady;
        this.isReady = (async () => {
            try {
                const resp = await fetch(`/static/locales/${this.currentLang}.json?t=${Date.now()}`);
                if (!resp.ok) throw new Error(`HTTP error! status: ${resp.status}`);
                this.data = await resp.json();
                
                window.currentLanguage = this.currentLang;
                this.apply();
                return true;
            } catch (e) {
                console.error("❌ [i18n]: Ошибка загрузки словаря", e);
                return false;
            }
        })();
        return this.isReady;
    },

    t(key) {
        if (!this.data || !key) return key;
        return key.split('.').reduce((obj, i) => (obj ? obj[i] : null), this.data) || key;
    },

    apply() {
        // Загружаем текущий открытый ИИ-шаблон инфографики из глобалки
        const effect = window.currentEffect;
        const effectI18n = (effect && effect.i18n && effect.i18n[this.currentLang]) ? effect.i18n[this.currentLang] : {};

        document.querySelectorAll('[data-i18n], [data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const placeholderKey = el.getAttribute('data-i18n-placeholder');

            if (placeholderKey) {
                el.placeholder = this.t(placeholderKey);
            }

            if (key) {
                // 1. 🎯 ПЕРЕХВАТ ЛОКАЛИЗАЦИИ ШАПКИ ЭФФЕКТОВ ИЗ ИХ КOНФИГOВ
                if (key.startsWith('effect.')) {
                    if (!effect) return;
                    
                    if (key === 'effect.title') {
                        const titleText = effectI18n.title || effect.title || "БЕЗ НАЗВАНИЯ";
                        el.innerText = titleText.toUpperCase();
                    }
                    if (key === 'effect.desc') {
                        // Пишем чистый текст напрямую в параграф
                        el.innerText = effectI18n.desc || effect.desc || "";
                    }
                    if (key === 'effect.icon') {
                        el.innerText = effect.icon || "📸";
                    }
                    return; 
                }

                // 2. ЖЕЛЕЗОБЕТОННАЯ ЗАЩИТА ИМЕНИ ПОЛЬЗОВАТЕЛЯ
                if (key === 'index.t1') {
                    const text = el.innerText.trim();
                    const currentTranslation = this.t('index.t1');
                    if (text.includes('@') || (text !== "" && text !== "Авторизация" && text !== "Authorization" && text !== "Login" && text !== currentTranslation)) {
                        return; 
                    }
                }

                // Игнорим динамические блоки каталога (у них свои функции отрисовки)
                if (!el.closest('.effect-card') && !el.closest('.filter-chip') && !el.closest('.detailed-view-wrap') && key !== 'editor.t5') {
                    el.innerText = this.t(key);
                }
            }
        });

        // Обновление активных классов языковых кнопок в шапке
        const ruBtn = document.getElementById('lang-ru');
        const enBtn = document.getElementById('lang-en');
        if (ruBtn && enBtn) {
            const activeClass = 'text-cyan-400';
            const inactiveClass = 'text-slate-500';
            ruBtn.classList.toggle(activeClass, this.currentLang === 'ru');
            ruBtn.classList.toggle(inactiveClass, this.currentLang !== 'ru');
            enBtn.classList.toggle(activeClass, this.currentLang === 'en');
            enBtn.classList.toggle(inactiveClass, this.currentLang !== 'en');
        }

        // Синхронизация цен на кнопках (10 Бонов / 5 Скалл)
        if (window.updatePriceDisplay) {
            window.updatePriceDisplay();
        }
    },

    async setLang(lang) {
        if (this.currentLang === lang) return;
        this.currentLang = lang;
        window.currentLanguage = lang;
        localStorage.setItem('lang', lang);
        this.isReady = null; 
        await this.init(); 
        
        // Перерисовываем интерфейс в зависимости от текущего экрана
        const isDetailed = document.querySelector('.detailed-view-marker');
        const isSearch = document.querySelector('.search-view-marker');
        const isAuthVisible = !document.getElementById('auth-modal')?.classList.contains('hidden');

        if (isAuthVisible && typeof window.showDashboard === 'function') {
            //user.isLoggedIn ? showDashboard() : showLoginForm();
        }

        if (isSearch && typeof window.applySmartFilter === 'function') {
            window.applySmartFilter(); 
        } 
        else if (isDetailed && window.lastOpenedCategory && typeof window.showGroupDetailed === 'function') {
            window.showGroupDetailed(window.lastOpenedCategory);
        } 
        else if (typeof window.renderCatalog === 'function') {
            window.renderCatalog();
        }

        if (typeof window.renderFilterChips === 'function') {
            window.renderFilterChips();
        }
    }
};

i18n.init();
