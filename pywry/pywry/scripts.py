"""JavaScript bridge scripts for PyWry."""

# pylint: disable=C0302

from __future__ import annotations

from pathlib import Path

from .assets import get_toast_notifications_js


_SRC_DIR = Path(__file__).parent / "frontend" / "src"


def _get_tooltip_manager_js() -> str:
    """Load the tooltip manager JavaScript from the single source file."""
    tooltip_file = _SRC_DIR / "tooltip-manager.js"
    if tooltip_file.exists():
        return tooltip_file.read_text(encoding="utf-8")
    return ""


PYWRY_BRIDGE_JS = """
(function() {
    'use strict';

    // Create or extend window.pywry - DO NOT replace to preserve existing handlers
    if (!window.pywry) {
        window.pywry = {
            theme: 'dark',
            _handlers: {}
        };
    }

    // Ensure _handlers exists
    if (!window.pywry._handlers) {
        window.pywry._handlers = {};
    }

    // Add/update methods on existing object (preserves registered handlers)
    window.pywry.result = function(data) {
        const payload = {
            data: data,
            window_label: window.__PYWRY_LABEL__ || 'unknown'
        };
        if (window.__TAURI__ && window.__TAURI__.pytauri && window.__TAURI__.pytauri.pyInvoke) {
            window.__TAURI__.pytauri.pyInvoke('pywry_result', payload);
        }
    };

    window.pywry.openFile = function(path) {
        if (window.__TAURI__ && window.__TAURI__.pytauri && window.__TAURI__.pytauri.pyInvoke) {
            window.__TAURI__.pytauri.pyInvoke('open_file', { path: path });
        }
    };

    window.pywry.devtools = function() {
        if (window.__TAURI__ && window.__TAURI__.webview) {
            console.log('DevTools requested');
        }
    };

    window.pywry.emit = function(eventType, data) {
        // Validate event type format (matches Python pattern in models.py)
        // Pattern: namespace:event-name with optional :suffix
        // Allows: letters, numbers, underscores, hyphens (case-insensitive)
        if (eventType !== '*' && !/^[a-zA-Z][a-zA-Z0-9]*:[a-zA-Z][a-zA-Z0-9_-]*(:[a-zA-Z0-9_-]+)?$/.test(eventType)) {
            console.error('Invalid event type:', eventType, 'Must match namespace:event-name pattern');
            return;
        }

        // Intercept modal events and handle them locally (client-side)
        if (eventType && eventType.startsWith('modal:')) {
            var parts = eventType.split(':');
            if (parts.length >= 3 && window.pywry && window.pywry.modal) {
                var action = parts[1];
                var modalId = parts.slice(2).join(':');
                if (action === 'open') {
                    window.pywry.modal.open(modalId);
                    return;
                } else if (action === 'close') {
                    window.pywry.modal.close(modalId);
                    return;
                } else if (action === 'toggle') {
                    window.pywry.modal.toggle(modalId);
                    return;
                }
            }
        }

        const payload = {
            label: window.__PYWRY_LABEL__ || 'main',
            event_type: eventType,
            data: data || {}
        };
        if (window.__TAURI__ && window.__TAURI__.pytauri && window.__TAURI__.pytauri.pyInvoke) {
            window.__TAURI__.pytauri.pyInvoke('pywry_event', payload);
        }
    };

    window.pywry.on = function(eventType, callback) {
        if (!this._handlers[eventType]) {
            this._handlers[eventType] = [];
        }
        this._handlers[eventType].push(callback);
    };

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

    window.pywry._trigger = function(eventType, data) {
        // Don't log data for secret-related events
        var isSensitive = eventType.indexOf(':reveal') !== -1 ||
                          eventType.indexOf(':copy') !== -1 ||
                          eventType.indexOf('secret') !== -1 ||
                          eventType.indexOf('password') !== -1 ||
                          eventType.indexOf('api-key') !== -1 ||
                          eventType.indexOf('token') !== -1;
        if (window.PYWRY_DEBUG && !isSensitive) {
            console.log('[PyWry] _trigger called:', eventType, data);
        } else if (window.PYWRY_DEBUG) {
            console.log('[PyWry] _trigger called:', eventType, '[REDACTED]');
        }
        var handlers = this._handlers[eventType] || [];
        var wildcardHandlers = this._handlers['*'] || [];
        handlers.concat(wildcardHandlers).forEach(function(handler) {
            try {
                handler(data, eventType);
            } catch (e) {
                console.error('Error in event handler:', e);
            }
        });
    };

    window.pywry.dispatch = function(eventType, data) {
        // Don't log data for secret-related events
        var isSensitive = eventType.indexOf(':reveal') !== -1 ||
                          eventType.indexOf(':copy') !== -1 ||
                          eventType.indexOf('secret') !== -1 ||
                          eventType.indexOf('password') !== -1 ||
                          eventType.indexOf('api-key') !== -1 ||
                          eventType.indexOf('token') !== -1;
        if (window.PYWRY_DEBUG && !isSensitive) {
            console.log('[PyWry] dispatch called:', eventType, data);
        } else if (window.PYWRY_DEBUG) {
            console.log('[PyWry] dispatch called:', eventType, '[REDACTED]');
        }
        this._trigger(eventType, data);
    };

    console.log('PyWry bridge initialized/updated');
})();
"""

