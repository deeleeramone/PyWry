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
