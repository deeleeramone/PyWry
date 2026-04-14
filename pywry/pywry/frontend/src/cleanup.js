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