# System event handlers for built-in pywry events
# These are ALWAYS included, not just during hot reload
PYWRY_SYSTEM_EVENTS_JS = """
(function() {
    'use strict';

    // Guard against re-registration of system event handlers
    if (window.pywry && window.pywry._systemEventsRegistered) {
        console.log('[PyWry] System events already registered, skipping');
        return;
    }

    // Helper function to inject or update CSS
    window.pywry.injectCSS = function(css, id) {
        var style = document.getElementById(id);
        if (style) {
            style.textContent = css;
        } else {
            style = document.createElement('style');
            style.id = id;
            style.textContent = css;
            document.head.appendChild(style);
        }
        console.log('[PyWry] Injected CSS with id:', id);
    };

    // Helper function to remove CSS by id
    window.pywry.removeCSS = function(id) {
        var style = document.getElementById(id);
        if (style) {
            style.remove();
            console.log('[PyWry] Removed CSS with id:', id);
        }
    };

    // Helper function to set element styles
    window.pywry.setStyle = function(data) {
        var styles = data.styles;
        if (!styles) return;
        var elements = [];
        if (data.id) {
            var el = document.getElementById(data.id);
            if (el) elements.push(el);
        } else if (data.selector) {
            elements = Array.from(document.querySelectorAll(data.selector));
        }
        elements.forEach(function(el) {
            Object.keys(styles).forEach(function(prop) {
                el.style[prop] = styles[prop];
            });
        });
        console.log('[PyWry] Set styles on', elements.length, 'elements:', styles);
    };

    // Helper function to set element content
    window.pywry.setContent = function(data) {
        var elements = [];
        if (data.id) {
            var el = document.getElementById(data.id);
            if (el) elements.push(el);
        } else if (data.selector) {
            elements = Array.from(document.querySelectorAll(data.selector));
        }
        elements.forEach(function(el) {
            if ('html' in data) {
                el.innerHTML = data.html;
            } else if ('text' in data) {
                el.textContent = data.text;
            }
        });
        console.log('[PyWry] Set content on', elements.length, 'elements');
    };

    // Register built-in pywry.on handlers for system events
    // These are triggered via pywry.dispatch() when Python calls widget.emit()
    window.pywry.on('pywry:inject-css', function(data) {
        window.pywry.injectCSS(data.css, data.id);
    });

    window.pywry.on('pywry:remove-css', function(data) {
        window.pywry.removeCSS(data.id);
    });

    window.pywry.on('pywry:set-style', function(data) {
        window.pywry.setStyle(data);
    });

    window.pywry.on('pywry:set-content', function(data) {
        window.pywry.setContent(data);
    });

    window.pywry.on('pywry:refresh', function() {
        if (window.pywry.refresh) {
            window.pywry.refresh();
        } else {
            window.location.reload();
        }
    });

    // Handler for file downloads - uses Tauri save dialog in native mode
    window.pywry.on('pywry:download', function(data) {
        if (!data.content || !data.filename) {
            console.error('[PyWry] Download requires content and filename');
            return;
        }
        // Use Tauri's native save dialog if available
        if (window.__TAURI__ && window.__TAURI__.dialog && window.__TAURI__.fs) {
            window.__TAURI__.dialog.save({
                defaultPath: data.filename,
                title: 'Save File'
            }).then(function(filePath) {
                if (filePath) {
                    // Write the file using Tauri's filesystem API
                    window.__TAURI__.fs.writeTextFile(filePath, data.content).then(function() {
                        console.log('[PyWry] Saved to:', filePath);
                    }).catch(function(err) {
                        console.error('[PyWry] Failed to save file:', err);
                    });
                } else {
                    console.log('[PyWry] Save cancelled by user');
                }
            }).catch(function(err) {
                console.error('[PyWry] Save dialog error:', err);
            });
        } else {
            // Fallback for browser/iframe mode
            var mimeType = data.mimeType || 'application/octet-stream';
            var blob = new Blob([data.content], { type: mimeType });
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = data.filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            console.log('[PyWry] Downloaded:', data.filename);
        }
    });

    // Handler for navigation
    window.pywry.on('pywry:navigate', function(data) {
        if (data.url) {
            window.location.href = data.url;
        }
    });

    // Handler for alert dialogs - uses PYWRY_TOAST for typed notifications
    window.pywry.on('pywry:alert', function(data) {
        var message = data.message || data.text || '';
        var type = data.type || 'info';

        // Use toast system if available
        if (window.PYWRY_TOAST) {
            if (type === 'confirm') {
                window.PYWRY_TOAST.confirm({
                    message: message,
                    title: data.title,
                    position: data.position,
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
                    position: data.position
                });
            }
        } else {
            // Fallback to browser alert
            alert(message);
        }
    });

    // Handler for replacing HTML content
    window.pywry.on('pywry:update-html', function(data) {
        if (data.html) {
            var app = document.getElementById('app');
            if (app) {
                app.innerHTML = data.html;
            } else {
                document.body.innerHTML = data.html;
            }
        }
    });

    // Register Tauri event listeners that use the shared helper functions
    if (window.__TAURI__ && window.__TAURI__.event) {
        window.__TAURI__.event.listen('pywry:inject-css', function(event) {
            window.pywry.injectCSS(event.payload.css, event.payload.id);
        });

        window.__TAURI__.event.listen('pywry:remove-css', function(event) {
            window.pywry.removeCSS(event.payload.id);
        });

        window.__TAURI__.event.listen('pywry:set-style', function(event) {
            window.pywry.setStyle(event.payload);
        });

        window.__TAURI__.event.listen('pywry:set-content', function(event) {
            window.pywry.setContent(event.payload);
        });

        window.__TAURI__.event.listen('pywry:refresh', function() {
            if (window.pywry.refresh) {
                window.pywry.refresh();
            } else {
                window.location.reload();
            }
        });

        window.__TAURI__.event.listen('pywry:download', function(event) {
            var data = event.payload;
            if (!data.content || !data.filename) {
                console.error('[PyWry] Download requires content and filename');
                return;
            }
            // Use Tauri's native save dialog
            window.__TAURI__.dialog.save({
                defaultPath: data.filename,
                title: 'Save File'
            }).then(function(filePath) {
                if (filePath) {
                    window.__TAURI__.fs.writeTextFile(filePath, data.content).then(function() {
                        console.log('[PyWry] Saved to:', filePath);
                    }).catch(function(err) {
                        console.error('[PyWry] Failed to save file:', err);
                    });
                } else {
                    console.log('[PyWry] Save cancelled by user');
                }
            }).catch(function(err) {
                console.error('[PyWry] Save dialog error:', err);
            });
        });

        window.__TAURI__.event.listen('pywry:navigate', function(event) {
            if (event.payload.url) {
                window.location.href = event.payload.url;
            }
        });

        // pywry:alert is handled by window.pywry.on() - no need for duplicate Tauri listener
        // The Tauri event fires window.pywry._fire() which triggers the pywry.on handler

        window.__TAURI__.event.listen('pywry:update-html', function(event) {
            if (event.payload.html) {
                var app = document.getElementById('app');
                if (app) {
                    app.innerHTML = event.payload.html;
                } else {
                    document.body.innerHTML = event.payload.html;
                }
            }
        });
    }

    // Mark system events as registered to prevent duplicate handlers
    window.pywry._systemEventsRegistered = true;
    console.log('PyWry system events initialized');
})();
"""

