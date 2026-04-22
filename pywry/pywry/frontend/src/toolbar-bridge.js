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
                } else if (el.classList.contains('pywry-marquee')) {
                    type = 'marquee';
                    var items = {};
                    el.querySelectorAll('[data-ticker]').forEach(function(item) {
                        var ticker = item.getAttribute('data-ticker');
                        if (ticker && !(ticker in items)) {
                            items[ticker] = (item.textContent || '').trim();
                        }
                    });
                    value = { text: el.getAttribute('data-text') || '', items: items };
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
            // Never expose secret values via state getter
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
        } else if (el.classList.contains('pywry-marquee')) {
            var marqueeItems = {};
            el.querySelectorAll('[data-ticker]').forEach(function(item) {
                var t = item.getAttribute('data-ticker');
                if (t && !(t in marqueeItems)) {
                    marqueeItems[t] = (item.textContent || '').trim();
                }
            });
            return { text: el.getAttribute('data-text') || '', items: marqueeItems };
        }
        return null;
    }

    function setComponentValue(componentId, value, attrs) {
        var el = document.getElementById(componentId);
        if (!el) return false;

        if (el.classList && el.classList.contains('pywry-input-secret')) {
            console.warn('[PyWry] Cannot set SecretInput value via toolbar:set-value. Use the event handler instead.');
            return false;
        }

        if (attrs && typeof attrs === 'object') {
            Object.keys(attrs).forEach(function(attrName) {
                var attrValue = attrs[attrName];

                if (attrName === 'componentId' || attrName === 'toolbarId') return;

                switch (attrName) {
                    case 'label':
                    case 'text':
                        if (el.classList.contains('pywry-toolbar-button') || el.tagName === 'BUTTON') {
                            el.textContent = attrValue;
                        } else if (el.classList.contains('pywry-dropdown')) {
                            var textEl = el.querySelector('.pywry-dropdown-text');
                            if (textEl) textEl.textContent = attrValue;
                        } else if (el.classList.contains('pywry-checkbox') || el.classList.contains('pywry-toggle')) {
                            var labelEl = el.querySelector('.pywry-checkbox-label, .pywry-input-label');
                            if (labelEl) labelEl.textContent = attrValue;
                        } else if (el.classList.contains('pywry-tab-group')) {
                            var groupLabel = el.closest('.pywry-input-group');
                            if (groupLabel) {
                                var lbl = groupLabel.querySelector('.pywry-input-label');
                                if (lbl) lbl.textContent = attrValue;
                            }
                        } else {
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
                        if (attrValue) {
                            el.setAttribute('disabled', 'disabled');
                            el.classList.add('pywry-disabled');
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
                        if (el.classList.contains('pywry-toolbar-button') || el.tagName === 'BUTTON') {
                            var variants = ['primary', 'secondary', 'neutral', 'ghost', 'outline', 'danger', 'warning', 'icon'];
                            variants.forEach(function(v) {
                                el.classList.remove('pywry-btn-' + v);
                            });
                            if (attrValue && attrValue !== 'primary') {
                                el.classList.add('pywry-btn-' + attrValue);
                            }
                        }
                        break;

                    case 'size':
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
                        if (attrValue) {
                            el.setAttribute('data-tooltip', attrValue);
                        } else {
                            el.removeAttribute('data-tooltip');
                        }
                        break;

                    case 'data':
                        if (attrValue) {
                            el.setAttribute('data-data', JSON.stringify(attrValue));
                        } else {
                            el.removeAttribute('data-data');
                        }
                        break;

                    case 'event':
                        el.setAttribute('data-event', attrValue);
                        break;

                    case 'style':
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
                        if (typeof attrValue === 'string') {
                            attrValue.split(' ').forEach(function(cls) {
                                if (cls) el.classList.add(cls);
                            });
                        } else if (typeof attrValue === 'object') {
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
                        var checkbox = el.querySelector('input[type="checkbox"]') || (el.type === 'checkbox' ? el : null);
                        if (checkbox) {
                            checkbox.checked = !!attrValue;
                            if (attrValue) {
                                el.classList.add('pywry-toggle-checked');
                            } else {
                                el.classList.remove('pywry-toggle-checked');
                            }
                        }
                        break;

                    case 'selected':
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
                        var input = el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' ? el : el.querySelector('input, textarea');
                        if (input) {
                            input.setAttribute('placeholder', attrValue);
                        }
                        break;

                    case 'min':
                    case 'max':
                    case 'step':
                        var numInput = el.tagName === 'INPUT' ? el : el.querySelector('input[type="number"], input[type="range"]');
                        if (numInput) {
                            numInput.setAttribute(attrName, attrValue);
                        }
                        break;

                    case 'options':
                        break;

                    case 'value':
                        break;

                    default:
                        if (attrName.startsWith('data-')) {
                            el.setAttribute(attrName, attrValue);
                        } else {
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
            if (attrs && (attrs.start !== undefined || attrs.end !== undefined)) {
                var startInput = el.querySelector('input[data-range="start"]');
                var endInput = el.querySelector('input[data-range="end"]');
                var fill = el.querySelector('.pywry-range-track-fill');
                var startDisp = el.querySelector('.pywry-range-start-value');
                var endDisp = el.querySelector('.pywry-range-end-value');

                if (startInput && attrs.start !== undefined) startInput.value = attrs.start;
                if (endInput && attrs.end !== undefined) endInput.value = attrs.end;

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
            if (value !== undefined) {
                el.value = value;
                var display = el.nextElementSibling;
                if (display && display.classList.contains('pywry-range-value')) {
                    display.textContent = value;
                }
            }
            return true;
        }

        if (value !== undefined && 'value' in el) {
            el.value = value;
            return true;
        }

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
