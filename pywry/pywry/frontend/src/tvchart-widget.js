/* PyWry TradingView Lightweight Charts Widget */

function render({ model, el }) {
    el.innerHTML = '';

    // Inject CSS into the main document to fix Jupyter output cell backgrounds
    // This must be done here because _css only applies inside the widget shadow DOM
    var JUPYTER_FIX_ID = 'pywry-jupyter-fix-css';
    if (!document.getElementById(JUPYTER_FIX_ID)) {
        var style = document.createElement('style');
        style.id = JUPYTER_FIX_ID;
        style.textContent = [
            '.cell-output-ipywidget-background {',
            '    background-color: transparent !important;',
            '}',
            '.jp-OutputArea-output {',
            '    background-color: transparent !important;',
            '}'
        ].join('\n');
        document.head.appendChild(style);
    }

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
        },
        // sendEvent — Python-only notification (no local _fire).
        // Used by theme toggle to notify Python without re-dispatching locally.
        sendEvent: function(type, data) {
            model.set('_js_event', JSON.stringify({ type: type, data: data, ts: Date.now() }));
            model.save_changes();
        }
    };

    container._pywryInstance = pywry;

    // Store this widget's chart ID on the bridge so event handlers can
    // resolve the correct chart without falling back to keys[0].
    var _widgetChartId = model.get('chart_id') || undefined;
    pywry._chartId = _widgetChartId;

    // Bridge dispatcher for inline onclick/onchange handlers in toolbar HTML.
    // Toolbar components (TabGroup, Toggle, Checkbox, etc.) generate inline
    // handlers that call window.pywry.emit(eventName, data, this).  In native
    // desktop mode window.pywry is a real bridge set by scripts.py.  In widget
    // mode there is no global bridge — each widget stores its bridge on its
    // container element.  This proxy walks up the DOM from the source element
    // (the 3rd argument) to find the correct widget's bridge.
    if (!window.pywry) {
        window.pywry = {
            emit: function(type, data, sourceEl) {
                var el = sourceEl;
                while (el) {
                    if (el._pywryInstance) {
                        el._pywryInstance.emit(type, data);
                        return;
                    }
                    el = el.parentElement;
                }
                // No sourceEl or DOM walk failed — resolve from data.chartId
                // via the chart registry (covers tvchart emit calls that don't
                // pass a source element, e.g. compare, symbol-change, intervals).
                var chartId = data && data.chartId;
                if (chartId && window.__PYWRY_TVCHARTS__) {
                    var entry = window.__PYWRY_TVCHARTS__[chartId];
                    if (entry) {
                        if (entry.bridge) { entry.bridge.emit(type, data); return; }
                        if (entry.container) {
                            var w = entry.container.closest && entry.container.closest('.pywry-widget');
                            if (w && w._pywryInstance) { w._pywryInstance.emit(type, data); return; }
                        }
                    }
                }
                // Last resort: find any widget instance on the page
                var widgets = document.querySelectorAll('.pywry-widget');
                for (var i = 0; i < widgets.length; i++) {
                    if (widgets[i]._pywryInstance) {
                        widgets[i]._pywryInstance.emit(type, data);
                        return;
                    }
                }
                console.warn('[PyWry] No bridge found for event:', type);
            },
            on: function() {},
            off: function() {},
            _fire: function() {}
        };
    }

    // Expose module-scoped tvchart functions to window so onclick attributes
    // in toolbar HTML work.  In native windows these are global (loaded via
    // <script> tags), but in the ESM/anywidget context they are module-scoped.
    if (typeof _tvToggleLogScale === 'function') window._tvToggleLogScale = _tvToggleLogScale;
    if (typeof _tvToggleAutoScale === 'function') window._tvToggleAutoScale = _tvToggleAutoScale;
    if (typeof _tvTogglePctScale === 'function') window._tvTogglePctScale = _tvTogglePctScale;
    if (typeof _tvToggleTimezoneMenu === 'function') window._tvToggleTimezoneMenu = _tvToggleTimezoneMenu;
    if (typeof _tvToggleSessionMenu === 'function') window._tvToggleSessionMenu = _tvToggleSessionMenu;

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
        } catch(e) { console.error('[PyWry] change:_py_event parse error:', e); }
    });

    // Custom comm messages bypass trait sync/batching — primary delivery
    // for Python→JS events when emit() runs inside a traitlets observer.
    model.on('msg:custom', function(msg) {
        if (msg && msg.type) {
            pywry._fire(msg.type, msg.data || {});
        }
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

        // Only update THIS widget's chart — never touch other charts
        var newTheme = isDark ? 'dark' : 'light';
        var myChartId = model.get('chart_id');
        if (myChartId && typeof _tvApplyThemeToChart === 'function') {
            _tvApplyThemeToChart(myChartId, newTheme);
        }
    }

    function renderContent() {
        var content = model.get('content');
        var chartConfig = model.get('chart_config');

        if (!content) {
            container.innerHTML = '<div style="padding:20px;color:#888;font-family:monospace;">Waiting for content...</div>';
            return;
        }

        // Register tvchart-defaults event handlers with THIS widget's bridge.
        // Each widget instance gets its own bridge — never touch window.pywry.
        if (typeof window._tvRegisterEventHandlers === 'function') {
            window._tvRegisterEventHandlers(pywry);
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