# TOOLTIP_MANAGER_JS is now loaded from frontend/src/tooltip-manager.js
# via _get_tooltip_manager_js() to avoid duplication

THEME_MANAGER_JS = """
(function() {
    'use strict';

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
    console.log('[PyWry] Registering pywry:update-theme handler');
    window.pywry.on('pywry:update-theme', function(data) {
        console.log('[PyWry] pywry:update-theme handler called with:', data);
        var theme = data.theme || 'plotly_dark';
        var isDark = theme.includes('dark');
        var mode = isDark ? 'dark' : 'light';
        updateTheme(mode);

        // Also update Plotly with full template if available
        if (window.Plotly && window.__PYWRY_PLOTLY_DIV__) {
            var templateName = theme;
            var template = window.PYWRY_PLOTLY_TEMPLATES && window.PYWRY_PLOTLY_TEMPLATES[templateName];
            if (template) {
                var plotDiv = window.__PYWRY_PLOTLY_DIV__;
                var newLayout = Object.assign({}, plotDiv.layout || {}, { template: template });
                window.Plotly.newPlot(plotDiv, plotDiv.data, newLayout, plotDiv._fullLayout?._config || {});
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
})();
"""

EVENT_BRIDGE_JS = """
(function() {
    'use strict';

    // Listen for all pywry:* events from Python
    if (window.__TAURI__ && window.__TAURI__.event) {
        window.__TAURI__.event.listen('pywry:event', function(event) {
            var eventType = event.payload.event_type;
            var data = event.payload.data;
            window.pywry._trigger(eventType, data);
        });
    }

    console.log('Event bridge initialized');
})();
"""

