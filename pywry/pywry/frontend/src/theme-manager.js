(function() {
    'use strict';

    // Guard against load-order surprises: if this file runs before
    // bridge.js, install a minimal shim so on()/_trigger() calls below
    // don't throw. bridge.js later replaces the methods in place while
    // preserving _handlers, so registered callbacks survive.
    if (!window.pywry) {
        window.pywry = { _handlers: {} };
    }
    if (!window.pywry._handlers) {
        window.pywry._handlers = {};
    }
    if (typeof window.pywry.on !== 'function') {
        window.pywry.on = function(eventType, callback) {
            if (!this._handlers[eventType]) this._handlers[eventType] = [];
            this._handlers[eventType].push(callback);
        };
    }
    if (typeof window.pywry.off !== 'function') {
        window.pywry.off = function(eventType, callback) {
            if (!this._handlers[eventType]) return;
            if (!callback) {
                delete this._handlers[eventType];
            } else {
                this._handlers[eventType] = this._handlers[eventType].filter(
                    function(h) { return h !== callback; }
                );
            }
        };
    }
    if (typeof window.pywry._trigger !== 'function') {
        window.pywry._trigger = function(eventType, data) {
            var handlers = (this._handlers[eventType] || []).concat(this._handlers['*'] || []);
            handlers.forEach(function(handler) {
                try { handler(data, eventType); } catch (err) { console.error(err); }
            });
        };
    }

    if (window.__TAURI__ && window.__TAURI__.event) {
        window.__TAURI__.event.listen('pywry:theme-update', function(event) {
            var mode = event.payload.mode;
            updateTheme(mode);
        });
    }

    if (window.matchMedia) {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
            var html = document.documentElement;
            if (html.dataset.themeMode === 'system') {
                updateTheme('system');
            }
        });
    }

    function updateTheme(mode) {
        var html = document.documentElement;
        var resolvedMode = mode;

        html.dataset.themeMode = mode;

        if (mode === 'system') {
            var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            resolvedMode = prefersDark ? 'dark' : 'light';
        }

        html.classList.remove('light', 'dark');
        html.classList.add(resolvedMode);
        window.pywry.theme = resolvedMode;

        var isDark = resolvedMode === 'dark';

        if (window.Plotly && window.__PYWRY_PLOTLY_DIV__) {
            Plotly.relayout(window.__PYWRY_PLOTLY_DIV__, {
                template: isDark ? 'plotly_dark' : 'plotly_white'
            });
        }

        var gridDiv = document.querySelector('[class*="ag-theme-"]');
        if (gridDiv) {
            var classList = Array.from(gridDiv.classList);
            classList.forEach(function(cls) {
                if (cls.startsWith('ag-theme-')) {
                    var baseTheme = cls.replace('-dark', '');
                    gridDiv.classList.remove(cls);
                    gridDiv.classList.add(isDark ? baseTheme + '-dark' : baseTheme);
                }
            });
        }

        window.pywry._trigger('pywry:theme-update', { mode: resolvedMode, original: mode });
    }

    // Register handler for pywry:update-theme events IMMEDIATELY (not in DOMContentLoaded)
    // because content is injected via JavaScript after the page loads
    if (window.PYWRY_DEBUG) {
        console.log('[PyWry] Registering pywry:update-theme handler');
    }
    window.pywry.on('pywry:update-theme', function(data) {
        if (window.PYWRY_DEBUG) {
            console.log('[PyWry] pywry:update-theme handler called with:', data);
        }
        var theme = data.theme || 'plotly_dark';
        var isDark = theme.includes('dark');
        var mode = isDark ? 'dark' : 'light';
        updateTheme(mode);

        // Also update Plotly with merged template (theme base + user overrides)
        // relayout avoids carrying stale colours from the old layout.
        if (window.Plotly && window.__PYWRY_PLOTLY_DIV__) {
            var plotDiv = window.__PYWRY_PLOTLY_DIV__;
            var templateName = isDark ? 'plotly_dark' : 'plotly_white';
            if (window.__pywryMergeThemeTemplate) {
                var merged = window.__pywryMergeThemeTemplate(plotDiv, templateName);
                if (window.__pywryStripThemeColors) window.__pywryStripThemeColors(plotDiv);
                window.Plotly.relayout(plotDiv, { template: merged });
            }
        }

        // Update AG Grid theme if present
        if (data.theme && data.theme.startsWith('ag-theme-')) {
            var gridDiv = document.querySelector('[class*="ag-theme-"]');
            if (gridDiv) {
                var classList = Array.from(gridDiv.classList);
                classList.forEach(function(cls) {
                    if (cls.startsWith('ag-theme-')) {
                        gridDiv.classList.remove(cls);
                    }
                });
                gridDiv.classList.add(data.theme);
            }
        }
    });

    // Initialize theme on DOMContentLoaded (for initial page load)
    document.addEventListener('DOMContentLoaded', function() {
        var html = document.documentElement;
        var currentTheme = html.classList.contains('dark') ? 'dark' : 'light';
        window.pywry.theme = currentTheme;
    });

    // Host bridge: when the widget is embedded as an AppArtifact in a chat
    // widget, MCP client, or Claude renderer, the outer page may expose a
    // light / dark toggle that is independent of this iframe. The host
    // should postMessage {source: 'pywry-host', type: 'pywry:set-theme',
    // theme: 'dark' | 'light' | 'system'} to signal theme changes. We
    // translate that into an internal pywry:update-theme event so every
    // subsystem (main layout, Plotly, AG Grid, TVChart) switches together.
    window.addEventListener('message', function (evt) {
        var data = evt.data;
        if (!data || typeof data !== 'object') return;
        if (data.source !== 'pywry-host') return;
        if (data.type !== 'pywry:set-theme') return;
        var theme = data.theme;
        if (theme !== 'dark' && theme !== 'light' && theme !== 'system') return;
        if (window.pywry && typeof window.pywry._fire === 'function') {
            window.pywry._fire('pywry:update-theme', { theme: theme });
        }
    });

    // Browser-native theme tracking: Claude Preview's light/dark toggle,
    // the OS-level appearance setting, and any browser devtools "Emulate
    // CSS prefers-color-scheme" override all flip prefers-color-scheme.
    // Subscribe so standalone AppArtifact renders (no parent postMessage
    // bridge) react to whatever the viewer clicked. The baked-in theme
    // from build_html wins until the media query actually fires.
    if (window.matchMedia) {
        var darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
        var onSchemeChange = function (e) {
            var resolved = e.matches ? 'dark' : 'light';
            if (window.pywry && typeof window.pywry._fire === 'function') {
                window.pywry._fire('pywry:update-theme', { theme: resolved });
            }
        };
        if (darkQuery.addEventListener) {
            darkQuery.addEventListener('change', onSchemeChange);
        } else if (darkQuery.addListener) {
            darkQuery.addListener(onSchemeChange);
        }

        // Also sync on initial mount: the HTML ships with whatever theme
        // show_* was invoked with, but the viewer's preference may
        // disagree — honour the viewer if so.
        var initialSync = function () {
            var html = document.documentElement;
            var baked = html.classList.contains('dark') ? 'dark' : 'light';
            var preferred = darkQuery.matches ? 'dark' : 'light';
            if (baked !== preferred && window.pywry && typeof window.pywry._fire === 'function') {
                window.pywry._fire('pywry:update-theme', { theme: preferred });
            }
        };
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initialSync, { once: true });
        } else {
            initialSync();
        }
    }
})();
