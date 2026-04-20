var _TV_LAYOUT_INDEX_KEY = '__pywry_tvchart_layout_index_v1';
var _TV_SETTINGS_DEFAULT_TEMPLATE_KEY = '__pywry_tvchart_settings_default_template_v1';
var _TV_SETTINGS_CUSTOM_TEMPLATE_KEY = '__pywry_tvchart_settings_custom_template_v1';
var _TV_LAYOUT_ACTIVE_STATE = window.__PYWRY_TVCHART_LAYOUT_ACTIVE__ || {};
window.__PYWRY_TVCHART_LAYOUT_ACTIVE__ = _TV_LAYOUT_ACTIVE_STATE;
var _TV_LAYOUT_MEMORY_STORE = window.__PYWRY_TVCHART_LAYOUT_MEMORY_STORE__ || {};
window.__PYWRY_TVCHART_LAYOUT_MEMORY_STORE__ = _TV_LAYOUT_MEMORY_STORE;
var _TV_STORAGE_ADAPTER_CACHE = window.__PYWRY_TVCHART_STORAGE_ADAPTER_CACHE__ || {};
window.__PYWRY_TVCHART_STORAGE_ADAPTER_CACHE__ = _TV_STORAGE_ADAPTER_CACHE;
var _TV_STORAGE_ALLOWED_BACKENDS = {
    localStorage: true,
    memory: true,
    config: true,
    path: true,
    adapter: true,
    server: true,
};
var _TV_STORAGE_MAX_KEY_LENGTH = 256;
var _TV_STORAGE_MAX_VALUE_LENGTH = 2 * 1024 * 1024;

function _tvSanitizeStorageToken(rawValue, fallback, maxLength) {
    var s = String(rawValue || '').trim();
    if (!s) return fallback;
    if (s.length > maxLength) s = s.slice(0, maxLength);
    if (!/^[A-Za-z0-9._:/\\-]+$/.test(s)) return fallback;
    return s;
}

function _tvNormalizeStorageConfig(inputCfg) {
    var cfg = inputCfg && typeof inputCfg === 'object' ? inputCfg : {};
    var backend = String(cfg.backend || cfg.mode || 'localStorage').trim();
    if (!_TV_STORAGE_ALLOWED_BACKENDS[backend]) backend = 'localStorage';
    return {
        backend: backend,
        path: _tvSanitizeStorageToken(cfg.path, '', 512),
        namespace: _tvSanitizeStorageToken(cfg.namespace, 'pywry.tvchart', 128),
        adapter: _tvSanitizeStorageToken(cfg.adapter, '', 128),
    };
}

function _tvLayoutDataKey(layoutId) {
    return '__pywry_tvchart_layout_data_v1_' + String(layoutId);
}

function _tvStorageConfig(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId || 'main'];
    var payload = entry && entry.payload ? entry.payload : {};
    var cfg = payload && payload.storage && typeof payload.storage === 'object' ? payload.storage : {};
    return _tvNormalizeStorageConfig(cfg);
}

function _tvStorageNamespace(chartId) {
    var cfg = _tvStorageConfig(chartId);
    if (cfg.backend === 'config') {
        return 'config:' + (cfg.path || '~/.config/pywry/tvchart');
    }
    if (cfg.backend === 'path') {
        return 'path:' + (cfg.path || cfg.namespace || 'pywry.tvchart');
    }
    return cfg.namespace || 'pywry.tvchart';
}

function _tvBuildNamespacedLocalStorageAdapter(namespace) {
    namespace = _tvSanitizeStorageToken(namespace, 'pywry.tvchart', 128);
    function k(key) {
        key = String(key || '');
        if (key.length > _TV_STORAGE_MAX_KEY_LENGTH) key = key.slice(0, _TV_STORAGE_MAX_KEY_LENGTH);
        return namespace + ':' + key;
    }
    return {
        getItem: function(key) {
            try {
                return window.localStorage.getItem(k(key));
            } catch (e) {
                return null;
            }
        },
        setItem: function(key, value) {
            try {
                window.localStorage.setItem(k(key), value);
            } catch (e) {}
        },
        removeItem: function(key) {
            try {
                window.localStorage.removeItem(k(key));
            } catch (e) {}
        },
    };
}

function _tvBuildMemoryAdapter(namespace) {
    namespace = _tvSanitizeStorageToken(namespace, 'pywry.tvchart', 128);
    var bucket = _TV_LAYOUT_MEMORY_STORE[namespace] || {};
    _TV_LAYOUT_MEMORY_STORE[namespace] = bucket;
    return {
        getItem: function(key) {
            key = String(key || '');
            return Object.prototype.hasOwnProperty.call(bucket, key) ? bucket[key] : null;
        },
        setItem: function(key, value) {
            bucket[String(key || '')] = value;
        },
        removeItem: function(key) {
            delete bucket[String(key || '')];
        },
    };
}

