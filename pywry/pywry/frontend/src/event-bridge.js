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