TOOLBAR_BRIDGE_JS = """
(function() {
    'use strict';

    function getToolbarState(toolbarId) {
        var state = { toolbars: {}, components: {}, timestamp: Date.now() };

        var toolbars = toolbarId
            ? [document.getElementById(toolbarId)]
            : document.querySelectorAll('.pywry-toolbar');

        toolbars.forEach(function(toolbar) {
            if (!toolbar) return;
            var tbId = toolbar.id;
            if (!tbId) return;

            state.toolbars[tbId] = {
                position: Array.from(toolbar.classList)
                    .find(function(c) { return c.startsWith('pywry-toolbar-'); })
                    ?.replace('pywry-toolbar-', '') || 'top',
                components: []
            };

            toolbar.querySelectorAll('[id]').forEach(function(el) {
                var id = el.id;
                var value = null;
                var type = null;

                if (el.tagName === 'BUTTON') {
                    type = 'button';
                    value = { disabled: el.disabled };
                } else if (el.tagName === 'SELECT') {
                    type = 'select';
                    value = el.value;
                } else if (el.tagName === 'INPUT') {
                    var inputType = el.type;
                    if (inputType === 'checkbox') {
                        return;
                    } else if (inputType === 'range') {
                        type = 'range';
                        value = parseFloat(el.value);
                    } else if (inputType === 'number') {
                        type = 'number';
                        value = parseFloat(el.value) || 0;
                    } else if (inputType === 'date') {
                        type = 'date';
                        value = el.value;
                    } else if (el.classList.contains('pywry-input-secret')) {
                        // SECURITY: Never expose secret values via state
                        // Return has_value indicator instead
                        type = 'secret';
                        value = { has_value: el.dataset.hasValue === 'true' };
                    } else {
                        type = 'text';
                        value = el.value;
                    }
                } else if (el.classList.contains('pywry-multiselect')) {
                    type = 'multiselect';
                    value = Array.from(el.querySelectorAll('input:checked'))
                        .map(function(i) { return i.value; });
                } else if (el.classList.contains('pywry-dropdown')) {
                    type = 'select';
                    var selectedOpt = el.querySelector('.pywry-dropdown-option.pywry-selected');
                    value = selectedOpt ? selectedOpt.getAttribute('data-value') : null;
                }

                if (type) {
                    state.components[id] = { type: type, value: value };
                    state.toolbars[tbId].components.push(id);
                }
            });
        });

        return state;
    }

    function getComponentValue(componentId) {
        var el = document.getElementById(componentId);
        if (!el) return null;

        if (el.tagName === 'SELECT') {
            return el.value;
        } else if (el.tagName === 'INPUT') {
            var inputType = el.type;
            // SECURITY: Never expose secret values via state getter
            if (el.classList.contains('pywry-input-secret')) {
                return { has_value: el.dataset.hasValue === 'true' };
            }
            if (inputType === 'range' || inputType === 'number') {
                return parseFloat(el.value);
            }
            return el.value;
        } else if (el.classList.contains('pywry-multiselect')) {
            return Array.from(el.querySelectorAll('input:checked'))
                .map(function(i) { return i.value; });
        } else if (el.classList.contains('pywry-dropdown')) {
            var selectedOpt = el.querySelector('.pywry-dropdown-option.pywry-selected');
            return selectedOpt ? selectedOpt.getAttribute('data-value') : null;
        }
        return null;
    }

    function setComponentValue(componentId, value, attrs) {
        var el = document.getElementById(componentId);
        if (!el) return false;

        // SECURITY: Prevent setting secret values via state setter
        // Secrets must be set via their event handler (with proper encoding)
        if (el.classList && el.classList.contains('pywry-input-secret')) {
            console.warn('[PyWry] Cannot set SecretInput value via toolbar:set-value. Use the event handler instead.');
            return false;
        }

        // Generic attribute setter - handles any attribute for any component
        // Accepts attrs object with attribute name: value pairs
        if (attrs && typeof attrs === 'object') {
            Object.keys(attrs).forEach(function(attrName) {
                var attrValue = attrs[attrName];

                // Skip componentId, toolbarId, value (handled separately), options (handled separately)
                if (attrName === 'componentId' || attrName === 'toolbarId') return;

                // Handle specific attribute types
                switch (attrName) {
                    case 'label':
                    case 'text':
                        // Update text content - find text element or use el directly
                        if (el.classList.contains('pywry-toolbar-button') || el.tagName === 'BUTTON') {
                            el.textContent = attrValue;
                        } else if (el.classList.contains('pywry-dropdown')) {
                            var textEl = el.querySelector('.pywry-dropdown-text');
                            if (textEl) textEl.textContent = attrValue;
                        } else if (el.classList.contains('pywry-checkbox') || el.classList.contains('pywry-toggle')) {
                            var labelEl = el.querySelector('.pywry-checkbox-label, .pywry-input-label');
                            if (labelEl) labelEl.textContent = attrValue;
                        } else if (el.classList.contains('pywry-tab-group')) {
                            // For tab groups, label refers to the group label
                            var groupLabel = el.closest('.pywry-input-group');
                            if (groupLabel) {
                                var lbl = groupLabel.querySelector('.pywry-input-label');
                                if (lbl) lbl.textContent = attrValue;
                            }
                        } else {
                            // Generic fallback - try to find label span or set text directly
                            var label = el.querySelector('.pywry-input-label');
                            if (label) {
                                label.textContent = attrValue;
                            } else if (el.textContent !== undefined) {
                                el.textContent = attrValue;
                            }
                        }
                        break;

                    case 'html':
                    case 'innerHTML':
                        // Update HTML content
                        if (el.classList.contains('pywry-toolbar-button') || el.tagName === 'BUTTON') {
                            el.innerHTML = attrValue;
                        } else if (el.classList.contains('pywry-dropdown')) {
                            var textEl = el.querySelector('.pywry-dropdown-text');
                            if (textEl) textEl.innerHTML = attrValue;
                        } else {
                            el.innerHTML = attrValue;
                        }
                        break;

                    case 'disabled':
                        // Toggle disabled state
                        if (attrValue) {
                            el.setAttribute('disabled', 'disabled');
                            el.classList.add('pywry-disabled');
                            // Also disable any inputs inside
                            el.querySelectorAll('input, button, select, textarea').forEach(function(inp) {
                                inp.setAttribute('disabled', 'disabled');
                            });
                        } else {
                            el.removeAttribute('disabled');
                            el.classList.remove('pywry-disabled');
                            el.querySelectorAll('input, button, select, textarea').forEach(function(inp) {
                                inp.removeAttribute('disabled');
                            });
                        }
                        break;

                    case 'variant':
                        // Swap variant class for buttons
                        if (el.classList.contains('pywry-toolbar-button') || el.tagName === 'BUTTON') {
                            // Remove existing variant classes
                            var variants = ['primary', 'secondary', 'neutral', 'ghost', 'outline', 'danger', 'warning', 'icon'];
                            variants.forEach(function(v) {
                                el.classList.remove('pywry-btn-' + v);
                            });
                            // Add new variant (if not primary, which is default with no class)
                            if (attrValue && attrValue !== 'primary') {
                                el.classList.add('pywry-btn-' + attrValue);
                            }
                        }
                        break;

                    case 'size':
                        // Swap size class for buttons/tabs
                        if (el.classList.contains('pywry-toolbar-button') || el.tagName === 'BUTTON' || el.classList.contains('pywry-tab-group')) {
                            var sizes = ['xs', 'sm', 'lg', 'xl'];
                            sizes.forEach(function(s) {
                                el.classList.remove('pywry-btn-' + s);
                                el.classList.remove('pywry-tab-' + s);
                            });
                            if (attrValue) {
                                if (el.classList.contains('pywry-tab-group')) {
                                    el.classList.add('pywry-tab-' + attrValue);
                                } else {
                                    el.classList.add('pywry-btn-' + attrValue);
                                }
                            }
                        }
                        break;

                    case 'description':
                    case 'tooltip':
                        // Update data-tooltip attribute
                        if (attrValue) {
                            el.setAttribute('data-tooltip', attrValue);
                        } else {
                            el.removeAttribute('data-tooltip');
                        }
                        break;

                    case 'data':
                        // Update data-data attribute (JSON payload for buttons)
                        if (attrValue) {
                            el.setAttribute('data-data', JSON.stringify(attrValue));
                        } else {
                            el.removeAttribute('data-data');
                        }
                        break;

                    case 'event':
                        // Update data-event attribute
                        el.setAttribute('data-event', attrValue);
                        break;

                    case 'style':
                        // Update inline styles - can be string or object
                        if (typeof attrValue === 'string') {
                            el.style.cssText = attrValue;
                        } else if (typeof attrValue === 'object') {
                            Object.keys(attrValue).forEach(function(prop) {
                                el.style[prop] = attrValue[prop];
                            });
                        }
                        break;

                    case 'className':
                    case 'class':
                        // Add/remove CSS classes
                        if (typeof attrValue === 'string') {
                            attrValue.split(' ').forEach(function(cls) {
                                if (cls) el.classList.add(cls);
                            });
                        } else if (typeof attrValue === 'object') {
                            // Object format: {add: ['cls1'], remove: ['cls2']}
                            if (attrValue.add) {
                                (Array.isArray(attrValue.add) ? attrValue.add : [attrValue.add]).forEach(function(cls) {
                                    if (cls) el.classList.add(cls);
                                });
                            }
                            if (attrValue.remove) {
                                (Array.isArray(attrValue.remove) ? attrValue.remove : [attrValue.remove]).forEach(function(cls) {
                                    if (cls) el.classList.remove(cls);
                                });
                            }
                        }
                        break;

                    case 'checked':
                        // Toggle checked state for checkboxes/toggles
                        var checkbox = el.querySelector('input[type="checkbox"]') || (el.type === 'checkbox' ? el : null);
                        if (checkbox) {
                            checkbox.checked = !!attrValue;
                            // Update visual state
                            if (attrValue) {
                                el.classList.add('pywry-toggle-checked');
                            } else {
                                el.classList.remove('pywry-toggle-checked');
                            }
                        }
                        break;

                    case 'selected':
                        // Update selected value for radio groups, tab groups
                        if (el.classList.contains('pywry-radio-group')) {
                            el.querySelectorAll('input[type="radio"]').forEach(function(radio) {
                                radio.checked = radio.value === attrValue;
                            });
                        } else if (el.classList.contains('pywry-tab-group')) {
                            el.querySelectorAll('.pywry-tab').forEach(function(tab) {
                                if (tab.dataset.value === attrValue) {
                                    tab.classList.add('pywry-tab-active');
                                } else {
                                    tab.classList.remove('pywry-tab-active');
                                }
                            });
                        }
                        break;

                    case 'placeholder':
                        // Update placeholder for inputs
                        var input = el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' ? el : el.querySelector('input, textarea');
                        if (input) {
                            input.setAttribute('placeholder', attrValue);
                        }
                        break;

                    case 'min':
                    case 'max':
                    case 'step':
                        // Update constraints for number/range inputs
                        var numInput = el.tagName === 'INPUT' ? el : el.querySelector('input[type="number"], input[type="range"]');
                        if (numInput) {
                            numInput.setAttribute(attrName, attrValue);
                        }
                        break;

                    case 'options':
                        // Handled separately below for dropdowns
                        break;

                    case 'value':
                        // Handled separately below
                        break;

                    default:
                        // Generic attribute setter - set as data attribute or HTML attribute
                        if (attrName.startsWith('data-')) {
                            el.setAttribute(attrName, attrValue);
                        } else {
                            // Try to set as property first, then as attribute
                            try {
                                if (attrName in el) {
                                    el[attrName] = attrValue;
                                } else {
                                    el.setAttribute(attrName, attrValue);
                                }
                            } catch (e) {
                                el.setAttribute(attrName, attrValue);
                            }
                        }
                }
            });
        }

        // Handle value and options (backward compatible behavior)
        var options = attrs && attrs.options;
        if (value === undefined && attrs && attrs.value !== undefined) {
            value = attrs.value;
        }

        if (el.tagName === 'SELECT' || el.tagName === 'INPUT') {
            if (value !== undefined) el.value = value;
            return true;
        } else if (el.classList.contains('pywry-dropdown')) {
            if (options && Array.isArray(options)) {
                var menu = el.querySelector('.pywry-dropdown-menu');
                if (menu) {
                    menu.innerHTML = options.map(function(opt) {
                        var isSelected = String(opt.value) === String(value);
                        return '<div class="pywry-dropdown-option' + (isSelected ? ' pywry-selected' : '') +
                               '" data-value="' + opt.value + '">' + opt.label + '</div>';
                    }).join('');
                }
            }
            if (value !== undefined) {
                var textEl = el.querySelector('.pywry-dropdown-text');
                if (textEl) {
                    var optionEl = el.querySelector('.pywry-dropdown-option[data-value="' + value + '"]');
                    if (optionEl) {
                        textEl.textContent = optionEl.textContent;
                        el.querySelectorAll('.pywry-dropdown-option').forEach(function(opt) {
                            opt.classList.remove('pywry-selected');
                        });
                        optionEl.classList.add('pywry-selected');
                    }
                }
            }
            return true;
        } else if (el.classList.contains('pywry-multiselect')) {
            if (value !== undefined) {
                var values = Array.isArray(value) ? value : [value];
                el.querySelectorAll('input[type="checkbox"]').forEach(function(cb) {
                    cb.checked = values.includes(cb.value);
                });
            }
            return true;
        } else if (el.classList.contains('pywry-toggle')) {
            if (value !== undefined) {
                var checkbox = el.querySelector('input[type="checkbox"]');
                if (checkbox) {
                    checkbox.checked = !!value;
                    if (value) {
                        el.classList.add('pywry-toggle-checked');
                    } else {
                        el.classList.remove('pywry-toggle-checked');
                    }
                }
            }
            return true;
        } else if (el.classList.contains('pywry-checkbox')) {
            if (value !== undefined) {
                var checkbox = el.querySelector('input[type="checkbox"]');
                if (checkbox) checkbox.checked = !!value;
            }
            return true;
        } else if (el.classList.contains('pywry-radio-group')) {
            if (value !== undefined) {
                el.querySelectorAll('input[type="radio"]').forEach(function(radio) {
                    radio.checked = radio.value === value;
                });
            }
            return true;
        } else if (el.classList.contains('pywry-tab-group')) {
            if (value !== undefined) {
                el.querySelectorAll('.pywry-tab').forEach(function(tab) {
                    if (tab.dataset.value === value) {
                        tab.classList.add('pywry-tab-active');
                    } else {
                        tab.classList.remove('pywry-tab-active');
                    }
                });
            }
            return true;
        } else if (el.classList.contains('pywry-range-group')) {
            // Dual-handle range slider
            if (attrs && (attrs.start !== undefined || attrs.end !== undefined)) {
                var startInput = el.querySelector('input[data-range="start"]');
                var endInput = el.querySelector('input[data-range="end"]');
                var fill = el.querySelector('.pywry-range-track-fill');
                var startDisp = el.querySelector('.pywry-range-start-value');
                var endDisp = el.querySelector('.pywry-range-end-value');

                if (startInput && attrs.start !== undefined) startInput.value = attrs.start;
                if (endInput && attrs.end !== undefined) endInput.value = attrs.end;

                // Update visual fill
                if (fill && startInput && endInput) {
                    var min = parseFloat(startInput.min) || 0;
                    var max = parseFloat(startInput.max) || 100;
                    var range = max - min;
                    var startVal = parseFloat(startInput.value);
                    var endVal = parseFloat(endInput.value);
                    var startPct = ((startVal - min) / range) * 100;
                    var endPct = ((endVal - min) / range) * 100;
                    fill.style.left = startPct + '%';
                    fill.style.width = (endPct - startPct) + '%';
                }
                if (startDisp && attrs.start !== undefined) startDisp.textContent = attrs.start;
                if (endDisp && attrs.end !== undefined) endDisp.textContent = attrs.end;
            }
            return true;
        } else if (el.classList.contains('pywry-input-range') || (el.tagName === 'INPUT' && el.type === 'range')) {
            // Single slider
            if (value !== undefined) {
                el.value = value;
                var display = el.nextElementSibling;
                if (display && display.classList.contains('pywry-range-value')) {
                    display.textContent = value;
                }
            }
            return true;
        }

        // Generic fallback - try to set value if provided
        if (value !== undefined && 'value' in el) {
            el.value = value;
            return true;
        }

        // Return true if we processed any attrs
        return attrs && Object.keys(attrs).length > 0;
    }

    window.pywry.on('toolbar:request-state', function(data) {
        var toolbarId = data && data.toolbarId;
        var componentId = data && data.componentId;
        var context = data && data.context;

        var response;
        if (componentId) {
            response = {
                componentId: componentId,
                value: getComponentValue(componentId),
                context: context
            };
        } else {
            response = getToolbarState(toolbarId);
            response.context = context;
            if (toolbarId) response.toolbarId = toolbarId;
        }

        window.pywry.emit('toolbar:state-response', response);
    });

    window.pywry.on('toolbar:set-value', function(data) {
        if (data && data.componentId) {
            // Pass entire data object as attrs for generic attribute setting
            setComponentValue(data.componentId, data.value, data);
        }
    });

    window.pywry.on('toolbar:set-values', function(data) {
        if (data && data.values) {
            Object.keys(data.values).forEach(function(id) {
                setComponentValue(id, data.values[id]);
            });
        }
    });

    window.__PYWRY_TOOLBAR__ = {
        getState: getToolbarState,
        getValue: getComponentValue,
        setValue: setComponentValue
    };
})();
"""