function _tvBuildServerAdapter(chartId, namespace) {
    namespace = _tvSanitizeStorageToken(namespace, 'pywry.tvchart', 128);
    var bucket = _TV_LAYOUT_MEMORY_STORE[namespace] || {};
    _TV_LAYOUT_MEMORY_STORE[namespace] = bucket;

    // Pre-seed from payload.storage.preload
    var entry = window.__PYWRY_TVCHARTS__[chartId || 'main'];
    var payload = entry && entry.payload ? entry.payload : {};
    var preload = payload && payload.storage && payload.storage.preload;
    if (preload && typeof preload === 'object') {
        var keys = Object.keys(preload);
        for (var i = 0; i < keys.length; i++) {
            bucket[keys[i]] = preload[keys[i]];
        }
    }

    return {
        getItem: function(key) {
            key = String(key || '');
            return Object.prototype.hasOwnProperty.call(bucket, key) ? bucket[key] : null;
        },
        setItem: function(key, value) {
            key = String(key || '');
            bucket[key] = value;
            if (window.pywry) {
                window.pywry.emit('tvchart:storage-set', {
                    chartId: chartId || 'main',
                    key: key,
                    value: value,
                });
            }
        },
        removeItem: function(key) {
            key = String(key || '');
            delete bucket[key];
            if (window.pywry) {
                window.pywry.emit('tvchart:storage-remove', {
                    chartId: chartId || 'main',
                    key: key,
                });
            }
        },
    };
}

function _tvStorageAdapter(chartId) {
    chartId = chartId || 'main';
    if (_TV_STORAGE_ADAPTER_CACHE[chartId]) return _TV_STORAGE_ADAPTER_CACHE[chartId];

    var cfg = _tvStorageConfig(chartId);
    var namespace = _tvStorageNamespace(chartId);
    var backend = cfg.backend;
    var adapter = null;

    if (backend === 'memory') {
        adapter = _tvBuildMemoryAdapter(namespace);
    } else if (backend === 'server') {
        adapter = _tvBuildServerAdapter(chartId, namespace);
    } else if (backend === 'config' || backend === 'path') {
        adapter = _tvBuildNamespacedLocalStorageAdapter(namespace);
    } else if (backend === 'adapter') {
        var adapters = window.__PYWRY_TVCHART_STORAGE_ADAPTERS__ || {};
        var named = null;
        if (cfg.adapter && Object.prototype.hasOwnProperty.call(adapters, cfg.adapter)) {
            named = adapters[cfg.adapter];
        }
        if (named && typeof named.getItem === 'function' && typeof named.setItem === 'function') {
            adapter = named;
        }
    }

    if (!adapter) {
        adapter = {
            getItem: function(key) {
                try {
                    return window.localStorage.getItem(String(key || ''));
                } catch (e) {
                    return null;
                }
            },
            setItem: function(key, value) {
                try {
                    window.localStorage.setItem(String(key || ''), value);
                } catch (e) {}
            },
            removeItem: function(key) {
                try {
                    window.localStorage.removeItem(String(key || ''));
                } catch (e) {}
            },
        };
    }

    _TV_STORAGE_ADAPTER_CACHE[chartId] = adapter;
    return adapter;
}

function _tvStorageGet(chartId, key) {
    try {
        var v = _tvStorageAdapter(chartId).getItem(key);
        if (v == null) return null;
        if (typeof v !== 'string') return null;
        if (v.length > _TV_STORAGE_MAX_VALUE_LENGTH) return null;
        return v;
    } catch (e) {
        return null;
    }
}

function _tvStorageSet(chartId, key, value) {
    try {
        if (typeof value !== 'string') value = String(value || '');
        if (value.length > _TV_STORAGE_MAX_VALUE_LENGTH) return;
        _tvStorageAdapter(chartId).setItem(key, value);
    } catch (e) {}
}

function _tvStorageRemove(chartId, key) {
    try {
        _tvStorageAdapter(chartId).removeItem(key);
    } catch (e) {}
}

function _tvLayoutActiveState(chartId) {
    chartId = chartId || 'main';
    if (!_TV_LAYOUT_ACTIVE_STATE[chartId]) {
        _TV_LAYOUT_ACTIVE_STATE[chartId] = {
            id: '',
            name: '',
        };
    }
    return _TV_LAYOUT_ACTIVE_STATE[chartId];
}

function _tvLayoutSetActive(chartId, row) {
    var st = _tvLayoutActiveState(chartId);
    if (row && row.id) {
        st.id = String(row.id || '');
        st.name = String(row.name || '').trim();
    } else {
        st.id = '';
        st.name = '';
    }
    _tvRefreshSaveMenu(chartId);
}

