(function() {
    'use strict';

    // Guard against load-order surprises: if this file runs before
    // bridge.js, install a minimal shim so _trigger() calls don't
    // throw.  bridge.js later replaces _trigger in place while
    // preserving _handlers, so any events that fire before bridge.js
    // finishes still reach their eventual subscribers.
    if (!window.pywry) {
        window.pywry = { _handlers: {} };
    }
    if (!window.pywry._handlers) {
        window.pywry._handlers = {};
    }
    if (typeof window.pywry._trigger !== 'function') {
        window.pywry._trigger = function(eventType, data) {
            var handlers = (this._handlers[eventType] || []).concat(this._handlers['*'] || []);
            handlers.forEach(function(handler) {
                try { handler(data, eventType); } catch (err) { console.error(err); }
            });
        };
    }

    // Listen for all pywry:* events from Python
    if (window.__TAURI__ && window.__TAURI__.event) {
        window.__TAURI__.event.listen('pywry:event', function(event) {
            var eventType = event.payload.event_type;
            var data = event.payload.data;
            window.pywry._trigger(eventType, data);
        });
    }

    if (window.PYWRY_DEBUG) {
        console.log('Event bridge initialized');
    }
})();
