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
        // Also dispatch locally so JS-side listeners fire immediately
        this._trigger(eventType, data || {});
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