function _tvLayoutRenameById(chartId, layoutId, nextName) {
    var name = String(nextName || '').replace(/\s+/g, ' ').trim();
    if (!name) return null;

    var index = _tvLayoutLoadIndex(chartId);
    var out = [];
    var found = null;
    for (var i = 0; i < index.length; i++) {
        var row = index[i] || {};
        if (String(row.id || '') === String(layoutId || '')) {
            row.name = name;
            row.savedAt = Date.now();
            found = row;
        }
        out.push(row);
    }
    if (!found) return null;

    out.sort(function(a, b) {
        return Number(b.savedAt || 0) - Number(a.savedAt || 0);
    });
    _tvLayoutSaveIndex(out.slice(0, 200), chartId);
    return found;
}

function _tvLayoutDeleteById(chartId, layoutId) {
    var id = String(layoutId || '');
    if (!id) return false;
    var index = _tvLayoutLoadIndex(chartId);
    var out = [];
    var removed = false;
    for (var i = 0; i < index.length; i++) {
        var row = index[i] || {};
        if (String(row.id || '') === id) {
            removed = true;
            continue;
        }
        out.push(row);
    }
    if (!removed) return false;
    _tvLayoutSaveIndex(out.slice(0, 200), chartId);
    _tvStorageRemove(chartId, _tvLayoutDataKey(id));
    var st = _tvLayoutActiveState(chartId);
    if (String(st.id || '') === id) {
        _tvLayoutSetActive(chartId, null);
    }
    return true;
}

function _tvRefreshSaveMenu(chartId) {
    chartId = chartId || 'main';
    var mainBtn = _tvScopedById(chartId, 'tvchart-save');
    var menu = _tvScopedById(chartId, 'tvchart-save-menu');
    var state = _tvLayoutActiveState(chartId);
    var activeName = String(state.name || '').trim();

    if (mainBtn) {
        var label = mainBtn.querySelector('.tvchart-save-label');
        if (label) {
            label.textContent = activeName || 'Layout';
        }
        mainBtn.setAttribute('data-tooltip', activeName ? ('Save layout "' + activeName + '"') : 'Save layout');
    }

    if (!menu) return;
    var saveItem = menu.querySelector('[data-action="save-layout"] .tvchart-save-menu-text');
    var copyItem = menu.querySelector('[data-action="make-copy"]');
    var renameItem = menu.querySelector('[data-action="rename-layout"]');
    var sep = menu.querySelector('.tvchart-save-menu-sep');

    if (saveItem) {
        saveItem.textContent = activeName ? ('Save layout "' + activeName + '"') : 'Save layout';
    }

    var hasActive = !!(state.id && activeName);
    if (copyItem) copyItem.style.display = hasActive ? '' : 'none';
    if (renameItem) renameItem.style.display = hasActive ? '' : 'none';
    if (sep) sep.style.display = hasActive ? '' : 'none';
}

function _tvLoadSettingsDefaultTemplateId(chartId) {
    try {
        var v = _tvStorageGet(chartId, _TV_SETTINGS_DEFAULT_TEMPLATE_KEY);
        return v === 'custom' ? 'custom' : 'factory';
    } catch (e) {
        return 'factory';
    }
}

function _tvSaveSettingsDefaultTemplateId(templateId, chartId) {
    try {
        _tvStorageSet(chartId, _TV_SETTINGS_DEFAULT_TEMPLATE_KEY, templateId === 'custom' ? 'custom' : 'factory');
    } catch (e) {}
}

function _tvLoadCustomSettingsTemplate(chartId) {
    try {
        var raw = _tvStorageGet(chartId, _TV_SETTINGS_CUSTOM_TEMPLATE_KEY);
        if (!raw) return null;
        var parsed = JSON.parse(raw);
        return parsed && typeof parsed === 'object' ? parsed : null;
    } catch (e) {
        return null;
    }
}

function _tvSaveCustomSettingsTemplate(settings, chartId) {
    try {
        _tvStorageSet(chartId, _TV_SETTINGS_CUSTOM_TEMPLATE_KEY, JSON.stringify(settings || {}));
    } catch (e) {}
}

function _tvClearCustomSettingsTemplate(chartId) {
    try {
        _tvStorageRemove(chartId, _TV_SETTINGS_CUSTOM_TEMPLATE_KEY);
    } catch (e) {}
}

function _tvLayoutLoadIndex(chartId) {
    try {
        var raw = _tvStorageGet(chartId, _TV_LAYOUT_INDEX_KEY);
        if (!raw) return [];
        var parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
        return [];
    }
}

function _tvLayoutSaveIndex(index, chartId) {
    try {
        _tvStorageSet(chartId, _TV_LAYOUT_INDEX_KEY, JSON.stringify(index || []));
    } catch (e) {}
}

function _tvLayoutFindByName(chartId, name, index) {
    var target = String(name || '').trim().toLowerCase();
    if (!target) return null;
    var rows = Array.isArray(index) ? index : _tvLayoutLoadIndex(chartId);
    for (var i = 0; i < rows.length; i++) {
        var row = rows[i] || {};
        if (String(row.name || '').trim().toLowerCase() === target) {
            return row;
        }
    }
    return null;
}

