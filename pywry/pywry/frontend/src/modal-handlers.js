/**
 * PyWry Modal Handlers
 *
 * Provides open/close/reset functionality for modal overlays.
 * Handles Escape key, overlay clicks, and form state preservation.
 */

(function () {
    'use strict';

    // Guard: only initialize once
    if (window.__PYWRY_MODAL_INIT__) return;
    window.__PYWRY_MODAL_INIT__ = true;

    // Ensure pywry namespace exists
    window.pywry = window.pywry || {};

    /**
     * Modal manager for PyWry modals.
     */
    window.pywry.modal = {
        /** Stack of open modal IDs (for proper Escape key handling) */
        _stack: [],

        /**
         * Open a modal by ID.
         * @param {string} id - The modal element ID.
         */
        open: function (id) {
            const modal = document.getElementById(id);
            if (!modal || !modal.classList.contains('pywry-modal-overlay')) {
                console.warn('[pywry.modal] Modal not found:', id);
                return;
            }

            // Store initial form values for reset
            this._storeInitialValues(modal);

            // Add to stack
            if (!this._stack.includes(id)) {
                this._stack.push(id);
            }

            // Show modal
            modal.classList.add('pywry-modal-open');
            document.body.classList.add('pywry-modal-body-locked');

            // Focus the modal container for accessibility
            const container = modal.querySelector('.pywry-modal-container');
            if (container) {
                container.setAttribute('tabindex', '-1');
                container.focus();
            }

            // Dispatch open event
            modal.dispatchEvent(new CustomEvent('modal:opened', {
                bubbles: true,
                detail: { modalId: id }
            }));
        },

        /**
         * Close a modal by ID.
         * @param {string} id - The modal element ID.
         * @param {Object} options - Close options.
         * @param {boolean} options.skipReset - If true, don't reset form values.
         */
        close: function (id, options) {
            options = options || {};
            const modal = document.getElementById(id);
            if (!modal) {
                console.warn('[pywry.modal] Modal not found:', id);
                return;
            }

            const resetOnClose = modal.dataset.resetOnClose !== 'false';
            const onCloseEvent = modal.dataset.onCloseEvent;

            // Reset form state if configured and not skipped
            if (resetOnClose && !options.skipReset) {
                this._resetForm(modal);
            }

            // Hide modal
            modal.classList.remove('pywry-modal-open');

            // Remove from stack
            this._stack = this._stack.filter(function (m) { return m !== id; });

            // Unlock body if no more modals open
            if (this._stack.length === 0) {
                document.body.classList.remove('pywry-modal-body-locked');
            }

            // Dispatch close event
            modal.dispatchEvent(new CustomEvent('modal:closed', {
                bubbles: true,
                detail: { modalId: id, wasReset: resetOnClose && !options.skipReset }
            }));

            // Emit custom on_close_event if configured
            if (onCloseEvent) {
                window.dispatchEvent(new CustomEvent(onCloseEvent, {
                    detail: { modalId: id }
                }));
            }
        },

        /**
         * Toggle a modal open/closed.
         * @param {string} id - The modal element ID.
         */
        toggle: function (id) {
            const modal = document.getElementById(id);
            if (!modal) return;

            if (modal.classList.contains('pywry-modal-open')) {
                this.close(id);
            } else {
                this.open(id);
            }
        },

        /**
         * Check if a modal is currently open.
         * @param {string} id - The modal element ID.
         * @returns {boolean}
         */
        isOpen: function (id) {
            const modal = document.getElementById(id);
            return modal ? modal.classList.contains('pywry-modal-open') : false;
        },

        /**
         * Store initial values for all form elements in the modal.
         * @param {HTMLElement} modal - The modal overlay element.
         * @private
         */
        _storeInitialValues: function (modal) {
            var inputs = modal.querySelectorAll('input, select, textarea');
            inputs.forEach(function (el) {
                if (el.type === 'checkbox' || el.type === 'radio') {
                    el.dataset.pywryInitialChecked = el.checked ? 'true' : 'false';
                } else {
                    el.dataset.pywryInitialValue = el.value;
                }
            });
        },

        /**
         * Reset all form elements in the modal to their initial values.
         * @param {HTMLElement} modal - The modal overlay element.
         * @private
         */
        _resetForm: function (modal) {
            var inputs = modal.querySelectorAll('input, select, textarea');
            inputs.forEach(function (el) {
                if (el.type === 'checkbox' || el.type === 'radio') {
                    var initialChecked = el.dataset.pywryInitialChecked;
                    if (initialChecked !== undefined) {
                        el.checked = initialChecked === 'true';
                    }
                } else {
                    var initialValue = el.dataset.pywryInitialValue;
                    if (initialValue !== undefined) {
                        el.value = initialValue;
                    } else {
                        el.value = '';
                    }
                }
            });
        },

        /**
         * Handle Escape key to close topmost modal.
         * @param {KeyboardEvent} e - The keyboard event.
         * @private
         */
        _handleEscape: function (e) {
            if (e.key !== 'Escape' || this._stack.length === 0) return;

            // Get topmost modal
            var topModalId = this._stack[this._stack.length - 1];
            var modal = document.getElementById(topModalId);

            if (modal && modal.dataset.closeEscape !== 'false') {
                e.preventDefault();
                this.close(topModalId);
            }
        },

        /**
         * Handle overlay click to close modal.
         * @param {MouseEvent} e - The click event.
         * @private
         */
        _handleOverlayClick: function (e) {
            // Only trigger if clicking the overlay itself, not the container
            if (!e.target.classList.contains('pywry-modal-overlay')) return;

            var modal = e.target;
            if (modal.dataset.closeOverlay !== 'false') {
                this.close(modal.id);
            }
        }
    };

    // Bind event handlers
    var modalManager = window.pywry.modal;

    // Escape key handler
    document.addEventListener('keydown', function (e) {
        modalManager._handleEscape(e);
    });

    // Overlay click handler (delegated)
    document.addEventListener('click', function (e) {
        modalManager._handleOverlayClick(e);
    });

    // Listen for modal:open:*, modal:close:*, modal:toggle:* custom events
    // These are dispatched by toolbar buttons with event="modal:open:my-modal"
    document.addEventListener('pywry:event', function (e) {
        var eventType = e.detail && e.detail.type;
        if (!eventType) return;

        // Parse modal events: modal:open:id, modal:close:id, modal:toggle:id
        var parts = eventType.split(':');
        if (parts[0] !== 'modal' || parts.length < 3) return;

        var action = parts[1];
        var modalId = parts.slice(2).join(':'); // Rejoin in case ID has colons

        if (action === 'open') {
            modalManager.open(modalId);
        } else if (action === 'close') {
            modalManager.close(modalId);
        } else if (action === 'toggle') {
            modalManager.toggle(modalId);
        }
    });

    // Expose for re-initialization (e.g., after hot reload)
    window.initModalHandlers = function () {
        // Handlers are already bound via delegation, nothing to reinit
    };

})();
