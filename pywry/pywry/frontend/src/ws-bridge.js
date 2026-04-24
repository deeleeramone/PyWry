(function() {
    const widgetId = '__WIDGET_ID__';
    const WS_AUTH_TOKEN = __WS_AUTH_TOKEN__;
    const PYWRY_DEBUG = __PYWRY_DEBUG__;

    // Use window.location to get current host/port (same as IFrame)
    const protocol = window.location.protocol;
    const host = window.location.hostname;
    const port = window.location.port;
    const apiUrl = protocol + '//' + host + (port ? ':' + port : '');

    // WebSocket connection
    const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = wsProtocol + '//' + host + (port ? ':' + port : '') + '/ws/' + widgetId;
    let socket = null;
    let reconnectAttempts = 0;
    let authFailures = 0;

    window.pywry = {
        _ready: false,
        _handlers: {},
        _pending: [],
        _msgQueue: [],
        _widgetId: widgetId,

        result: function(data) {
            this.emit('pywry:result', data);
        },

        emit: function(type, data) {
            const msg = { type: type, data: data, widgetId: widgetId, ts: Date.now() };

            if (!socket || socket.readyState !== WebSocket.OPEN) {
                console.warn('[PyWry] WebSocket not ready, queueing emit:', type);
                this._msgQueue.push(msg);
                return;
            }

            if (PYWRY_DEBUG) {
                console.log('[PyWry] Sending via WS:', msg);
            }
            socket.send(JSON.stringify(msg));
        },

        on: function(type, callback) {
            if (!this._handlers[type]) this._handlers[type] = [];
            this._handlers[type].push(callback);
            const pending = this._pending.filter(p => p.type === type);
            this._pending = this._pending.filter(p => p.type !== type);
            pending.forEach(p => callback(p.data));
        },

        _fire: function(type, data) {
            const handlers = this._handlers[type] || [];
            if (handlers.length === 0) {
                this._pending.push({type: type, data: data});
            } else {
                handlers.forEach(h => h(data));
            }
        },

        send: function(data) {
            this.emit('pywry:message', data);
        }
    };

    function connect() {
        if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
            return;
        }

        if (PYWRY_DEBUG) {
            console.log('[PyWry] Connecting to WebSocket:', wsUrl);
        }

        if (WS_AUTH_TOKEN) {
            socket = new WebSocket(wsUrl, ['pywry.token.' + WS_AUTH_TOKEN]);
        } else {
            socket = new WebSocket(wsUrl);
        }

        socket.onopen = function() {
            console.log('[PyWry] WebSocket connected');
            reconnectAttempts = 0;
            authFailures = 0;

            if (window.pywry._msgQueue && window.pywry._msgQueue.length > 0) {
                if (PYWRY_DEBUG) {
                    console.log('[PyWry] Flushing ' + window.pywry._msgQueue.length + ' queued messages');
                }
                window.pywry._msgQueue.forEach(function(msg) {
                    socket.send(JSON.stringify(msg));
                });
                window.pywry._msgQueue = [];
            }

            window.pywry._ready = true;
            window.pywry._fire('pywry:ready', {});
        };

        socket.onmessage = function(event) {
            try {
                const msg = JSON.parse(event.data);
                if (PYWRY_DEBUG) {
                    console.log('[PyWry] WebSocket received:', msg);
                }

                const events = msg.events || [msg];
                events.forEach(e => {
                    if (e && e.type) {
                        window.pywry._fire(e.type, e.data);
                    }
                });
            } catch (err) {
                console.error('[PyWry] Error parsing message:', err);
            }
        };

        socket.onclose = function(e) {
            console.log('[PyWry] ===== WebSocket CLOSED =====');
            console.log('[PyWry] Close code:', e.code);
            console.log('[PyWry] Close reason:', e.reason);
            console.log('[PyWry] Auth failures before increment:', authFailures);
            window.pywry._ready = false;

            if (e.code === 1000 && e.reason === 'New connection replaced old one') {
                console.log('[PyWry] Connection replaced by newer instance, not reconnecting');
                return;
            }

            if (e.code === 4001 || e.code === 1006) {
                authFailures++;
                console.log('[PyWry] Auth failure detected! New count:', authFailures);

                if (authFailures >= 2) {
                    console.log('[PyWry] ===== REFRESHING PAGE NOW =====');
                    setTimeout(function() {
                        console.log('[PyWry] Calling window.location.reload()...');
                        window.location.reload();
                    }, 500);
                    return;
                }
            }

            if (window.pywry._intentionalDisconnect) {
                console.log('[PyWry] Intentional disconnect, not reconnecting');
                return;
            }

            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
            reconnectAttempts++;
            console.log('[PyWry] Reconnecting in', delay, 'ms... (attempt', reconnectAttempts, ')');
            setTimeout(connect, delay);
        };

        socket.onerror = function(err) {
            console.error('[PyWry] ===== WebSocket ERROR =====');
            console.error('[PyWry] Error:', err);
            console.error('[PyWry] Socket readyState:', socket.readyState);
            socket.close();
        };
    }

    // --- Disconnect handling for page close/refresh/navigate ---
    let disconnectSent = false;

    function sendDisconnect(reason) {
        if (disconnectSent) return;
        disconnectSent = true;
        window.pywry._intentionalDisconnect = true;

        if (PYWRY_DEBUG) {
            console.log('[PyWry] Sending disconnect, reason:', reason);
        }

        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({
                type: 'pywry:disconnect',
                data: { reason: reason },
                widgetId: widgetId
            }));
            socket.close(1000, reason);
        }

        try {
            navigator.sendBeacon(apiUrl + '/disconnect/' + widgetId + '?reason=' + encodeURIComponent(reason));
        } catch (e) {
            if (PYWRY_DEBUG) {
                console.log('[PyWry] sendBeacon failed:', e);
            }
        }
    }

    // Clear all revealed secrets from DOM
    var SECRET_MASK = '••••••••••••';
    function clearSecrets() {
        try {
            var secretInputs = document.querySelectorAll('.pywry-input-secret, input[type="password"]');
            for (var i = 0; i < secretInputs.length; i++) {
                var inp = secretInputs[i];
                inp.type = 'password';
                if (inp.dataset && inp.dataset.hasValue === 'true') {
                    inp.value = SECRET_MASK;
                    inp.dataset.masked = 'true';
                } else {
                    inp.value = '';
                }
            }
            if (window.pywry && window.pywry._revealedSecrets) {
                window.pywry._revealedSecrets = {};
            }
            if (PYWRY_DEBUG) {
                console.log('[PyWry] Secrets cleared from DOM');
            }
        } catch (e) {
            // Ignore errors during unload
        }
    }

    window.addEventListener('beforeunload', function() {
        clearSecrets();
        sendDisconnect('beforeunload');
    });

    window.addEventListener('pagehide', function() {
        clearSecrets();
        sendDisconnect('pagehide');
    });

    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'hidden') {
            if (PYWRY_DEBUG) {
                console.log('[PyWry] Page hidden (visibility change)');
            }
        }
    });

    // Connect immediately
    connect();
    window.pywry._ready = true;
    if (PYWRY_DEBUG) {
        console.log('[PyWry] Bridge ready! widgetId:', widgetId);
        console.log('[PyWry] window.pywry object:', window.pywry);
    }

    // Theme update handler
    window.pywry.on('pywry:update-theme', function(data) {
        if (PYWRY_DEBUG) {
            console.log('[PyWry] Received theme update:', data.theme);
        }

        const isDark = data.theme && data.theme.includes('dark');
        const isLight = !isDark;

        if (data.theme && data.theme.includes('light')) {
            document.documentElement.className = 'light';
            document.documentElement.classList.add('light');
            document.documentElement.classList.remove('dark');
        } else {
            document.documentElement.className = 'dark';
            document.documentElement.classList.add('dark');
            document.documentElement.classList.remove('light');
        }

        document.querySelectorAll('.pywry-widget').forEach(function(widget) {
            widget.classList.remove('pywry-theme-dark', 'pywry-theme-light');
            widget.classList.add(isLight ? 'pywry-theme-light' : 'pywry-theme-dark');
        });

        document.querySelectorAll('.pywry-toolbar').forEach(function(toolbar) {
            toolbar.classList.remove('pywry-theme-dark', 'pywry-theme-light');
            toolbar.classList.add(isLight ? 'pywry-theme-light' : 'pywry-theme-dark');
        });

        document.querySelectorAll('[class*="pywry-wrapper"]').forEach(function(wrapper) {
            wrapper.classList.remove('pywry-theme-dark', 'pywry-theme-light');
            wrapper.classList.add(isLight ? 'pywry-theme-light' : 'pywry-theme-dark');
        });

        const gridDiv = document.getElementById('grid');
        if (gridDiv && data.theme) {
            gridDiv.className = gridDiv.className.replace(/ag-theme-[\w-]+/g, '').trim();
            gridDiv.className = (gridDiv.className + ' ' + data.theme).trim();
            if (PYWRY_DEBUG) {
                console.log('[PyWry] Updated grid theme class to:', data.theme);
            }
        }

        // Relayout every Plotly chart to match the new theme. Templates
        // are bundled into window.PYWRY_PLOTLY_TEMPLATES; the helpers
        // window.__pywryStripThemeColors and __pywryMergeThemeTemplate
        // are defined by plotly-defaults.js (also inlined into the
        // widget HTML). Plotly's CDN/standalone build doesn't register
        // plotly_dark / plotly_white by name, so we resolve the template
        // object manually. Plotly's explicit layout colour properties
        // always beat template defaults, so the strip pass is mandatory
        // before relayout — otherwise baked-in paper_bgcolor / font
        // colours win and the template swap looks like a no-op.
        if (window.Plotly && window.PYWRY_PLOTLY_TEMPLATES) {
            var plotlyTemplateName = isDark ? 'plotly_dark' : 'plotly_white';
            var plotlyTemplate = window.PYWRY_PLOTLY_TEMPLATES[plotlyTemplateName];
            if (plotlyTemplate) {
                document.querySelectorAll('.js-plotly-plot, [data-pywry-plotly]').forEach(function (plotDiv) {
                    try {
                        // Nuke the stored "user template" overrides. When the
                        // figure is first rendered without an explicit
                        // template, Plotly.js's default (plotly_white) gets
                        // shovelled into __pywry_user_template__ by the
                        // init-time call to __pywryMergeThemeTemplate —
                        // which means every subsequent theme switch merges
                        // plotly_dark under those stored white colours and
                        // the chart keeps looking light. Clearing these
                        // makes the merge fall through to the clean base
                        // template.
                        delete plotDiv.__pywry_user_template__;
                        delete plotDiv.__pywry_user_template_dark__;
                        delete plotDiv.__pywry_user_template_light__;
                        if (typeof window.__pywryStripThemeColors === 'function') {
                            window.__pywryStripThemeColors(plotDiv);
                        }
                        // Deep-clone so future relayouts don't share mutable
                        // state with the cached base template.
                        var tpl = JSON.parse(JSON.stringify(plotlyTemplate));
                        window.Plotly.relayout(plotDiv, { template: tpl });
                    } catch (err) {
                        if (PYWRY_DEBUG) {
                            console.warn('[PyWry] Plotly relayout failed:', err);
                        }
                    }
                });
            } else if (PYWRY_DEBUG) {
                console.warn('[PyWry] Plotly template not found:', plotlyTemplateName);
            }
        }
    });

    // HTML content update handler
    window.pywry.on('pywry:update-html', function(data) {
        if (PYWRY_DEBUG) {
            console.log('[PyWry] Received HTML update, reloading page');
        }
        setTimeout(function() {
            window.location.reload();
        }, 50);
    });

    // Navigation handler
    window.pywry.on('pywry:navigate', function(data) {
        if (data.url) {
            if (PYWRY_DEBUG) {
                console.log('[PyWry] Navigating to:', data.url);
            }
            window.location.href = data.url;
        }
    });

    // Alert handler
    window.pywry.on('pywry:alert', function(data) {
        const message = data.message || data.text || '';
        const type = data.type || 'info';
        const container = document.querySelector('.pywry-widget') || document.body;
        if (PYWRY_DEBUG) {
            console.log('[PyWry] Alert:', type, message);
        }

        if (window.PYWRY_TOAST) {
            if (type === 'confirm') {
                window.PYWRY_TOAST.confirm({
                    message: message,
                    title: data.title,
                    position: data.position,
                    container: container,
                    onConfirm: function() {
                        if (data.callback_event) {
                            window.pywry.emit(data.callback_event, { confirmed: true });
                        }
                    },
                    onCancel: function() {
                        if (data.callback_event) {
                            window.pywry.emit(data.callback_event, { confirmed: false });
                        }
                    }
                });
            } else {
                window.PYWRY_TOAST.show({
                    message: message,
                    title: data.title,
                    type: type,
                    duration: data.duration,
                    position: data.position,
                    container: container
                });
            }
        } else {
            alert(message);
        }
    });

    // CSS injection handler
    window.pywry.on('pywry:inject-css', function(data) {
        if (!data.css) {
            console.error('[PyWry] inject-css requires css property');
            return;
        }
        let css = data.css;
        if (css.includes(':root')) {
            css = css.replace(/:root\s*\{/g, ':root, .pywry-widget, .pywry-theme-dark, .pywry-theme-light {');
        }
        const id = data.id || 'pywry-injected-style';
        let style = document.getElementById(id);
        if (style) {
            style.textContent = css;
        } else {
            style = document.createElement('style');
            style.id = id;
            style.textContent = css;
            document.head.appendChild(style);
        }
        if (PYWRY_DEBUG) {
            console.log('[PyWry] Injected CSS with id:', id);
        }
    });

    // CSS removal handler
    window.pywry.on('pywry:remove-css', function(data) {
        if (!data.id) {
            console.error('[PyWry] remove-css requires id property');
            return;
        }
        const style = document.getElementById(data.id);
        if (style) {
            style.remove();
            if (PYWRY_DEBUG) {
                console.log('[PyWry] Removed CSS with id:', data.id);
            }
        }
    });

    // Set inline styles handler
    window.pywry.on('pywry:set-style', function(data) {
        if (!data.styles) {
            console.error('[PyWry] set_style requires styles property');
            return;
        }
        let elements = [];
        if (data.id) {
            const el = document.getElementById(data.id);
            if (el) elements.push(el);
        } else if (data.selector) {
            elements = Array.from(document.querySelectorAll(data.selector));
        } else {
            console.error('[PyWry] set_style requires id or selector property');
            return;
        }
        elements.forEach(function(el) {
            Object.keys(data.styles).forEach(function(prop) {
                el.style[prop] = data.styles[prop];
            });
        });
        if (PYWRY_DEBUG) {
            console.log('[PyWry] Set styles on', elements.length, 'elements:', data.styles);
        }
    });

    // Set content handler
    window.pywry.on('pywry:set-content', function(data) {
        let elements = [];
        if (data.id) {
            const el = document.getElementById(data.id);
            if (el) elements.push(el);
        } else if (data.selector) {
            elements = Array.from(document.querySelectorAll(data.selector));
        } else {
            console.error('[PyWry] set_content requires id or selector property');
            return;
        }
        elements.forEach(function(el) {
            if ('html' in data) {
                el.innerHTML = data.html;
            } else if ('text' in data) {
                el.textContent = data.text;
            }
        });
        if (PYWRY_DEBUG) {
            console.log('[PyWry] Set content on', elements.length, 'elements');
        }
    });

    // File download handler
    window.pywry.on('pywry:download', function(data) {
        if (!data.content || !data.filename) {
            console.error('[PyWry] Download requires content and filename');
            return;
        }
        const mimeType = data.mimeType || 'application/octet-stream';
        const blob = new Blob([data.content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = data.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        if (PYWRY_DEBUG) {
            console.log('[PyWry] Downloaded:', data.filename);
        }
    });

    // Plotly figure update handler
    window.pywry.on('plotly:update-figure', function(data) {
        const chartEl = document.getElementById('chart');

        if (chartEl && (typeof Plotly !== 'undefined' || typeof window.Plotly !== 'undefined')) {
            const PlotlyLib = typeof Plotly !== 'undefined' ? Plotly : window.Plotly;

            const figureData = data.figure || data;
            const traceData = figureData.data || [];
            const layout = figureData.layout || {};
            const config = data.config || {};

            if (config.modeBarButtonsToAdd) {
                config.modeBarButtonsToAdd = config.modeBarButtonsToAdd.map(function(btn) {
                    if (btn.event && !btn.click) {
                        const eventName = btn.event;
                        const eventData = btn.data || {};
                        btn.click = function(gd) {
                            window.pywry.emit(eventName, eventData);
                        };
                    } else if (typeof btn.click === 'string') {
                        try {
                            btn.click = eval('(' + btn.click + ')');
                        } catch(e) {
                            console.error('[PyWry] Failed to parse button click:', e);
                        }
                    }
                    return btn;
                });
            }

            PlotlyLib.react(chartEl, traceData, layout, config);
        } else {
            console.error('[PyWry] Cannot update: chartEl or Plotly not available');
        }
    });

    // Plotly layout update handler
    window.pywry.on('plotly:update-layout', function(data) {
        const chartEl = document.getElementById('chart');
        if (chartEl && (typeof Plotly !== 'undefined' || typeof window.Plotly !== 'undefined')) {
            const PlotlyLib = typeof Plotly !== 'undefined' ? Plotly : window.Plotly;
            const layout = data.layout || {};
            PlotlyLib.relayout(chartEl, layout);
        }
    });

    // Theme triggers: translate viewer-side theme signals into the
    // internal pywry:update-theme event that the handler above listens
    // for. Covers three cases:
    //
    //   1. Browser prefers-color-scheme changes — fires when the OS
    //      appearance flips, when a DevTools "emulate CSS
    //      prefers-color-scheme" override is toggled, or when a host
    //      webview (Claude Preview, Claude Desktop, etc.) swaps its
    //      own light/dark state by flipping the media query for its
    //      embedded browser.
    //
    //   2. Parent-page postMessage — when the widget is embedded in
    //      a chat widget (AppArtifact iframe) or an MCP-UI client
    //      whose host UI has its own theme toggle, the host sends
    //      {source: 'pywry-host', type: 'pywry:set-theme',
    //       theme: 'dark' | 'light'}.
    //
    //   3. Initial mount — honour the viewer's preference over the
    //      theme baked into the HTML at build time, so a widget
    //      rendered with theme='dark' still shows light if the
    //      viewer's preference is light.
    if (typeof window !== 'undefined' && window.pywry && typeof window.pywry._fire === 'function') {
        window.addEventListener('message', function (evt) {
            var data = evt && evt.data;
            if (!data || typeof data !== 'object') return;
            if (data.source !== 'pywry-host') return;
            if (data.type !== 'pywry:set-theme') return;
            var theme = data.theme;
            if (theme !== 'dark' && theme !== 'light' && theme !== 'system') return;
            window.pywry._fire('pywry:update-theme', { theme: theme });
        });

        if (window.matchMedia) {
            var darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
            var lastPrefers = darkQuery.matches ? 'dark' : 'light';
            var onSchemeChange = function (e) {
                lastPrefers = (e && e.matches !== undefined ? e.matches : darkQuery.matches) ? 'dark' : 'light';
                window.pywry._fire('pywry:update-theme', { theme: lastPrefers });
            };
            if (darkQuery.addEventListener) {
                darkQuery.addEventListener('change', onSchemeChange);
            } else if (darkQuery.addListener) {
                darkQuery.addListener(onSchemeChange);
            }
            // Electron (Claude Preview, Claude Desktop) doesn't reliably
            // fire the matchMedia 'change' event when the host flips
            // prefers-color-scheme underneath the webContents, but the
            // query's own .matches value DOES update. Poll it.
            setInterval(function () {
                var nowPrefers = darkQuery.matches ? 'dark' : 'light';
                if (nowPrefers !== lastPrefers) {
                    lastPrefers = nowPrefers;
                    window.pywry._fire('pywry:update-theme', { theme: nowPrefers });
                }
            }, 500);

            // Initial sync: always fire pywry:update-theme once after the
            // chart renders so Plotly's template matches the current
            // PyWry theme. Without this, a figure rendered without an
            // explicit template defaults to plotly_white even when the
            // surrounding PyWry layer ships as class="dark" — that
            // mismatch is the "chart in light mode while preview is
            // dark" case. Resolved theme priority: explicit html class
            // (dark/light) wins, then prefers-color-scheme, then dark
            // as a safe default.
            var resolveCurrentTheme = function () {
                var html = document.documentElement;
                if (html.classList.contains('light')) return 'light';
                if (html.classList.contains('dark')) return 'dark';
                return darkQuery.matches ? 'dark' : 'light';
            };
            var initialSync = function () {
                var resolved = resolveCurrentTheme();
                // Delay one frame so Plotly has finished its initial
                // layout pass — relaying out before Plotly has created
                // the SVG is a no-op.
                window.requestAnimationFrame(function () {
                    window.pywry._fire('pywry:update-theme', { theme: resolved });
                });
            };
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', initialSync, { once: true });
            } else {
                initialSync();
            }
        }
    }

    window.pywry._fire('pywry:ready', {});

    if (PYWRY_DEBUG) {
        console.log('[PyWry] Bridge initialized for widget:', widgetId);
        console.log('[PyWry] API URL:', apiUrl);
    }
})();