function _tvLayoutPersist(chartId, name, layout) {
    if (!layout) return null;
    var now = Date.now();
    var title = String(name || '').trim() || ('Layout ' + new Date(now).toLocaleString());
    var index = _tvLayoutLoadIndex(chartId);
    var opts = arguments.length > 3 ? (arguments[3] || {}) : {};
    var overwriteExisting = opts.overwriteExisting !== false;
    var existing = overwriteExisting ? _tvLayoutFindByName(chartId, title, index) : null;
    var id = existing && existing.id
        ? existing.id
        : ('layout_' + now + '_' + Math.floor(Math.random() * 1000000));

    // Build a short summary of layout contents for the index
    var inds = Array.isArray(layout.indicators) ? layout.indicators : [];
    var draws = Array.isArray(layout.drawings) ? layout.drawings : [];
    // Deduplicate indicator names (grouped indicators share the same group)
    var seenGroups = {};
    var indNames = [];
    for (var k = 0; k < inds.length; k++) {
        var ind = inds[k] || {};
        if (ind.group) {
            if (seenGroups[ind.group]) continue;
            seenGroups[ind.group] = true;
            // Map to canonical name for display
            if (ind.type === 'bollinger-bands' || /^BB /.test(ind.name)) {
                indNames.push('BB ' + (ind.period || 20));
            } else {
                indNames.push(ind.name);
            }
        } else if (ind.name) {
            indNames.push(ind.name + (ind.period ? ' ' + ind.period : ''));
        }
    }
    var summary = indNames.length ? indNames.join(', ') : '';
    if (draws.length && summary) summary += ' + ' + draws.length + ' drawing' + (draws.length > 1 ? 's' : '');
    else if (draws.length) summary = draws.length + ' drawing' + (draws.length > 1 ? 's' : '');

    var entry = {
        id: id,
        chartId: chartId || 'main',
        name: title,
        savedAt: now,
        summary: summary || '',
    };

    var nextIndex = [];
    nextIndex.push(entry);
    for (var i = 0; i < index.length; i++) {
        var row = index[i] || {};
        if (String(row.id) === String(id)) continue;
        nextIndex.push(row);
    }

    _tvLayoutSaveIndex(nextIndex.slice(0, 200), chartId);
    try {
        _tvStorageSet(chartId, _tvLayoutDataKey(id), JSON.stringify(layout));
    } catch (e) {}

    entry.overwritten = !!existing;
    return entry;
}

function _tvLayoutLoad(layoutId, chartId) {
    try {
        var raw = _tvStorageGet(chartId, _tvLayoutDataKey(layoutId));
        if (!raw) return null;
        return JSON.parse(raw);
    } catch (e) {
        return null;
    }
}

function _tvDefaultLayoutName(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId || 'main'];
    var base = 'Layout';
    if (entry && entry.payload && entry.payload.title) {
        base = String(entry.payload.title);
    } else if (entry && entry.payload && entry.payload.series && entry.payload.series[0] && entry.payload.series[0].seriesId) {
        base = String(entry.payload.series[0].seriesId);
    }
    return base;
}

function _tvResolveToastContainer(chartId) {
    var entry = window.__PYWRY_TVCHARTS__[chartId || 'main'];
    if (entry && entry.container && entry.container.closest) {
        return entry.container.closest('.pywry-widget') || entry.container;
    }
    return document.querySelector('.pywry-widget') || document.body;
}

function _tvNotify(type, message, title, chartId) {
    var payload = {
        type: type || 'info',
        message: String(message || ''),
    };
    if (title) payload.title = String(title);

    if (window.pywry && typeof window.pywry.emit === 'function') {
        try {
            window.pywry.emit('pywry:alert', payload);
            return;
        } catch (e) {}
    }

    if (window.PYWRY_TOAST && typeof window.PYWRY_TOAST.show === 'function') {
        window.PYWRY_TOAST.show(_tvMerge(payload, {
            container: _tvResolveToastContainer(chartId),
        }));
    }
}

function _tvCloseLayoutPicker(chartId) {
    var widget = _tvResolveToastContainer(chartId);
    if (!widget || !widget.querySelector) return;
    var existing = widget.querySelector('.tvchart-layout-modal-overlay[data-chart-id="' + (chartId || 'main') + '"]');
    if (existing && existing.parentNode) {
        existing.parentNode.removeChild(existing);
    }
}

function _tvLayoutMetaLabel(row) {
    row = row || {};
    var parts = [];
    if (row.summary) parts.push(String(row.summary));
    var dt = new Date(row.savedAt || Date.now()).toLocaleString();
    parts.push(dt);
    return parts.join(' \u2022 ');
}

function _tvSortLayouts(rows, mode) {
    var sorted = (rows || []).slice();
    if (mode === 'name_asc') {
        sorted.sort(function(a, b) {
            return String(a.name || '').localeCompare(String(b.name || ''));
        });
        return sorted;
    }
    if (mode === 'name_desc') {
        sorted.sort(function(a, b) {
            return String(b.name || '').localeCompare(String(a.name || ''));
        });
        return sorted;
    }
    if (mode === 'oldest') {
        sorted.sort(function(a, b) {
            return Number(a.savedAt || 0) - Number(b.savedAt || 0);
        });
        return sorted;
    }
    sorted.sort(function(a, b) {
        return Number(b.savedAt || 0) - Number(a.savedAt || 0);
    });
    return sorted;
}