# NOTE: Plotly and AG Grid event bridges are NOT defined here.
# They are loaded from the frontend JS files:
#   - pywry/frontend/src/plotly-defaults.js (single source of truth for Plotly events)
#   - pywry/frontend/src/aggrid-defaults.js (single source of truth for AG Grid events)
# These files are loaded via templates.py's build_plotly_script() and build_aggrid_script()


# Script for cleaning up sensitive inputs on page unload
_UNLOAD_CLEANUP_JS = """
(function() {
    'use strict';

    // Clear all revealed secrets from DOM - called on unload
    // Restores mask for inputs that had a value, clears others
    var MASK_CHARS = '••••••••••••';

    function clearSecrets() {
        try {
            var secretInputs = document.querySelectorAll('.pywry-input-secret, input[type="password"]');
            for (var i = 0; i < secretInputs.length; i++) {
                var inp = secretInputs[i];
                inp.type = 'password';
                // Restore mask if value existed, otherwise clear
                if (inp.dataset && inp.dataset.hasValue === 'true') {
                    inp.value = MASK_CHARS;
                    inp.dataset.masked = 'true';
                } else {
                    inp.value = '';
                }
            }
            if (window.pywry && window.pywry._revealedSecrets) {
                window.pywry._revealedSecrets = {};
            }
        } catch (e) {
            // Ignore errors during unload
        }
    }

    // Page is being unloaded (close tab, refresh, navigate away)
    window.addEventListener('beforeunload', function() {
        clearSecrets();
    });

    // Fallback for mobile/Safari - fires when page is hidden
    window.addEventListener('pagehide', function() {
        clearSecrets();
    });
})();
"""


