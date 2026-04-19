(function() {
    'use strict';

    // Guard against load-order surprises: if this file runs before
    // bridge.js, install a minimal shim so on()/off()/_trigger() calls
    // below don't throw. bridge.js later replaces the methods in place
    // while preserving _handlers, so registered callbacks survive.
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

    if (window.pywry._systemEventsRegistered) {
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