function _tvBuildLayoutModalShell(chartId, titleText, options) {
    var widget = _tvResolveToastContainer(chartId);
    if (!widget) return null;
    options = options || {};

    _tvCloseLayoutPicker(chartId);

    if (window.getComputedStyle(widget).position === 'static') {
        widget.style.position = 'relative';
    }

    var overlay = document.createElement('div');
    overlay.className = 'tvchart-layout-modal-overlay';
    overlay.setAttribute('data-chart-id', chartId || 'main');

    var panel = document.createElement('div');
    panel.className = 'tvchart-layout-modal-panel';
    if (options.variant === 'save') {
        panel.classList.add('tvchart-layout-modal-panel-save');
    } else if (options.variant === 'open') {
        panel.classList.add('tvchart-layout-modal-panel-open');
    }

    var header = document.createElement('div');
    header.className = 'tvchart-layout-modal-header';

    var title = document.createElement('div');
    title.className = 'tvchart-layout-modal-title';
    title.textContent = titleText || 'Layouts';

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.innerHTML = '<svg viewBox="0 0 16 16"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>';
    closeBtn.className = 'tvchart-layout-modal-close';
    closeBtn.setAttribute('aria-label', 'Close');

    header.appendChild(title);
    header.appendChild(closeBtn);
    panel.appendChild(header);

    var body = document.createElement('div');
    body.className = 'tvchart-layout-modal-body';
    panel.appendChild(body);
    overlay.appendChild(panel);

    function closeModal() {
        _tvCloseLayoutPicker(chartId);
    }

    closeBtn.addEventListener('click', closeModal);
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
            closeModal();
        }
    });
    overlay.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            e.preventDefault();
            closeModal();
        }
    });

    widget.appendChild(overlay);

    return {
        overlay: overlay,
        panel: panel,
        header: header,
        title: title,
        closeBtn: closeBtn,
        body: body,
        close: closeModal,
    };
}