CLEANUP_JS = """
(function() {
    'use strict';

    // Listen for cleanup signal before window destruction
    if (window.__TAURI__ && window.__TAURI__.event) {
        window.__TAURI__.event.listen('pywry:cleanup', function() {
            console.log('Cleanup requested, releasing resources...');

            // Clear Plotly
            if (window.Plotly && window.__PYWRY_PLOTLY_DIV__) {
                try { Plotly.purge(window.__PYWRY_PLOTLY_DIV__); } catch(e) {}
                window.__PYWRY_PLOTLY_DIV__ = null;
            }

            // Clear AG Grid
            if (window.__PYWRY_GRID_API__) {
                try { window.__PYWRY_GRID_API__.destroy(); } catch(e) {}
                window.__PYWRY_GRID_API__ = null;
            }

            // Clear event handlers
            if (window.pywry) {
                window.pywry._handlers = {};
            }

            console.log('Cleanup complete');
        });
    }

    console.log('Cleanup handler registered');
})();
"""

HOT_RELOAD_JS = """
(function() {
    'use strict';

    // Store scroll position in sessionStorage for preservation across refreshes
    var SCROLL_KEY = 'pywry_scroll_' + (window.__PYWRY_LABEL__ || 'main');

    /**
     * Save current scroll position to sessionStorage.
     */
    function saveScrollPosition() {
        var scrollData = {
            x: window.scrollX || window.pageXOffset,
            y: window.scrollY || window.pageYOffset,
            timestamp: Date.now()
        };
        try {
            sessionStorage.setItem(SCROLL_KEY, JSON.stringify(scrollData));
        } catch (e) {
            // sessionStorage may not be available
        }
    }

    function restoreScrollPosition() {
        try {
            var data = sessionStorage.getItem(SCROLL_KEY);
            if (data) {
                var scrollData = JSON.parse(data);
                // Only restore if saved within last 5 seconds (hot reload window)
                if (Date.now() - scrollData.timestamp < 5000) {
                    window.scrollTo(scrollData.x, scrollData.y);
                }
                sessionStorage.removeItem(SCROLL_KEY);
            }
        } catch (e) {
            // Ignore errors
        }
    }

    // Override refresh to save scroll position before reloading
    window.pywry.refresh = function() {
        saveScrollPosition();
        window.location.reload();
    };

    if (document.readyState === 'complete') {
        restoreScrollPosition();
    } else {
        window.addEventListener('load', restoreScrollPosition);
    }

    console.log('Hot reload bridge initialized');
})();
"""


