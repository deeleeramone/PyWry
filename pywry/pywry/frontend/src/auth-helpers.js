// PyWry Auth Helpers
// Provides window.pywry.auth namespace for frontend authentication support

(function() {
  'use strict';

  // Initialize auth namespace
  window.pywry = window.pywry || {};
  window.pywry.auth = {
    _stateChangeHandlers: [],

    /**
     * Get the current authentication state.
     * @returns {{ authenticated: boolean, user_id?: string, roles?: string[], token_type?: string }}
     */
    getState: function() {
      var authData = window.__PYWRY_AUTH__;
      if (!authData) {
        return { authenticated: false };
      }
      return {
        authenticated: true,
        user_id: authData.user_id || null,
        roles: authData.roles || [],
        token_type: authData.token_type || 'Bearer'
      };
    },

    /**
     * Check if the user is currently authenticated.
     * @returns {boolean}
     */
    isAuthenticated: function() {
      return !!window.__PYWRY_AUTH__;
    },

    /**
     * Initiate a login flow.
     * In deploy mode, navigates to /auth/login.
     * In native mode, sends a login request event to the backend.
     */
    login: function() {
      if (window.pywry && window.pywry.sendEvent) {
        window.pywry.sendEvent('auth:login-request', {});
      } else {
        // Fallback: navigate to login URL
        window.location.href = '/auth/login';
      }
    },

    /**
     * Initiate a logout flow.
     * In deploy mode, posts to /auth/logout.
     * In native mode, sends a logout event to the backend.
     */
    logout: function() {
      if (window.pywry && window.pywry.sendEvent) {
        window.pywry.sendEvent('auth:logout-request', {});
      } else {
        // Fallback: POST to logout endpoint
        fetch('/auth/logout', { method: 'POST', credentials: 'same-origin' })
          .then(function() {
            window.__PYWRY_AUTH__ = null;
            window.pywry.auth._notifyStateChange();
            window.location.reload();
          })
          .catch(function(err) {
            console.error('Logout failed:', err);
          });
      }
    },

    /**
     * Register a callback for authentication state changes.
     * @param {function} callback - Called with the new auth state
     */
    onAuthStateChange: function(callback) {
      if (typeof callback === 'function') {
        this._stateChangeHandlers.push(callback);
      }
    },

    /**
     * Notify all state change handlers.
     * @private
     */
    _notifyStateChange: function() {
      var state = this.getState();
      for (var i = 0; i < this._stateChangeHandlers.length; i++) {
        try {
          this._stateChangeHandlers[i](state);
        } catch (e) {
          console.error('Auth state change handler error:', e);
        }
      }
    }
  };

  // Listen for auth events from the backend
  if (window.pywry && window.pywry.on) {
    window.pywry.on('auth:token-refresh', function(data) {
      if (window.__PYWRY_AUTH__) {
        window.__PYWRY_AUTH__.token_type = data.token_type || window.__PYWRY_AUTH__.token_type;
      }
      window.pywry.auth._notifyStateChange();
    });

    window.pywry.on('auth:logout', function() {
      window.__PYWRY_AUTH__ = null;
      window.pywry.auth._notifyStateChange();
    });

    window.pywry.on('auth:state-changed', function(data) {
      if (data && data.authenticated) {
        window.__PYWRY_AUTH__ = {
          user_id: data.user_id,
          roles: data.roles || [],
          token_type: data.token_type || 'Bearer'
        };
      } else {
        window.__PYWRY_AUTH__ = null;
      }
      window.pywry.auth._notifyStateChange();
    });
  }

  // Dispatch custom DOM event for framework integration
  document.addEventListener('DOMContentLoaded', function() {
    if (window.__PYWRY_AUTH__) {
      document.dispatchEvent(new CustomEvent('pywry:auth-ready', {
        detail: window.pywry.auth.getState()
      }));
    }
  });
})();