function _tvOpenLayoutPicker(chartId, index) {
    chartId = chartId || 'main';
    var modal = _tvBuildLayoutModalShell(chartId, 'Layouts', { variant: 'open' });
    if (!modal) return;

    var topRow = document.createElement('div');
    topRow.className = 'tvchart-layout-search-row';

    var searchWrap = document.createElement('div');
    searchWrap.className = 'tvchart-layout-search-wrap';

    var searchIcon = document.createElement('span');
    searchIcon.className = 'tvchart-layout-search-icon';
    searchIcon.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="7" cy="7" r="4.8"/><line x1="10.5" y1="10.5" x2="14" y2="14"/></svg>';

    var searchInput = document.createElement('input');
    searchInput.className = 'tvchart-layout-search-input';
    searchInput.type = 'text';
    searchInput.placeholder = 'Search';

    searchWrap.appendChild(searchIcon);
    searchWrap.appendChild(searchInput);
    topRow.appendChild(searchWrap);
    modal.body.appendChild(topRow);

    var listTitle = document.createElement('div');
    listTitle.className = 'tvchart-layout-list-title';
    var titleText = document.createElement('span');
    titleText.textContent = 'LAYOUT NAME';
    var sortBtn = document.createElement('button');
    sortBtn.type = 'button';
    sortBtn.className = 'tvchart-layout-sort-btn';
    listTitle.appendChild(titleText);
    listTitle.appendChild(sortBtn);
    modal.body.appendChild(listTitle);

    var list = document.createElement('div');
    list.className = 'tvchart-layout-list';
    list.tabIndex = 0;
    modal.body.appendChild(list);

    var selectedId = index[0] ? String(index[0].id) : '';
    var filteredRows = [];
    var sortModes = ['newest', 'oldest', 'name_asc', 'name_desc'];
    var sortModeIdx = 0;

    function updateSortButton() {
        var mode = sortModes[sortModeIdx] || 'newest';
        if (mode === 'oldest') {
            sortBtn.textContent = '\u2191\u2261';
            sortBtn.title = 'Sort: Oldest';
            return;
        }
        if (mode === 'name_asc') {
            sortBtn.textContent = 'A\u2192Z';
            sortBtn.title = 'Sort: Name A-Z';
            return;
        }
        if (mode === 'name_desc') {
            sortBtn.textContent = 'Z\u2192A';
            sortBtn.title = 'Sort: Name Z-A';
            return;
        }
        sortBtn.textContent = '\u2193\u2261';
        sortBtn.title = 'Sort: Newest';
    }

    function applySelection(rowEl, active) {
        if (!rowEl || !rowEl.classList) return;
        if (active) rowEl.classList.add('selected');
        else rowEl.classList.remove('selected');
    }

    function findSelectedIndex() {
        for (var i = 0; i < filteredRows.length; i++) {
            if (String(filteredRows[i].id) === String(selectedId)) {
                return i;
            }
        }
        return -1;
    }

    function moveSelection(delta) {
        if (!filteredRows.length) return;
        var idx = findSelectedIndex();
        if (idx < 0) idx = 0;
        idx = Math.max(0, Math.min(filteredRows.length - 1, idx + delta));
        selectedId = String(filteredRows[idx].id);
        var rows = list.querySelectorAll('[data-layout-id]');
        for (var r = 0; r < rows.length; r++) {
            var active = rows[r].getAttribute('data-layout-id') === selectedId;
            applySelection(rows[r], active);
            if (active && rows[r].scrollIntoView) {
                rows[r].scrollIntoView({ block: 'nearest' });
            }
        }
    }

    function renderList() {
        var query = String(searchInput.value || '').trim().toLowerCase();
        list.innerHTML = '';
        var source = _tvSortLayouts(index, sortModes[sortModeIdx] || 'newest');
        filteredRows = source.filter(function(row) {
            if (!query) return true;
            var label = [
                String(row.name || '').toLowerCase(),
                String(row.symbol || '').toLowerCase(),
                String(row.timeframe || '').toLowerCase(),
                _tvLayoutMetaLabel(row).toLowerCase(),
            ].join(' ');
            return label.indexOf(query) !== -1;
        });

        if (!filteredRows.length) {
            var empty = document.createElement('div');
            empty.className = 'tvchart-layout-empty';
            empty.textContent = 'No matching layouts.';
            list.appendChild(empty);
            return;
        }

        if (!selectedId || !filteredRows.some(function(r) { return String(r.id) === selectedId; })) {
            selectedId = String(filteredRows[0].id);
        }

        for (var i = 0; i < filteredRows.length; i++) {
            var row = filteredRows[i];
            var item = document.createElement('div');
            item.className = 'tvchart-layout-item';
            if (i === filteredRows.length - 1) {
                item.classList.add('tvchart-layout-item-last');
            }
            item.setAttribute('data-layout-id', row.id);
            item.tabIndex = 0;

            var favBtn = document.createElement('button');
            favBtn.type = 'button';
            favBtn.className = 'tvchart-layout-item-fav';
            favBtn.setAttribute('aria-label', 'Favorite layout');
            favBtn.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M8 1.8l2 4.05 4.47.65-3.24 3.16.76 4.46L8 12.1 4.01 14.12l.76-4.46L1.53 6.5l4.47-.65z"/></svg>';

            var main = document.createElement('div');
            main.className = 'tvchart-layout-item-main';

            var n = document.createElement('div');
            n.className = 'tvchart-layout-item-name';
            n.textContent = row.name || 'Untitled layout';

            var m = document.createElement('div');
            m.className = 'tvchart-layout-item-meta';
            m.textContent = _tvLayoutMetaLabel(row);

            main.appendChild(n);
            main.appendChild(m);

            var deleteBtn = document.createElement('button');
            deleteBtn.type = 'button';
            deleteBtn.className = 'tvchart-layout-item-delete';
            deleteBtn.setAttribute('aria-label', 'Delete layout');
            deleteBtn.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.2 4.3h9.6"/><path d="M6.3 4.3V3.1h3.4v1.2"/><path d="M4.5 4.3l.6 8.1h5.8l.6-8.1"/></svg>';

            item.appendChild(favBtn);
            item.appendChild(main);
            item.appendChild(deleteBtn);
            applySelection(item, String(row.id) === selectedId);

            item.addEventListener('click', function(e) {
                selectedId = e.currentTarget.getAttribute('data-layout-id') || '';
                var rows = list.querySelectorAll('[data-layout-id]');
                for (var r = 0; r < rows.length; r++) {
                    applySelection(rows[r], rows[r].getAttribute('data-layout-id') === selectedId);
                }
            });

            item.addEventListener('dblclick', function(e) {
                selectedId = e.currentTarget.getAttribute('data-layout-id') || '';
                doOpen();
            });

            item.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    selectedId = e.currentTarget.getAttribute('data-layout-id') || '';
                    doOpen();
                }
            });

            favBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
            });

            deleteBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                var rowEl = e.currentTarget && e.currentTarget.parentElement ? e.currentTarget.parentElement : null;
                var id = rowEl ? (rowEl.getAttribute('data-layout-id') || '') : '';
                if (!id) return;
                _tvLayoutDeleteById(chartId, id);
                for (var x = index.length - 1; x >= 0; x--) {
                    if (String(index[x] && index[x].id || '') === String(id)) {
                        index.splice(x, 1);
                    }
                }
                if (selectedId === String(id)) {
                    selectedId = index[0] ? String(index[0].id) : '';
                }
                renderList();
            });

            list.appendChild(item);
        }
    }

    function doOpen() {
        if (!selectedId) return;
        var selected = null;
        for (var j = 0; j < index.length; j++) {
            if (String(index[j].id) === String(selectedId)) {
                selected = index[j];
                break;
            }
        }
        if (!selected) {
            _tvNotify('error', 'Layout not found.', 'Layout', chartId);
            return;
        }
        var layout = _tvLayoutLoad(selected.id, chartId);
        if (!layout) {
            _tvNotify('error', 'Saved layout data is unavailable.', 'Layout', chartId);
            modal.close();
            return;
        }
        _tvApplyLayout(chartId, layout);
        _tvLayoutSetActive(chartId, selected);
        modal.close();
    }

    searchInput.addEventListener('input', renderList);
    sortBtn.addEventListener('click', function() {
        sortModeIdx = (sortModeIdx + 1) % sortModes.length;
        updateSortButton();
        renderList();
    });
    searchInput.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            moveSelection(1);
            return;
        }
        if (e.key === 'ArrowUp') {
            e.preventDefault();
            moveSelection(-1);
            return;
        }
        if (e.key === 'Enter') {
            e.preventDefault();
            doOpen();
        }
    });
    list.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            moveSelection(1);
            return;
        }
        if (e.key === 'ArrowUp') {
            e.preventDefault();
            moveSelection(-1);
            return;
        }
        if (e.key === 'Enter') {
            e.preventDefault();
            doOpen();
        }
    });

    updateSortButton();
    renderList();
    searchInput.focus();
}