def build_init_script(
    window_label: str,
    enable_hot_reload: bool = False,
) -> str:
    """Build the core initialization script for a window.

    This builds the CORE JavaScript bridges:
    - pywry bridge (emit, on, result, etc.)
    - theme manager
    - event bridge
    - toolbar bridge
    - cleanup handler
    - hot reload (optional)

    NOTE: Plotly and AG Grid defaults are loaded separately via templates.py's
    build_plotly_script() and build_aggrid_script() functions, which include
    the library JS AND the defaults JS together.

    Parameters
    ----------
    window_label : str
        The label for this window.
    enable_hot_reload : bool, optional
        Whether to include hot reload functionality.

    Returns
    -------
    str
        The combined JavaScript initialization script.
    """
    scripts = [
        f"window.__PYWRY_LABEL__ = '{window_label}';",
        PYWRY_BRIDGE_JS,
        PYWRY_SYSTEM_EVENTS_JS,
        get_toast_notifications_js(),  # Toast notification system
        _get_tooltip_manager_js(),  # Tooltip system for data-tooltip attributes
        THEME_MANAGER_JS,
        EVENT_BRIDGE_JS,
        TOOLBAR_BRIDGE_JS,
        _UNLOAD_CLEANUP_JS,  # SecretInput cleanup on page unload
        CLEANUP_JS,
    ]

    # Add hot reload bridge only when enabled
    if enable_hot_reload:
        scripts.append(HOT_RELOAD_JS)

    return "\n".join(scripts)
