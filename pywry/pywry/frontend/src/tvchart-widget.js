/* PyWry TradingView Lightweight Charts Widget */

function render({ model, el }) {
    el.innerHTML = '';

    var isDarkInitial = model.get('theme') === 'dark';
    el.classList.add(isDarkInitial ? 'pywry-theme-dark' : 'pywry-theme-light');

    var container = document.createElement('div');
    container.className = 'pywry-widget';
    container.classList.add(isDarkInitial ? 'pywry-theme-dark' : 'pywry-theme-light');

    var modelHeight = model.get('height');
    var modelWidth = model.get('width');
    if (modelHeight) container.style.setProperty('--pywry-widget-height', modelHeight);
    if (modelWidth) container.style.setProperty('--pywry-widget-width', modelWidth);
    container.style.overflow = 'hidden';
    el.appendChild(container);

    if (window.PYWRY_TOAST && window.PYWRY_TOAST.setContainer) {
        window.PYWRY_TOAST.setContainer(container);
    }

    container._pywryModel = model;

    // Local bridge for this widget instance
    var pywry = {
        _ready: false,
        _handlers: {},
        _pending: [],
        emit: function(type, data) {
            model.set('_js_event', JSON.stringify({ type: type, data: data, ts: Date.now() }));
            model.save_changes();
            // Also dispatch locally so JS-side listeners fire immediately
            this._fire(type, data || {});
        },
        on: function(type, cb) {
            if (!this._handlers[type]) this._handlers[type] = [];
            this._handlers[type].push(cb);
            var pending = this._pending.filter(function(p) { return p.type === type; });
            this._pending = this._pending.filter(function(p) { return p.type !== type; });
            for (var i = 0; i < pending.length; i++) cb(pending[i].data);
        },
        _fire: function(type, data) {
            var handlers = this._handlers[type] || [];
            if (handlers.length === 0) {
                this._pending.push({ type: type, data: data });
            } else {
                for (var i = 0; i < handlers.length; i++) handlers[i](data);
            }
        }
    };

    container._pywryInstance = pywry;

    // Toolbar handlers placeholder (injected by widget builder)
    __TOOLBAR_HANDLERS__

    // Listen for Python events via model trait
    model.off('change:_py_event');
    model.off('change:content');
    model.off('change:chart_config');
    model.off('change:theme');

    model.on('change:_py_event', function() {
        try {
            var event = JSON.parse(model.get('_py_event') || '{}');
            if (event.type) {
                pywry._fire(event.type, event.data);
            }
        } catch(e) { /* ignore */ }
    });

    // Alert/toast support
    pywry.on('pywry:alert', function(data) {
        if (window.PYWRY_TOAST && window.PYWRY_TOAST.show) {
            window.PYWRY_TOAST.show(Object.assign({}, data, { container: container }));
        } else {
            alert(data.message || data.text || '');
        }
    });

    function applyTheme() {
        var isDark = model.get('theme') === 'dark';
        el.classList.remove('pywry-theme-dark', 'pywry-theme-light');
        el.classList.add(isDark ? 'pywry-theme-dark' : 'pywry-theme-light');
        container.classList.remove('pywry-theme-dark', 'pywry-theme-light');
        container.classList.add(isDark ? 'pywry-theme-dark' : 'pywry-theme-light');

        // Update existing TV charts via the defaults theme switcher
        var newTheme = isDark ? 'dark' : 'light';
        if (typeof _tvApplyThemeToAll === 'function') {
            _tvApplyThemeToAll(newTheme);
        }
    }

    function renderContent() {
        var content = model.get('content');
        var chartConfig = model.get('chart_config');

        if (!content) {
            container.innerHTML = '<div style="padding:20px;color:#888;font-family:monospace;">Waiting for content...</div>';
            return;
        }

        // Set window.pywry to our local bridge BEFORE injecting content
        // so inline onclick handlers route through the widget immediately.
        window.pywry = pywry;

        // Register tvchart-defaults event handlers now that pywry is available.
        // In ESM context, the IIFE may have run before pywry existed.
        if (typeof window._tvRegisterEventHandlers === 'function') {
            window._tvRegisterEventHandlers();
        }

        container.innerHTML = content;

        // innerHTML doesn't execute <script> tags.  Re-create them so
        // the browser runs embedded toolbar/legend scripts.
        container.querySelectorAll('script').forEach(function(old) {
            var s = document.createElement('script');
            s.textContent = old.textContent;
            old.parentNode.replaceChild(s, old);
        });

        // Initialize toolbar handlers
        if (typeof initToolbarHandlers === 'function') {
            setTimeout(function() { initToolbarHandlers(container, pywry); }, 10);
        }

        applyTheme();

        // Find chart container element
        var chartEl = container.querySelector('.pywry-tvchart-container');
        if (!chartEl) {
            console.error('[PyWry TVChart] No .pywry-tvchart-container found');
            return;
        }

        if (typeof LightweightCharts === 'undefined') {
            console.error('[PyWry TVChart] LightweightCharts library not available');
            chartEl.innerHTML = '<div style="background:#ff4444;color:white;padding:20px;">LightweightCharts not loaded</div>';
            return;
        }

        // Parse chart config and create chart
        if (chartConfig) {
            try {
                var config = JSON.parse(chartConfig);
                var chartId = model.get('chart_id') || 'main';

                window.PYWRY_TVCHART_CREATE(chartId, chartEl, config);
            } catch(e) {
                console.error('[PyWry TVChart] Failed to parse chart_config:', e);
            }
        }

        pywry._ready = true;
    }

    model.on('change:content', renderContent);
    model.on('change:chart_config', renderContent);
    model.on('change:theme', applyTheme);
    renderContent();
}

export default { render };