function _tvPromptSaveLayout(chartId, fallbackName, onSave) {
    chartId = chartId || 'main';
    var modal = _tvBuildLayoutModalShell(chartId, 'Save New Chart Layout', { variant: 'save' });
    if (!modal) return;

    var hint = document.createElement('div');
    hint.className = 'tvchart-layout-hint';
    hint.textContent = 'Enter a new chart layout name:';
    modal.body.appendChild(hint);

    var nameInput = document.createElement('input');
    nameInput.className = 'tvchart-layout-save-input';
    nameInput.type = 'text';
    nameInput.value = String(fallbackName || '');
    nameInput.placeholder = 'Layout name';
    nameInput.maxLength = 120;
    modal.body.appendChild(nameInput);

    var errorText = document.createElement('div');
    errorText.className = 'tvchart-layout-error';
    modal.body.appendChild(errorText);

    var duplicateText = document.createElement('div');
    duplicateText.className = 'tvchart-layout-duplicate';
    modal.body.appendChild(duplicateText);

    var btnRow = document.createElement('div');
    btnRow.className = 'tvchart-layout-btn-row';

    function makeBtn(label, primary) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = label;
        btn.className = primary ? 'tvchart-layout-btn tvchart-layout-btn-primary' : 'tvchart-layout-btn';
        return btn;
    }

    var cancelBtn = makeBtn('Cancel', false);
    var saveBtn = makeBtn('Save', true);
    btnRow.appendChild(cancelBtn);
    btnRow.appendChild(saveBtn);
    modal.body.appendChild(btnRow);

    function updateSaveEnabled() {
        var name = String(nameInput.value || '').replace(/\s+/g, ' ').trim();
        saveBtn.disabled = !name;
    }

    function updateDuplicateHint() {
        var name = String(nameInput.value || '').trim();
        if (!name) {
            duplicateText.textContent = '';
            return;
        }
        var existing = _tvLayoutFindByName(chartId, name);
        if (!existing) {
            duplicateText.textContent = '';
            return;
        }
        duplicateText.textContent = 'An existing layout with this name will be updated.';
    }

    function submitSave() {
        var name = String(nameInput.value || '').replace(/\s+/g, ' ').trim();
        if (!name) {
            errorText.textContent = 'Please provide a layout name.';
            nameInput.focus();
            return;
        }
        if (name.length > 120) {
            errorText.textContent = 'Layout name must be 120 characters or fewer.';
            nameInput.focus();
            return;
        }
        errorText.textContent = '';
        if (typeof onSave === 'function') {
            onSave(name);
        }
        modal.close();
    }

    cancelBtn.addEventListener('click', function() { modal.close(); });
    saveBtn.addEventListener('click', submitSave);
    nameInput.addEventListener('input', function() {
        updateSaveEnabled();
        updateDuplicateHint();
    });
    nameInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            submitSave();
        }
    });

    updateSaveEnabled();
    updateDuplicateHint();
    nameInput.focus();
    nameInput.select();
}

function _tvApplyLayout(chartId, layout) {
    var entry = window.__PYWRY_TVCHARTS__[chartId || 'main'];
    if (!entry || !entry.chart || !layout) return false;

    // Suppress undo tracking during layout restore
    window.__PYWRY_UNDO_SUPPRESS__ = true;

    // Replace drawings.
    var ds = window.__PYWRY_DRAWINGS__[chartId] || _tvEnsureDrawingLayer(chartId);
    if (ds) {
        var srcDrawings = Array.isArray(layout.drawings) ? layout.drawings : [];
        ds.drawings = srcDrawings.map(function(d) { return _tvMerge({}, d || {}); });
        _tvRenderDrawings(chartId);
    }

    // Replace indicators for this chart.
    var activeKeys = Object.keys(_activeIndicators || {});
    var toRemove = [];
    for (var i = 0; i < activeKeys.length; i++) {
        var sid = activeKeys[i];
        var info = _activeIndicators[sid];
        if (info && info.chartId === chartId) toRemove.push(sid);
    }
    for (var r = 0; r < toRemove.length; r++) {
        _tvRemoveIndicator(toRemove[r]);
    }

    var inds = Array.isArray(layout.indicators) ? layout.indicators : [];
    var restoredGroups = {};
    for (var j = 0; j < inds.length; j++) {
        var ind = inds[j] || {};
        if (!ind.name) continue;

        // Grouped indicators (e.g. Bollinger Bands): only add once per group.
        if (ind.group) {
            if (restoredGroups[ind.group]) continue;
            restoredGroups[ind.group] = true;
            // Map individual band names back to canonical group name
            var groupName = ind.name;
            if (ind.type === 'bollinger-bands' || /^BB (Basis|Upper|Lower)$/.test(ind.name)) {
                groupName = 'Bollinger Bands';
            }
            _tvAddIndicator({
                name: groupName,
                defaultPeriod: ind.period,
                _color: ind.color || undefined,
                _multiplier: ind.multiplier,
                _maType: ind.maType,
                _offset: ind.offset,
                _source: ind.source,
            }, chartId);
            continue;
        }

        _tvAddIndicator({
            name: ind.name,
            defaultPeriod: ind.period,
            _color: ind.color || undefined,
            _fromIndex: ind.fromIndex != null ? ind.fromIndex : undefined,
            _toIndex: ind.toIndex != null ? ind.toIndex : undefined,
            _widthPercent: ind.widthPercent != null ? ind.widthPercent : undefined,
            _placement: ind.placement || undefined,
        }, chartId);
    }

    // Restore settings (colors, candle styles, crosshair, grid, etc.)
    if (layout.settings && typeof _tvApplySettingsToChart === 'function') {
        if (typeof persistSettings === 'function') {
            persistSettings(layout.settings);
        } else if (entry._chartPrefs) {
            // Manually persist the key prefs so they survive settings panel re-opens
            var s = layout.settings;
            entry._chartPrefs.crosshairEnabled = s['Crosshair-Enabled'] === true;
            entry._chartPrefs.crosshairColor = s['Crosshair-Color'] || entry._chartPrefs.crosshairColor;
            entry._chartPrefs.gridVisible = s['Grid lines'] !== 'Hidden';
            entry._chartPrefs.gridMode = s['Grid lines'] || 'Vert and horz';
            entry._chartPrefs.gridColor = s['Grid-Color'] || entry._chartPrefs.gridColor;
            entry._chartPrefs.backgroundColor = s['Background-Color'] || entry._chartPrefs.backgroundColor;
            entry._chartPrefs.textColor = s['Text-Color'] || entry._chartPrefs.textColor;
            entry._chartPrefs.linesColor = s['Lines-Color'] || entry._chartPrefs.linesColor;
            entry._chartPrefs.dayOfWeekOnLabels = s['Day of week on labels'] !== false;
            entry._chartPrefs.dateFormat = s['Date format'] || entry._chartPrefs.dateFormat;
            entry._chartPrefs.timeHoursFormat = s['Time hours format'] || entry._chartPrefs.timeHoursFormat;
            entry._chartPrefs.bodyVisible = s['Body'] !== false;
            entry._chartPrefs.bodyUpColor = s['Body-Up Color'] || entry._chartPrefs.bodyUpColor;
            entry._chartPrefs.bodyDownColor = s['Body-Down Color'] || entry._chartPrefs.bodyDownColor;
            entry._chartPrefs.bordersVisible = s['Borders'] !== false;
            entry._chartPrefs.bordersUpColor = s['Borders-Up Color'] || entry._chartPrefs.bordersUpColor;
            entry._chartPrefs.bordersDownColor = s['Borders-Down Color'] || entry._chartPrefs.bordersDownColor;
            entry._chartPrefs.wickVisible = s['Wick'] !== false;
            entry._chartPrefs.wickUpColor = s['Wick-Up Color'] || entry._chartPrefs.wickUpColor;
            entry._chartPrefs.wickDownColor = s['Wick-Down Color'] || entry._chartPrefs.wickDownColor;
        }
        _tvApplySettingsToChart(chartId, entry, layout.settings);
    }

    // visibleRange intentionally NOT restored — layouts are portable across charts

    window.__PYWRY_UNDO_SUPPRESS__ = false;
    return true;
}

function _tvPromptOpenLayout(chartId) {
    var index = _tvLayoutLoadIndex(chartId);
    _tvOpenLayoutPicker(chartId, index);
}

