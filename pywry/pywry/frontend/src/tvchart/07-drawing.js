// ---------------------------------------------------------------------------
// Drawing system — canvas overlay for interactive drawing tools
// ---------------------------------------------------------------------------

window.__PYWRY_DRAWINGS__ = window.__PYWRY_DRAWINGS__ || {};
// _activeTool is stored per chart on ds (drawing state), not as a global
var _drawPending = null;
var _drawSelectedIdx = -1;      // index into ds.drawings
var _drawSelectedChart = null;  // chartId of selected drawing
var _drawDragging = null;       // { anchor: 'p1'|'p2'|'body', startX, startY, origD }
var _drawDidDrag = false;       // true after a drag completes — suppresses next click
var _drawHoverIdx = -1;
var _drawIdCounter = 0;

// ---------------------------------------------------------------------------
// Global undo/redo stack — handles all chart mutations (drawings, indicators)
// Each entry: { undo: function(), redo: function(), label: string }
// ---------------------------------------------------------------------------
var _tvUndoStack = [];
var _tvRedoStack = [];
var _TV_UNDO_MAX = 100;

function _tvPushUndo(entry) {
    _tvUndoStack.push(entry);
    if (_tvUndoStack.length > _TV_UNDO_MAX) _tvUndoStack.shift();
    _tvRedoStack.length = 0;  // new action clears redo
}

function _tvPerformUndo() {
    if (_tvUndoStack.length === 0) return;
    var entry = _tvUndoStack.pop();
    try { entry.undo(); } catch(e) { console.warn('[pywry] undo failed:', e); }
    _tvRedoStack.push(entry);
}

function _tvPerformRedo() {
    if (_tvRedoStack.length === 0) return;
    var entry = _tvRedoStack.pop();
    try { entry.redo(); } catch(e) { console.warn('[pywry] redo failed:', e); }
    _tvUndoStack.push(entry);
}

// ---------------------------------------------------------------------------
// Tool-group flyout definitions (matches TradingView left toolbar pattern)
// ---------------------------------------------------------------------------

var _TV_ICON_ATTRS = 'xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"';

var _TOOL_GROUP_DEFS = {
    'lines': [
        { section: 'LINES', tools: [
            { id: 'trendline', name: 'Trend Line', shortcut: 'Alt+T',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="3" y1="15" x2="15" y2="3"/><circle cx="3" cy="15" r="1.5" fill="currentColor"/><circle cx="15" cy="3" r="1.5" fill="currentColor"/></svg>' },
            { id: 'ray', name: 'Ray',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="3" y1="14" x2="16" y2="3"/><circle cx="3" cy="14" r="1.5" fill="currentColor"/><polyline points="14,2 16,3 14,5" stroke-width="1"/></svg>' },
            { id: 'extended_line', name: 'Extended Line',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="1" y1="16" x2="17" y2="2"/><circle cx="6" cy="12" r="1.5" fill="currentColor"/><circle cx="12" cy="6" r="1.5" fill="currentColor"/></svg>' },
            { id: 'hline', name: 'Horizontal Line', shortcut: 'Alt+H',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="1" y1="9" x2="17" y2="9"/><line x1="1" y1="9" x2="3" y2="7" stroke-width="1"/><line x1="1" y1="9" x2="3" y2="11" stroke-width="1"/><line x1="17" y1="9" x2="15" y2="7" stroke-width="1"/><line x1="17" y1="9" x2="15" y2="11" stroke-width="1"/></svg>' },
            { id: 'hray', name: 'Horizontal Ray', shortcut: 'Alt+J',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="2" y1="9" x2="17" y2="9"/><circle cx="2" cy="9" r="1.5" fill="currentColor"/><polyline points="15,7 17,9 15,11" stroke-width="1"/></svg>' },
            { id: 'vline', name: 'Vertical Line', shortcut: 'Alt+V',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="9" y1="1" x2="9" y2="17"/><line x1="9" y1="1" x2="7" y2="3" stroke-width="1"/><line x1="9" y1="1" x2="11" y2="3" stroke-width="1"/><line x1="9" y1="17" x2="7" y2="15" stroke-width="1"/><line x1="9" y1="17" x2="11" y2="15" stroke-width="1"/></svg>' },
            { id: 'crossline', name: 'Cross Line', shortcut: 'Alt+C',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="9" y1="1" x2="9" y2="17"/><line x1="1" y1="9" x2="17" y2="9"/></svg>' },
        ]},
    ],
    'channels': [
        { section: 'CHANNELS', tools: [
            { id: 'channel', name: 'Parallel Channel',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="2" y1="14" x2="14" y2="2"/><line x1="4" y1="16" x2="16" y2="4" stroke-dasharray="2 2"/></svg>' },
            { id: 'regression_channel', name: 'Regression Trend',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="2" y1="13" x2="16" y2="5"/><line x1="2" y1="10" x2="16" y2="2" stroke-dasharray="2 2"/><line x1="2" y1="16" x2="16" y2="8" stroke-dasharray="2 2"/></svg>' },
            { id: 'flat_channel', name: 'Flat Top/Bottom',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="2" y1="5" x2="16" y2="5"/><line x1="2" y1="13" x2="16" y2="13"/></svg>' },
        ]},
    ],
    'fib': [
        { section: 'FIBONACCI', tools: [
            { id: 'fibonacci', name: 'Fib Retracement', shortcut: 'Alt+F',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="1" y1="3" x2="17" y2="3" stroke-dasharray="2 2"/><line x1="1" y1="7.5" x2="17" y2="7.5" stroke-dasharray="2 2"/><line x1="1" y1="11" x2="17" y2="11" stroke-dasharray="2 2"/><line x1="1" y1="15" x2="17" y2="15" stroke-dasharray="2 2"/><text x="1" y="2.5" font-size="4" fill="currentColor" stroke="none">0</text><text x="1" y="16.5" font-size="4" fill="currentColor" stroke="none">1</text></svg>' },
            { id: 'fib_extension', name: 'Trend-Based Fib Extension',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="1" y1="15" x2="9" y2="3"/><line x1="9" y1="3" x2="9" y2="10"/><line x1="9" y1="10" x2="17" y2="1" stroke-dasharray="2 2"/><circle cx="1" cy="15" r="1.2" fill="currentColor"/><circle cx="9" cy="3" r="1.2" fill="currentColor"/><circle cx="9" cy="10" r="1.2" fill="currentColor"/></svg>' },
            { id: 'fib_channel', name: 'Fib Channel',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="2" y1="14" x2="16" y2="6"/><line x1="2" y1="10" x2="16" y2="2" stroke-dasharray="2 2"/><line x1="2" y1="16" x2="16" y2="10" opacity="0.5"/><circle cx="2" cy="14" r="1.2" fill="currentColor"/><circle cx="16" cy="6" r="1.2" fill="currentColor"/></svg>' },
            { id: 'fib_timezone', name: 'Fib Time Zone',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="2" y1="1" x2="2" y2="17"/><line x1="4" y1="1" x2="4" y2="17"/><line x1="7" y1="1" x2="7" y2="17" stroke-dasharray="2 2"/><line x1="12" y1="1" x2="12" y2="17" stroke-dasharray="2 2"/></svg>' },
            { id: 'fib_fan', name: 'Fib Speed Resistance Fan',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="2" y1="16" x2="16" y2="2"/><line x1="2" y1="16" x2="16" y2="7" stroke-dasharray="2 2"/><line x1="2" y1="16" x2="16" y2="11" stroke-dasharray="2 2"/><circle cx="2" cy="16" r="1.2" fill="currentColor"/><circle cx="16" cy="2" r="1.2" fill="currentColor"/></svg>' },
            { id: 'fib_time', name: 'Trend-Based Fib Time',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="3" y1="14" x2="10" y2="4"/><line x1="10" y1="4" x2="10" y2="10"/><line x1="10" y1="1" x2="10" y2="17" stroke-dasharray="2 2"/><line x1="14" y1="1" x2="14" y2="17" stroke-dasharray="2 2"/><circle cx="3" cy="14" r="1.2" fill="currentColor"/><circle cx="10" cy="4" r="1.2" fill="currentColor"/><circle cx="10" cy="10" r="1.2" fill="currentColor"/></svg>' },
            { id: 'fib_circle', name: 'Fib Circles',
              icon: '<svg ' + _TV_ICON_ATTRS + '><circle cx="9" cy="9" r="3" fill="none"/><circle cx="9" cy="9" r="5.5" fill="none" stroke-dasharray="2 2"/><circle cx="9" cy="9" r="7.5" fill="none" opacity="0.5"/></svg>' },
            { id: 'fib_spiral', name: 'Fib Spiral',
              icon: '<svg ' + _TV_ICON_ATTRS + '><path d="M9 9 A 2 2 0 0 1 11 7 A 4 4 0 0 1 13 11 A 6 6 0 0 1 7 15 A 8 8 0 0 1 1 7" fill="none"/><circle cx="9" cy="9" r="1.2" fill="currentColor"/></svg>' },
            { id: 'fib_arc', name: 'Fib Speed Resistance Arcs',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="3" y1="14" x2="15" y2="4"/><path d="M8 14 A 7 7 0 0 1 15 7" fill="none" stroke-dasharray="2 2"/><path d="M5 14 A 10 10 0 0 1 15 4" fill="none" opacity="0.5"/></svg>' },
            { id: 'fib_wedge', name: 'Fib Wedge',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="2" y1="9" x2="16" y2="3"/><line x1="2" y1="9" x2="16" y2="15"/><line x1="2" y1="9" x2="16" y2="7" stroke-dasharray="2 2"/><line x1="2" y1="9" x2="16" y2="11" stroke-dasharray="2 2"/><circle cx="2" cy="9" r="1.2" fill="currentColor"/></svg>' },
            { id: 'pitchfan', name: 'Pitchfan',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="2" y1="16" x2="16" y2="2"/><line x1="2" y1="16" x2="16" y2="6" stroke-dasharray="2 2"/><line x1="2" y1="16" x2="16" y2="10" stroke-dasharray="2 2"/><line x1="2" y1="16" x2="16" y2="14" opacity="0.4"/></svg>' },
        ]},
    ],
    'gann': [
        { section: 'GANN', tools: [
            { id: 'gann_box', name: 'Gann Box',
              icon: '<svg ' + _TV_ICON_ATTRS + '><rect x="2" y="3" width="14" height="12" fill="none"/><line x1="2" y1="3" x2="16" y2="15"/><line x1="2" y1="9" x2="16" y2="9" stroke-dasharray="2 2"/><line x1="9" y1="3" x2="9" y2="15" stroke-dasharray="2 2"/></svg>' },
            { id: 'gann_square_fixed', name: 'Gann Square Fixed',
              icon: '<svg ' + _TV_ICON_ATTRS + '><rect x="3" y="3" width="12" height="12" fill="none"/><line x1="3" y1="3" x2="15" y2="15"/><line x1="3" y1="15" x2="15" y2="3" stroke-dasharray="2 2"/><line x1="9" y1="3" x2="9" y2="15" stroke-dasharray="2 2"/></svg>' },
            { id: 'gann_square', name: 'Gann Square',
              icon: '<svg ' + _TV_ICON_ATTRS + '><rect x="2" y="2" width="14" height="14" fill="none"/><line x1="2" y1="2" x2="16" y2="16"/><line x1="2" y1="16" x2="16" y2="2" stroke-dasharray="2 2"/><circle cx="9" cy="9" r="1.2" fill="currentColor"/></svg>' },
            { id: 'gann_fan', name: 'Gann Fan',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="2" y1="16" x2="16" y2="2"/><line x1="2" y1="16" x2="16" y2="9" stroke-dasharray="2 2"/><line x1="2" y1="16" x2="16" y2="5"/><line x1="2" y1="16" x2="9" y2="2" stroke-dasharray="2 2"/><circle cx="2" cy="16" r="1.2" fill="currentColor"/></svg>' },
        ]},
    ],
    'shapes': [
        { section: 'SHAPES', tools: [
            { id: 'rect', name: 'Rectangle', shortcut: 'Alt+Shift+R',
              icon: '<svg ' + _TV_ICON_ATTRS + '><rect x="3" y="4" width="12" height="10" rx="1"/></svg>' },
            { id: 'rotated_rect', name: 'Rotated Rectangle',
              icon: '<svg ' + _TV_ICON_ATTRS + '><polygon points="5,2 16,5 13,16 2,13" fill="none"/></svg>' },
            { id: 'path', name: 'Path',
              icon: '<svg ' + _TV_ICON_ATTRS + '><polyline points="3,14 7,4 12,12 16,3" fill="none"/><circle cx="3" cy="14" r="1.2" fill="currentColor"/><circle cx="7" cy="4" r="1.2" fill="currentColor"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/><circle cx="16" cy="3" r="1.2" fill="currentColor"/></svg>' },
            { id: 'circle', name: 'Circle',
              icon: '<svg ' + _TV_ICON_ATTRS + '><circle cx="9" cy="9" r="7" fill="none"/><circle cx="9" cy="9" r="1.2" fill="currentColor"/></svg>' },
            { id: 'ellipse', name: 'Ellipse',
              icon: '<svg ' + _TV_ICON_ATTRS + '><ellipse cx="9" cy="9" rx="7.5" ry="5" fill="none"/></svg>' },
            { id: 'polyline', name: 'Polyline',
              icon: '<svg ' + _TV_ICON_ATTRS + '><polyline points="2,14 6,5 11,12 16,4" fill="none"/><circle cx="2" cy="14" r="1" fill="currentColor"/><circle cx="6" cy="5" r="1" fill="currentColor"/><circle cx="11" cy="12" r="1" fill="currentColor"/><circle cx="16" cy="4" r="1" fill="currentColor"/></svg>' },
            { id: 'triangle', name: 'Triangle',
              icon: '<svg ' + _TV_ICON_ATTRS + '><polygon points="9,2 2,15 16,15" fill="none"/></svg>' },
            { id: 'shape_arc', name: 'Arc',
              icon: '<svg ' + _TV_ICON_ATTRS + '><path d="M3 14 Q 9 0 15 14" fill="none"/><circle cx="3" cy="14" r="1.2" fill="currentColor"/><circle cx="15" cy="14" r="1.2" fill="currentColor"/></svg>' },
            { id: 'curve', name: 'Curve',
              icon: '<svg ' + _TV_ICON_ATTRS + '><path d="M3 14 C 3 4 15 4 15 14" fill="none"/><circle cx="3" cy="14" r="1.2" fill="currentColor"/><circle cx="15" cy="14" r="1.2" fill="currentColor"/></svg>' },
            { id: 'double_curve', name: 'Double Curve',
              icon: '<svg ' + _TV_ICON_ATTRS + '><path d="M2 9 C 2 2 9 2 9 9 C 9 16 16 16 16 9" fill="none"/><circle cx="2" cy="9" r="1.2" fill="currentColor"/><circle cx="16" cy="9" r="1.2" fill="currentColor"/></svg>' },
        ]},
    ],
    'annotations': [
        { section: 'BRUSHES', tools: [
            { id: 'brush', name: 'Brush',
              icon: '<svg ' + _TV_ICON_ATTRS + '><path d="M13 2l3 3-8 8-4 1 1-4z"/><line x1="10" y1="5" x2="13" y2="8"/></svg>' },
            { id: 'highlighter', name: 'Highlighter',
              icon: '<svg ' + _TV_ICON_ATTRS + '><path d="M12 2l4 4-7 7-5 1 1-5z" fill="none"/><line x1="2" y1="16" x2="16" y2="16" stroke-width="2"/></svg>' },
        ]},
        { section: 'ARROWS', tools: [
            { id: 'arrow_marker', name: 'Arrow Marker',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="3" y1="15" x2="14" y2="4"/><polyline points="9,3 15,3 15,9" fill="none"/></svg>' },
            { id: 'arrow', name: 'Arrow',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="3" y1="15" x2="15" y2="3"/><polyline points="10,3 15,3 15,8" fill="none"/><circle cx="3" cy="15" r="1.2" fill="currentColor"/></svg>' },
            { id: 'arrow_mark_up', name: 'Arrow Mark Up',
              icon: '<svg ' + _TV_ICON_ATTRS + '><polygon points="9,3 3,13 15,13" fill="none"/><line x1="9" y1="13" x2="9" y2="16"/></svg>' },
            { id: 'arrow_mark_down', name: 'Arrow Mark Down',
              icon: '<svg ' + _TV_ICON_ATTRS + '><polygon points="9,15 3,5 15,5" fill="none"/><line x1="9" y1="5" x2="9" y2="2"/></svg>' },
            { id: 'arrow_mark_left', name: 'Arrow Mark Left',
              icon: '<svg ' + _TV_ICON_ATTRS + '><polygon points="3,9 13,3 13,15" fill="none"/><line x1="13" y1="9" x2="16" y2="9"/></svg>' },
            { id: 'arrow_mark_right', name: 'Arrow Mark Right',
              icon: '<svg ' + _TV_ICON_ATTRS + '><polygon points="15,9 5,3 5,15" fill="none"/><line x1="5" y1="9" x2="2" y2="9"/></svg>' },
        ]},
        { section: 'TEXT', tools: [
            { id: 'text', name: 'Text',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="4" y1="4" x2="14" y2="4"/><line x1="9" y1="4" x2="9" y2="15"/><line x1="6" y1="15" x2="12" y2="15"/></svg>' },
            { id: 'anchored_text', name: 'Anchored Text',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="4" y1="4" x2="14" y2="4"/><line x1="9" y1="4" x2="9" y2="12"/><line x1="6" y1="12" x2="12" y2="12"/><circle cx="9" cy="15" r="1.5" fill="currentColor"/></svg>' },
            { id: 'note', name: 'Note',
              icon: '<svg ' + _TV_ICON_ATTRS + '><rect x="3" y="2" width="12" height="14" rx="1" fill="none"/><line x1="6" y1="6" x2="12" y2="6"/><line x1="6" y1="9" x2="12" y2="9"/><line x1="6" y1="12" x2="10" y2="12"/></svg>' },
            { id: 'price_note', name: 'Price Note',
              icon: '<svg ' + _TV_ICON_ATTRS + '><rect x="3" y="2" width="12" height="14" rx="1" fill="none"/><text x="9" y="12" text-anchor="middle" font-size="9" fill="currentColor">$</text></svg>' },
            { id: 'pin', name: 'Pin',
              icon: '<svg ' + _TV_ICON_ATTRS + '><circle cx="9" cy="6" r="4" fill="none"/><circle cx="9" cy="6" r="1.5" fill="currentColor"/><path d="M9 10 L9 16" /><circle cx="9" cy="16" r="0.8" fill="currentColor"/></svg>' },
            { id: 'callout', name: 'Callout',
              icon: '<svg ' + _TV_ICON_ATTRS + '><path d="M3 3h12v8H8l-3 3v-3H3z" fill="none"/><line x1="6" y1="6" x2="12" y2="6"/><line x1="6" y1="9" x2="10" y2="9"/></svg>' },
            { id: 'comment', name: 'Comment',
              icon: '<svg ' + _TV_ICON_ATTRS + '><circle cx="9" cy="8" r="6" fill="none"/><line x1="6" y1="7" x2="12" y2="7"/><line x1="6" y1="10" x2="10" y2="10"/><path d="M7 14 L9 17 L11 14" fill="none"/></svg>' },
            { id: 'price_label', name: 'Price Label',
              icon: '<svg ' + _TV_ICON_ATTRS + '><path d="M2 5h11l3 4-3 4H2z" fill="none"/><line x1="5" y1="9" x2="10" y2="9"/></svg>' },
            { id: 'signpost', name: 'Signpost',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="5" y1="3" x2="5" y2="16"/><polygon points="5,3 16,5 5,8" fill="none"/></svg>' },
            { id: 'flag_mark', name: 'Flag Mark',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="4" y1="3" x2="4" y2="16"/><path d="M4 3h10l-3 4 3 4H4" fill="none"/></svg>' },
        ]},
    ],
    'projection': [
        { section: 'PROJECTION', tools: [
            { id: 'long_position', name: 'Long Position',
              icon: '<svg ' + _TV_ICON_ATTRS + '><rect x="3" y="3" width="12" height="12" fill="none"/><line x1="3" y1="9" x2="15" y2="9" stroke-dasharray="2 2"/><line x1="9" y1="3" x2="15" y2="9" fill="none" stroke="currentColor"/></svg>' },
            { id: 'short_position', name: 'Short Position',
              icon: '<svg ' + _TV_ICON_ATTRS + '><rect x="3" y="3" width="12" height="12" fill="none"/><line x1="3" y1="9" x2="15" y2="9" stroke-dasharray="2 2"/><line x1="9" y1="15" x2="15" y2="9" fill="none" stroke="currentColor"/></svg>' },
            { id: 'forecast', name: 'Forecast',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="2" y1="14" x2="8" y2="5"/><line x1="8" y1="5" x2="16" y2="8" stroke-dasharray="3 2"/><line x1="8" y1="5" x2="16" y2="3" stroke-dasharray="3 2"/><line x1="8" y1="5" x2="16" y2="13" stroke-dasharray="3 2"/></svg>' },
            { id: 'bars_pattern', name: 'Bars Pattern',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="3" y1="5" x2="3" y2="14"/><line x1="6" y1="4" x2="6" y2="12"/><line x1="9" y1="6" x2="9" y2="15"/><line x1="12" y1="4" x2="12" y2="13" stroke-dasharray="2 2"/><line x1="15" y1="5" x2="15" y2="14" stroke-dasharray="2 2"/></svg>' },
            { id: 'ghost_feed', name: 'Ghost Feed',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="2" y1="12" x2="5" y2="7"/><line x1="5" y1="7" x2="8" y2="10"/><line x1="8" y1="10" x2="11" y2="5" stroke-dasharray="2 2"/><line x1="11" y1="5" x2="14" y2="8" stroke-dasharray="2 2"/><line x1="14" y1="8" x2="17" y2="4" stroke-dasharray="2 2"/></svg>' },
            { id: 'projection', name: 'Projection',
              icon: '<svg ' + _TV_ICON_ATTRS + '><rect x="3" y="5" width="5" height="8" fill="none"/><rect x="10" y="3" width="5" height="12" fill="none" stroke-dasharray="2 2"/></svg>' },
        ]},
        { section: 'VOLUME-BASED', tools: [
            { id: 'anchored_vwap', name: 'Anchored VWAP',
              icon: '<svg ' + _TV_ICON_ATTRS + '><path d="M2 12 Q 5 4 9 9 Q 13 14 16 6" fill="none"/><circle cx="2" cy="12" r="1.2" fill="currentColor"/></svg>' },
            { id: 'fixed_range_vol', name: 'Fixed Range Volume Profile',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="3" y1="3" x2="3" y2="15"/><rect x="3" y="4" width="8" height="2" fill="currentColor" stroke="none"/><rect x="3" y="7" width="12" height="2" fill="currentColor" stroke="none"/><rect x="3" y="10" width="6" height="2" fill="currentColor" stroke="none"/><rect x="3" y="13" width="4" height="2" fill="currentColor" stroke="none"/></svg>' },
        ]},
    ],
    'measure': [
        { section: 'MEASURER', tools: [
            { id: 'measure', name: 'Measure',
              icon: '<svg ' + _TV_ICON_ATTRS + '><rect x="2" y="4" width="14" height="10" rx="1"/><line x1="5" y1="14" x2="5" y2="11"/><line x1="9" y1="14" x2="9" y2="11"/><line x1="13" y1="14" x2="13" y2="11"/></svg>' },
            { id: 'price_range', name: 'Price Range',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="9" y1="2" x2="9" y2="16"/><line x1="6" y1="4" x2="12" y2="4"/><line x1="6" y1="14" x2="12" y2="14"/><polyline points="7,2 9,0 11,2" stroke-width="1"/><polyline points="7,16 9,18 11,16" stroke-width="1"/></svg>' },
            { id: 'date_range', name: 'Date Range',
              icon: '<svg ' + _TV_ICON_ATTRS + '><line x1="2" y1="9" x2="16" y2="9"/><line x1="4" y1="6" x2="4" y2="12"/><line x1="14" y1="6" x2="14" y2="12"/><polyline points="2,7 0,9 2,11" stroke-width="1"/><polyline points="16,7 18,9 16,11" stroke-width="1"/></svg>' },
            { id: 'date_price_range', name: 'Date and Price Range',
              icon: '<svg ' + _TV_ICON_ATTRS + '><rect x="3" y="3" width="12" height="12" fill="none"/><line x1="5" y1="3" x2="5" y2="15" stroke-dasharray="2 2"/><line x1="13" y1="3" x2="13" y2="15" stroke-dasharray="2 2"/><line x1="3" y1="6" x2="15" y2="6" stroke-dasharray="2 2"/><line x1="3" y1="12" x2="15" y2="12" stroke-dasharray="2 2"/></svg>' },
        ]},
    ],
};

// Track which sub-tool is active for each group (shown on the group button)
var _toolGroupActive = {
    'lines': 'trendline',
    'channels': 'channel',
    'fib': 'fibonacci',
    'gann': 'gann_box',
    'shapes': 'rect',
    'annotations': 'brush',
    'projection': 'long_position',
    'measure': 'measure',
};

// Map tool IDs back to their parent group name
var _toolToGroup = {};
(function() {
    var groups = Object.keys(_TOOL_GROUP_DEFS);
    for (var g = 0; g < groups.length; g++) {
        var sections = _TOOL_GROUP_DEFS[groups[g]];
        for (var s = 0; s < sections.length; s++) {
            for (var t = 0; t < sections[s].tools.length; t++) {
                _toolToGroup[sections[s].tools[t].id] = groups[g];
            }
        }
    }
})();

// Active flyout DOM element
var _activeGroupFlyout = null;
var _activeGroupBtn = null;

function _tvFindToolDef(toolId) {
    var groups = Object.keys(_TOOL_GROUP_DEFS);
    for (var g = 0; g < groups.length; g++) {
        var sections = _TOOL_GROUP_DEFS[groups[g]];
        for (var s = 0; s < sections.length; s++) {
            for (var t = 0; t < sections[s].tools.length; t++) {
                if (sections[s].tools[t].id === toolId) return sections[s].tools[t];
            }
        }
    }
    return null;
}

function _tvShowToolGroupFlyout(groupBtn) {
    var groupName = groupBtn.getAttribute('data-tool-group');
    // Toggle off if already open for this group
    if (_activeGroupFlyout && _activeGroupBtn === groupBtn) {
        _tvHideToolGroupFlyout();
        return;
    }
    _tvHideToolGroupFlyout();

    var sections = _TOOL_GROUP_DEFS[groupName];
    if (!sections) return;

    var flyout = document.createElement('div');
    flyout.className = 'pywry-tool-flyout';
    flyout.setAttribute('data-group', groupName);

    for (var s = 0; s < sections.length; s++) {
        var sec = sections[s];
        var header = document.createElement('div');
        header.className = 'pywry-tool-flyout-header';
        header.textContent = sec.section;
        flyout.appendChild(header);

        for (var t = 0; t < sec.tools.length; t++) {
            var tool = sec.tools[t];
            var item = document.createElement('div');
            item.className = 'pywry-tool-flyout-item';
            if (tool.id === _toolGroupActive[groupName]) {
                item.classList.add('selected');
            }
            item.setAttribute('data-tool-id', tool.id);
            item.setAttribute('data-tool-group', groupName);

            var iconSpan = document.createElement('span');
            iconSpan.className = 'pywry-tool-flyout-icon';
            iconSpan.innerHTML = tool.icon;
            iconSpan.style.pointerEvents = 'none';
            item.appendChild(iconSpan);

            var nameSpan = document.createElement('span');
            nameSpan.className = 'pywry-tool-flyout-name';
            nameSpan.textContent = tool.name;
            nameSpan.style.pointerEvents = 'none';
            item.appendChild(nameSpan);

            if (tool.shortcut) {
                var shortcutSpan = document.createElement('span');
                shortcutSpan.className = 'pywry-tool-flyout-shortcut';
                shortcutSpan.textContent = tool.shortcut;
                shortcutSpan.style.pointerEvents = 'none';
                item.appendChild(shortcutSpan);
            }

            // Direct click handler on each item — no event delegation
            (function(itemEl, toolId, group) {
                itemEl.addEventListener('mousedown', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();

                    _toolGroupActive[group] = toolId;

                    // Update the group button icon
                    var def = _tvFindToolDef(toolId);
                    if (def) {
                        var iconEl = groupBtn.querySelector('.pywry-tool-group-icon');
                        if (iconEl) iconEl.innerHTML = def.icon;
                    }

                    // Highlight group button as active, deactivate others
                    var cId = _tvResolveChartIdFromElement(groupBtn);
                    var allIcons = _tvScopedQueryAll(cId, '.pywry-toolbar-left .pywry-icon-btn');
                    if (allIcons) allIcons.forEach(function(el) { el.classList.remove('active'); });
                    groupBtn.classList.add('active');

                    _tvSetDrawTool(cId, toolId);
                    _tvHideToolGroupFlyout();
                });
            })(item, tool.id, groupName);

            flyout.appendChild(item);
        }
    }

    // Position to the right of the left toolbar
    var _oc = _tvOverlayContainer(groupBtn);
    var _isWidget = (_oc !== document.body);
    var rect = groupBtn.getBoundingClientRect();
    var toolbar = groupBtn.closest('.tvchart-left');
    var toolbarRect = toolbar ? toolbar.getBoundingClientRect() : rect;
    flyout.style.position = _isWidget ? 'absolute' : 'fixed';
    var _cRect = _tvContainerRect(_oc, toolbarRect);
    var _bRect = _tvContainerRect(_oc, rect);
    flyout.style.left = (_cRect.right + 1) + 'px';
    flyout.style.top = _bRect.top + 'px';

    _oc.appendChild(flyout);
    _activeGroupFlyout = flyout;
    _activeGroupBtn = groupBtn;

    // Clamp to container bottom
    var _cs = _tvContainerSize(_oc);
    var flyRect = flyout.getBoundingClientRect();
    var flyH = flyRect.height;
    if (_bRect.top + flyH > _cs.height - 8) {
        flyout.style.top = Math.max(8, _cs.height - flyH - 8) + 'px';
    }

    // Block all flyout-level events from propagating to document handlers
    flyout.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    flyout.addEventListener('click', function(e) { e.stopPropagation(); });
}

function _tvHideToolGroupFlyout() {
    if (_activeGroupFlyout) {
        _activeGroupFlyout.remove();
        _activeGroupFlyout = null;
        _activeGroupBtn = null;
    }
}

// Default properties for new drawings (resolved from CSS variables)
function _getDrawDefaults() {
    return {
        color: _cssVar('--pywry-draw-default-color'),
        lineWidth: 2,
        lineStyle: 0
    };
}
var _drawDefaults = { get color() { return _getDrawDefaults().color; }, lineWidth: 2, lineStyle: 0 };

// Color palette for the floating toolbar picker (resolved from CSS variables)
function _getDrawColors() {
    var colors = [];
    for (var i = 0; i < 15; i++) {
        colors.push(_cssVar('--pywry-preset-' + i));
    }
    return colors;
}

// ---------------------------------------------------------------------------
// Shared color+opacity picker popup — used by all settings modals
// ---------------------------------------------------------------------------
var _colorOpacityPopupEl = null;
var _colorOpacityCleanups = [];

function _tvHideColorOpacityPopup() {
    for (var i = 0; i < _colorOpacityCleanups.length; i++) {
        try { _colorOpacityCleanups[i](); } catch(e) {}
    }
    _colorOpacityCleanups = [];
    if (_colorOpacityPopupEl && _colorOpacityPopupEl.parentNode) {
        _colorOpacityPopupEl.parentNode.removeChild(_colorOpacityPopupEl);
    }
    _colorOpacityPopupEl = null;
}

/**
 * Show a color+opacity popup anchored to `anchor`.
 * @param {Element} anchor       The element to position relative to
 * @param {string}  currentColor Hex color
 * @param {number}  currentOpacity 0-100 percent
 * @param {Element} parentOverlay The overlay to append the popup to (or document.body)
 * @param {function(color,opacity)} onUpdate Called on every change
 */
function _tvShowColorOpacityPopup(anchor, currentColor, currentOpacity, parentOverlay, onUpdate) {
    if (!anchor) return;
    if (_colorOpacityPopupEl && _colorOpacityPopupEl._anchor === anchor) {
        _tvHideColorOpacityPopup();
        return;
    }
    _tvHideColorOpacityPopup();
    _tvHideColorPicker();

    currentColor = _tvColorToHex(currentColor || '#aeb4c2', '#aeb4c2');
    currentOpacity = _tvClamp(_tvToNumber(currentOpacity, 100), 0, 100);

    var curRgb = _hexToRgb(currentColor);
    var curHsv = _rgbToHsv(curRgb[0], curRgb[1], curRgb[2]);
    var cpH = curHsv[0], cpS = curHsv[1], cpV = curHsv[2];

    var PW = 276;
    var popup = document.createElement('div');
    popup.style.cssText =
        'position:fixed;z-index:12002;width:' + PW + 'px;padding:14px;' +
        'background:' + _cssVar('--pywry-draw-bg', '#1e222d') + ';' +
        'border:1px solid ' + _cssVar('--pywry-draw-border', '#434651') + ';' +
        'border-radius:12px;box-shadow:0 12px 32px ' + _cssVar('--pywry-draw-shadow-lg', 'rgba(0,0,0,.6)') + ';' +
        'font-family:-apple-system,BlinkMacSystemFont,sans-serif;';
    popup.addEventListener('click', function(e) { e.stopPropagation(); });
    popup.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    popup._anchor = anchor;

    var presets = _getDrawColors();
    var presetButtons = [];

    // === SV Canvas ===
    var svW = PW, svH = 150;
    var svWrap = document.createElement('div');
    svWrap.style.cssText =
        'position:relative;width:' + svW + 'px;height:' + svH + 'px;' +
        'border-radius:6px;overflow:hidden;cursor:crosshair;margin-bottom:10px;';
    var svCanvas = document.createElement('canvas');
    svCanvas.width = svW * 2; svCanvas.height = svH * 2;
    svCanvas.style.cssText = 'width:100%;height:100%;display:block;';
    svWrap.appendChild(svCanvas);

    var svDot = document.createElement('div');
    svDot.style.cssText =
        'position:absolute;width:14px;height:14px;border-radius:50%;' +
        'border:2px solid ' + _cssVar('--pywry-draw-handle-fill', '#ffffff') + ';' +
        'box-shadow:0 0 4px ' + _cssVar('--pywry-draw-shadow-lg', 'rgba(0,0,0,.6)') + ';' +
        'pointer-events:none;transform:translate(-50%,-50%);';
    svWrap.appendChild(svDot);
    popup.appendChild(svWrap);

    function paintSV() { _cpPaintSV(svCanvas, cpH); }

    function svFromEvent(e) {
        var r = svWrap.getBoundingClientRect();
        cpS = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
        cpV = Math.max(0, Math.min(1, 1 - (e.clientY - r.top) / r.height));
        applyFromHSV();
    }
    svWrap.addEventListener('mousedown', function(e) {
        e.preventDefault();
        svFromEvent(e);
        function mv(ev) { svFromEvent(ev); }
        function up() { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); }
        document.addEventListener('mousemove', mv);
        document.addEventListener('mouseup', up);
    });

    // === Hue bar ===
    var hueH = 14;
    var hueWrap = document.createElement('div');
    hueWrap.style.cssText =
        'position:relative;width:100%;height:' + hueH + 'px;' +
        'border-radius:7px;overflow:hidden;cursor:pointer;margin-bottom:10px;';
    var hueCanvas = document.createElement('canvas');
    hueCanvas.width = svW * 2; hueCanvas.height = hueH * 2;
    hueCanvas.style.cssText = 'width:100%;height:100%;display:block;';
    hueWrap.appendChild(hueCanvas);
    _cpPaintHue(hueCanvas);

    var hueThumb = document.createElement('div');
    hueThumb.style.cssText =
        'position:absolute;top:50%;width:16px;height:16px;border-radius:50%;' +
        'border:2px solid ' + _cssVar('--pywry-draw-handle-fill', '#ffffff') + ';' +
        'box-shadow:0 0 4px ' + _cssVar('--pywry-draw-shadow-lg', 'rgba(0,0,0,.6)') + ';' +
        'pointer-events:none;transform:translate(-50%,-50%);';
    hueWrap.appendChild(hueThumb);
    popup.appendChild(hueWrap);

    function hueFromEvent(e) {
        var r = hueWrap.getBoundingClientRect();
        cpH = Math.max(0, Math.min(0.999, (e.clientX - r.left) / r.width));
        paintSV();
        applyFromHSV();
    }
    hueWrap.addEventListener('mousedown', function(e) {
        e.preventDefault();
        hueFromEvent(e);
        function mv(ev) { hueFromEvent(ev); }
        function up() { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); }
        document.addEventListener('mousemove', mv);
        document.addEventListener('mouseup', up);
    });

    // === Hex input row ===
    var hexRow = document.createElement('div');
    hexRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:10px;';
    var prevBox = document.createElement('div');
    prevBox.style.cssText =
        'width:32px;height:32px;border-radius:4px;flex-shrink:0;' +
        'border:1px solid ' + _cssVar('--pywry-draw-border', '#434651') + ';';
    var hexIn = document.createElement('input');
    hexIn.type = 'text'; hexIn.spellcheck = false; hexIn.maxLength = 7;
    hexIn.style.cssText =
        'flex:1;background:' + _cssVar('--pywry-draw-input-bg', '#0a0a0d') + ';' +
        'border:1px solid ' + _cssVar('--pywry-draw-border', '#434651') + ';border-radius:4px;' +
        'color:' + _cssVar('--pywry-draw-input-text', '#d1d4dc') + ';font-size:13px;padding:6px 8px;font-family:monospace;' +
        'outline:none;text-transform:uppercase;';
    hexIn.addEventListener('focus', function() { hexIn.style.borderColor = _cssVar('--pywry-draw-input-focus', '#2962ff'); });
    hexIn.addEventListener('blur',  function() { hexIn.style.borderColor = _cssVar('--pywry-draw-border', '#434651'); });
    hexIn.addEventListener('keydown', function(e) {
        e.stopPropagation();
        if (e.key === 'Enter') {
            var val = hexIn.value.trim();
            if (val[0] !== '#') val = '#' + val;
            if (/^#[0-9a-fA-F]{6}$/.test(val)) {
                var rgb = _hexToRgb(val);
                var hsv = _rgbToHsv(rgb[0], rgb[1], rgb[2]);
                cpH = hsv[0]; cpS = hsv[1]; cpV = hsv[2];
                paintSV();
                applyFromHSV();
            }
        }
    });
    hexRow.appendChild(prevBox);
    hexRow.appendChild(hexIn);
    popup.appendChild(hexRow);

    // === Separator ===
    var sep1 = document.createElement('div');
    sep1.style.cssText = 'height:1px;background:' + _cssVar('--pywry-draw-border', '#434651') + ';margin:0 0 10px 0;';
    popup.appendChild(sep1);

    // === Preset swatches ===
    var swatchGrid = document.createElement('div');
    swatchGrid.style.cssText = 'display:grid;grid-template-columns:repeat(10,minmax(0,1fr));gap:6px;margin-bottom:14px;';
    popup.appendChild(swatchGrid);

    for (var pi = 0; pi < presets.length; pi++) {
        (function(presetColor) {
            var presetButton = document.createElement('button');
            presetButton.type = 'button';
            presetButton.dataset.color = presetColor.toLowerCase();
            presetButton.style.cssText =
                'width:100%;aspect-ratio:1;border-radius:6px;cursor:pointer;box-sizing:border-box;' +
                'border:2px solid transparent;background:' + presetColor + ';';
            presetButton.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                var rgb = _hexToRgb(presetColor);
                var hsv = _rgbToHsv(rgb[0], rgb[1], rgb[2]);
                cpH = hsv[0]; cpS = hsv[1]; cpV = hsv[2];
                paintSV();
                applyFromHSV();
            });
            presetButtons.push(presetButton);
            swatchGrid.appendChild(presetButton);
        })(presets[pi]);
    }

    // === Separator ===
    var sep2 = document.createElement('div');
    sep2.style.cssText = 'height:1px;background:' + _cssVar('--pywry-draw-border', '#434651') + ';margin:0 0 14px 0;';
    popup.appendChild(sep2);

    // === Opacity ===
    var opacityTitle = document.createElement('div');
    opacityTitle.textContent = 'Opacity';
    opacityTitle.style.cssText = 'color:' + _cssVar('--pywry-tvchart-text', '#d1d4dc') + ';font-size:12px;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:8px;';
    popup.appendChild(opacityTitle);

    var opacityRow = document.createElement('div');
    opacityRow.style.cssText = 'display:flex;align-items:center;gap:10px;';
    var opacitySlider = document.createElement('input');
    opacitySlider.type = 'range';
    opacitySlider.className = 'tv-settings-slider';
    opacitySlider.min = '0';
    opacitySlider.max = '100';
    opacityRow.appendChild(opacitySlider);
    var opacityValue = document.createElement('input');
    opacityValue.type = 'number';
    opacityValue.className = 'ts-input ts-input-sm';
    opacityValue.min = '0';
    opacityValue.max = '100';
    opacityValue.addEventListener('keydown', function(e) { e.stopPropagation(); });
    opacityRow.appendChild(opacityValue);
    var opacityUnit = document.createElement('span');
    opacityUnit.className = 'tv-settings-unit';
    opacityUnit.textContent = '%';
    opacityRow.appendChild(opacityUnit);
    popup.appendChild(opacityRow);

    // === Refresh helpers ===
    function refreshPresetSelection() {
        presetButtons.forEach(function(btn) {
            btn.style.borderColor = btn.dataset.color === currentColor.toLowerCase()
                ? _cssVar('--pywry-draw-input-focus', '#2962ff')
                : 'transparent';
        });
    }

    function refreshHSVUI() {
        var rgb = _hsvToRgb(cpH, cpS, cpV);
        var hex = _rgbToHex(rgb[0], rgb[1], rgb[2]);
        svDot.style.left = (cpS * 100) + '%';
        svDot.style.top  = ((1 - cpV) * 100) + '%';
        svDot.style.background = hex;
        hueThumb.style.left = (cpH * 100) + '%';
        var hRgb = _hsvToRgb(cpH, 1, 1);
        hueThumb.style.background = _rgbToHex(hRgb[0], hRgb[1], hRgb[2]);
        hexIn.value = hex.toUpperCase();
        prevBox.style.background = _tvColorWithOpacity(hex, currentOpacity, hex);
    }

    function applyFromHSV() {
        var rgb = _hsvToRgb(cpH, cpS, cpV);
        currentColor = _rgbToHex(rgb[0], rgb[1], rgb[2]);
        opacitySlider.value = String(currentOpacity);
        opacityValue.value = String(currentOpacity);
        prevBox.style.background = _tvColorWithOpacity(currentColor, currentOpacity, currentColor);
        refreshHSVUI();
        refreshPresetSelection();
        if (onUpdate) onUpdate(currentColor, currentOpacity);
    }

    function applySelection(nextColor, nextOpacity) {
        currentColor = _tvColorToHex(nextColor || currentColor, currentColor);
        currentOpacity = _tvClamp(_tvToNumber(nextOpacity, currentOpacity), 0, 100);
        var rgb = _hexToRgb(currentColor);
        var hsv = _rgbToHsv(rgb[0], rgb[1], rgb[2]);
        cpH = hsv[0]; cpS = hsv[1]; cpV = hsv[2];
        paintSV();
        opacitySlider.value = String(currentOpacity);
        opacityValue.value = String(currentOpacity);
        prevBox.style.background = _tvColorWithOpacity(currentColor, currentOpacity, currentColor);
        refreshHSVUI();
        refreshPresetSelection();
        if (onUpdate) onUpdate(currentColor, currentOpacity);
    }

    opacitySlider.addEventListener('input', function() {
        applySelection(currentColor, opacitySlider.value);
    });
    opacityValue.addEventListener('input', function() {
        applySelection(currentColor, opacityValue.value);
    });

    _colorOpacityPopupEl = popup;
    var appendTarget = parentOverlay || document.body;
    appendTarget.appendChild(popup);
    paintSV();
    applySelection(currentColor, currentOpacity);

    // --- Position within the parent (absolute if inside overlay, fixed if body) ---
    if (parentOverlay) {
        popup.style.position = 'absolute';
        // Find the settings panel inside the overlay to constrain within it
        var constrainEl = parentOverlay.querySelector('.tv-settings-panel') || parentOverlay;
        var constrainRect = constrainEl.getBoundingClientRect();
        var overlayRect = parentOverlay.getBoundingClientRect();
        var anchorRect = anchor.getBoundingClientRect();
        var popupRect = popup.getBoundingClientRect();
        // Calculate position relative to the overlay
        var top = anchorRect.bottom - overlayRect.top + 6;
        // If it goes below the panel bottom, show above the anchor
        if (top + popupRect.height > constrainRect.bottom - overlayRect.top - 8) {
            top = anchorRect.top - overlayRect.top - popupRect.height - 6;
        }
        // Clamp to panel bounds vertically
        var minTop = constrainRect.top - overlayRect.top + 4;
        var maxTop = constrainRect.bottom - overlayRect.top - popupRect.height - 4;
        top = Math.max(minTop, Math.min(maxTop, top));
        var left = anchorRect.left - overlayRect.left;
        // Clamp to panel bounds horizontally
        var maxLeft = constrainRect.right - overlayRect.left - popupRect.width - 4;
        left = Math.max(constrainRect.left - overlayRect.left + 4, Math.min(maxLeft, left));
        popup.style.top = top + 'px';
        popup.style.left = left + 'px';
    } else {
        var anchorRect = anchor.getBoundingClientRect();
        var popupRect = popup.getBoundingClientRect();
        var top = anchorRect.bottom + 10;
        if (top + popupRect.height > window.innerHeight - 12) {
            top = Math.max(12, anchorRect.top - popupRect.height - 10);
        }
        var left = anchorRect.left;
        if (left + popupRect.width > window.innerWidth - 12) {
            left = Math.max(12, window.innerWidth - popupRect.width - 12);
        }
        popup.style.top = top + 'px';
        popup.style.left = left + 'px';
    }

    // --- Dismissal: Escape key and click outside ---
    function onEscKey(e) {
        if (e.key === 'Escape') {
            e.stopPropagation();
            _tvHideColorOpacityPopup();
        }
    }
    function onOutsideClick(e) {
        if (popup.contains(e.target) || e.target === anchor) return;
        _tvHideColorOpacityPopup();
    }
    document.addEventListener('keydown', onEscKey, true);
    // Delay the click listener so the current click doesn't immediately close it
    var _outsideTimer = setTimeout(function() {
        document.addEventListener('mousedown', onOutsideClick, true);
    }, 0);
    _colorOpacityCleanups.push(function() {
        clearTimeout(_outsideTimer);
        document.removeEventListener('keydown', onEscKey, true);
        document.removeEventListener('mousedown', onOutsideClick, true);
    });
}

var _DRAW_WIDTHS = [1, 2, 3, 4];

function _tvApplyDrawingInteractionMode(ds) {
    if (!ds || !ds.canvas) return;
    var tool = ds._activeTool || 'cursor';
    if (tool === 'crosshair' || tool === 'cursor') {
        ds.canvas.style.pointerEvents = 'none';
        ds.canvas.style.cursor = tool === 'crosshair' ? 'crosshair' : 'default';
        return;
    }
    ds.canvas.style.pointerEvents = 'auto';
    ds.canvas.style.cursor = 'crosshair';
}

function _tvGetDrawingViewport(chartId) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    var width = ds && ds.canvas ? ds.canvas.clientWidth : 0;
    var height = ds && ds.canvas ? ds.canvas.clientHeight : 0;
    var viewport = { left: 0, top: 0, right: width, bottom: height, width: width, height: height };
    if (!entry || !entry.chart || width <= 0 || height <= 0) return viewport;

    var timeScale = entry.chart.timeScale ? entry.chart.timeScale() : null;
    if (timeScale && typeof timeScale.logicalToCoordinate === 'function' &&
        typeof timeScale.getVisibleLogicalRange === 'function') {
        var range = timeScale.getVisibleLogicalRange();
        if (range && isFinite(range.from) && isFinite(range.to)) {
            var leftCoord = timeScale.logicalToCoordinate(range.from);
            var rightCoord = timeScale.logicalToCoordinate(range.to);
            if (leftCoord !== null && isFinite(leftCoord)) {
                viewport.left = Math.max(0, Math.min(width, leftCoord));
            }
            if (rightCoord !== null && isFinite(rightCoord)) {
                viewport.right = Math.max(viewport.left, Math.min(width, rightCoord));
            }
        }
    }

    if (!isFinite(viewport.right) || viewport.right <= viewport.left + 8 || viewport.right >= width - 2) {
        var placement = entry._chartPrefs && entry._chartPrefs.scalesPlacement
            ? entry._chartPrefs.scalesPlacement
            : 'Auto';
        var labelProbe = 68;
        if (ds && ds.ctx) {
            ds.ctx.save();
            ds.ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
            labelProbe = Math.ceil(ds.ctx.measureText('000000.00').width) + 18;
            ds.ctx.restore();
        }
        var gutter = Math.max(52, Math.min(96, labelProbe));
        if (placement === 'Left') {
            viewport.left = gutter;
            viewport.right = width;
        } else {
            viewport.left = 0;
            viewport.right = Math.max(0, width - gutter);
        }
    }

    viewport.width = Math.max(0, viewport.right - viewport.left);
    return viewport;
}

// Fibonacci settings (resolved from CSS variables)
var _FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
function _getFibColors() {
    var colors = [];
    for (var i = 0; i < 7; i++) {
        colors.push(_cssVar('--pywry-fib-color-' + i));
    }
    return colors;
}

// ---- SVG icon templates for drawing toolbar ----
var _DT_ICONS = {
    pencil: '<svg viewBox="0 0 18 18"><path d="M13.3 1.3a1 1 0 011.4 0l2 2a1 1 0 010 1.4l-10 10a1 1 0 01-.5.3l-3 .7a.5.5 0 01-.6-.6l.7-3a1 1 0 01.3-.5l10-10z"/></svg>',
    bucket: '<svg viewBox="0 0 18 18"><path d="M11 1.5L2.5 10a1 1 0 000 1.4l4.1 4.1a1 1 0 001.4 0L16.5 7m-2 6c0 1.1.9 2.5 2 2.5s2-1.4 2-2.5S17.1 11 16.5 11 14.5 11.9 14.5 13z"/></svg>',
    text: '<svg viewBox="0 0 18 18"><path d="M3 4h12M9 4v11M6 15h6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
    border: '<svg viewBox="0 0 18 18"><rect x="3" y="3" width="12" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>',
    lineW: '<svg viewBox="0 0 18 18"><rect x="2" y="4" width="14" height="2" rx="1"/><rect x="2" y="8" width="14" height="3" rx="1.5"/><rect x="2" y="13" width="14" height="1" rx=".5"/></svg>',
    settings: '<svg viewBox="0 0 18 18"><circle cx="9" cy="9" r="2.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M9 1v2m0 12v2M1 9h2m12 0h2M3.3 3.3l1.4 1.4m8.6 8.6l1.4 1.4M14.7 3.3l-1.4 1.4M4.7 13.3l-1.4 1.4" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
    lock: '<svg viewBox="0 0 18 18"><rect x="4" y="8" width="10" height="8" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M6 8V5.5a3 3 0 016 0V8" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>',
    unlock: '<svg viewBox="0 0 18 18"><rect x="4" y="8" width="10" height="8" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M6 8V5.5a3 3 0 016 0" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>',
    trash: '<svg viewBox="0 0 18 18"><path d="M3 5h12M7 5V3.5A1.5 1.5 0 018.5 2h1A1.5 1.5 0 0111 3.5V5m-6 0l.8 10a1.5 1.5 0 001.5 1.4h3.4a1.5 1.5 0 001.5-1.4L13 5" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
    clone: '<svg viewBox="0 0 18 18"><rect x="5" y="5" width="10" height="10" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M3 13V4a1 1 0 011-1h9" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>',
    eye: '<svg viewBox="0 0 18 18"><path d="M1 9s3-5.5 8-5.5S17 9 17 9s-3 5.5-8 5.5S1 9 1 9z" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="9" cy="9" r="2.5" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>',
    eyeOff: '<svg viewBox="0 0 18 18"><path d="M1 9s3-5.5 8-5.5S17 9 17 9s-3 5.5-8 5.5S1 9 1 9zM2 16L16 2" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>',
    more: '<svg viewBox="0 0 18 18"><circle cx="4" cy="9" r="1.3"/><circle cx="9" cy="9" r="1.3"/><circle cx="14" cy="9" r="1.3"/></svg>',
};

// ---- Ensure drawing layer ----
function _tvEnsureDrawingLayer(chartId) {
    if (window.__PYWRY_DRAWINGS__[chartId]) return window.__PYWRY_DRAWINGS__[chartId];

    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.container) return null;

    var container = entry.container;
    var pos = window.getComputedStyle(container).position;
    if (pos === 'static') container.style.position = 'relative';

    var canvas = document.createElement('canvas');
    canvas.className = 'pywry-drawing-overlay';
    canvas.style.cssText =
        'position:absolute;top:0;left:0;width:100%;height:100%;' +
        'pointer-events:none;z-index:5;';
    container.appendChild(canvas);

    // UI overlay div (sits above canvas, for floating toolbar / menus)
    var uiLayer = document.createElement('div');
    uiLayer.className = 'pywry-draw-ui-layer';
    uiLayer.style.cssText =
        'position:absolute;top:0;left:0;width:100%;height:100%;' +
        'pointer-events:none;z-index:10;overflow:visible;';
    container.appendChild(uiLayer);

    var ctx = canvas.getContext('2d');
    var state = {
        canvas: canvas,
        ctx: ctx,
        uiLayer: uiLayer,
        chartId: chartId,
        drawings: [],
        priceLines: [],
        _activeTool: 'cursor',
    };
    window.__PYWRY_DRAWINGS__[chartId] = state;
    _tvApplyDrawingInteractionMode(state);

    function resize() {
        var rect = container.getBoundingClientRect();
        var dpr = window.devicePixelRatio || 1;
        canvas.width  = rect.width  * dpr;
        canvas.height = rect.height * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        _tvRenderDrawings(chartId);
    }
    if (typeof ResizeObserver !== 'undefined') {
        new ResizeObserver(resize).observe(container);
    }
    resize();

    entry.chart.timeScale().subscribeVisibleLogicalRangeChange(function() {
        _tvRenderDrawings(chartId);
        _tvRepositionToolbar(chartId);
    });

    _tvEnableDrawing(chartId);
    return state;
}

// ---- Coordinate helpers ----
function _tvMainSeries(chartId) {
    var e = window.__PYWRY_TVCHARTS__[chartId];
    if (!e) return null;
    var k = Object.keys(e.seriesMap)[0];
    return k ? e.seriesMap[k] : null;
}

function _tvResolveChartId(chartId) {
    if (chartId && window.__PYWRY_TVCHARTS__[chartId]) return chartId;
    var keys = Object.keys(window.__PYWRY_TVCHARTS__);
    return keys.length ? keys[0] : null;
}

function _tvResolveChartEntry(chartId) {
    var resolvedId = _tvResolveChartId(chartId);
    if (!resolvedId) return null;
    return {
        chartId: resolvedId,
        entry: window.__PYWRY_TVCHARTS__[resolvedId],
    };
}

function _tvIsUiScopeNode(node) {
    if (!node || !node.classList) return false;
    return (
        node.classList.contains('pywry-widget') ||
        node.classList.contains('pywry-content') ||
        node.classList.contains('pywry-wrapper-inside') ||
        node.classList.contains('pywry-wrapper-top') ||
        node.classList.contains('pywry-body-scroll') ||
        node.classList.contains('pywry-wrapper-left') ||
        node.classList.contains('pywry-wrapper-header')
    );
}

function _tvResolveUiRootFromElement(element) {
    if (!element || !element.closest) return document;
    var root = element.closest('.pywry-content, .pywry-widget') || element;
    while (root && root.parentElement && _tvIsUiScopeNode(root.parentElement)) {
        root = root.parentElement;
    }
    return root || document;
}

function _tvResolveUiRoot(chartId) {
    var resolved = _tvResolveChartEntry(chartId);
    var entry = resolved ? resolved.entry : null;
    if (!entry) return document;
    if (entry.uiRoot) return entry.uiRoot;
    if (entry.container) {
        entry.uiRoot = _tvResolveUiRootFromElement(entry.container);
        return entry.uiRoot;
    }
    return document;
}

function _tvResolveChartIdFromElement(element) {
    var root = _tvResolveUiRootFromElement(element);
    var ids = Object.keys(window.__PYWRY_TVCHARTS__ || {});
    for (var i = 0; i < ids.length; i++) {
        if (_tvResolveUiRoot(ids[i]) === root) {
            return ids[i];
        }
    }
    return _tvResolveChartId(null);
}

function _tvScopedQuery(scopeOrChartId, selector) {
    var scope = scopeOrChartId;
    if (!scope || typeof scope === 'string') {
        scope = _tvResolveUiRoot(scopeOrChartId);
    }
    if (scope && typeof scope.querySelector === 'function') {
        var scopedNode = scope.querySelector(selector);
        if (scopedNode) return scopedNode;
    }
    return document.querySelector(selector);
}

function _tvScopedQueryAll(scopeOrChartId, selector) {
    var scope = scopeOrChartId;
    if (!scope || typeof scope === 'string') {
        scope = _tvResolveUiRoot(scopeOrChartId);
    }
    if (scope && typeof scope.querySelectorAll === 'function') {
        return scope.querySelectorAll(selector);
    }
    return document.querySelectorAll(selector);
}

function _tvScopedById(scopeOrChartId, id) {
    return _tvScopedQuery(scopeOrChartId, '[id="' + id + '"]');
}

function _tvSetLegendVisible(visible, chartId) {
    if (!chartId) {
        var chartIds = Object.keys(window.__PYWRY_TVCHARTS__ || {});
        if (chartIds.length) {
            for (var i = 0; i < chartIds.length; i++) {
                _tvSetLegendVisible(visible, chartIds[i]);
            }
            return;
        }
    }
    var legend = _tvScopedById(chartId, 'tvchart-legend-box');
    if (!legend) return;
    legend.style.opacity = visible ? '1' : '0';
}

function _tvRefreshLegendVisibility(chartId) {
    if (!chartId) {
        var chartIds = Object.keys(window.__PYWRY_TVCHARTS__ || {});
        if (chartIds.length) {
            for (var i = 0; i < chartIds.length; i++) {
                _tvRefreshLegendVisibility(chartIds[i]);
            }
            return;
        }
    }
    var root = _tvResolveUiRoot(chartId);
    var menuOpen = !!_tvScopedQuery(
        root,
        '.tvchart-save-menu.open, .tvchart-chart-type-menu.open, .tvchart-interval-menu.open'
    );
    _tvSetLegendVisible(!menuOpen, chartId);
}

function _tvRefreshLegendTitle(chartId) {
    var resolved = _tvResolveChartEntry(chartId);
    var entry = resolved ? resolved.entry : null;
    var effectiveChartId = resolved ? resolved.chartId : chartId;
    if (!entry) return;

    var titleEl = _tvScopedById(effectiveChartId, 'tvchart-legend-title');
    if (!titleEl) return;
    var legendBox = _tvScopedById(effectiveChartId, 'tvchart-legend-box');
    var ds = legendBox ? legendBox.dataset : null;

    var base = ds && ds.baseTitle ? String(ds.baseTitle) : '';
    if (!base && entry.payload && entry.payload.useDatafeed && entry.payload.series && entry.payload.series[0] && entry.payload.series[0].symbol) {
        base = String(entry.payload.series[0].symbol);
    }
    if (!base && entry.payload && entry.payload.title) {
        base = String(entry.payload.title);
    }
    if (!base && entry.payload && entry.payload.series && entry.payload.series[0] && entry.payload.series[0].seriesId) {
        var sid = String(entry.payload.series[0].seriesId);
        if (sid && sid !== 'main') base = sid;
    }

    if (ds && ds.showTitle === '0') {
        base = '';
    }
    // Description mode replaces the base title with resolved symbol info
    if (ds && ds.description && ds.description !== 'Off') {
        var descMode = ds.description;
        var symInfo = (entry && entry._resolvedSymbolInfo && entry._resolvedSymbolInfo.main)
            || (entry && entry._mainSymbolInfo) || {};
        var ticker = String(symInfo.ticker || symInfo.displaySymbol || symInfo.symbol || base || '').trim();
        var descText = String(symInfo.description || symInfo.fullName || '').trim();
        if (descMode === 'Description' && descText) {
            base = descText;
        } else if (descMode === 'Ticker and description') {
            base = (ticker && descText) ? (ticker + ' · ' + descText) : (ticker || descText || base);
        }
        // 'Ticker' mode keeps base as-is
    }
    if (ds && base) {
        var intervalText = ds.interval || '';
        // If no explicit interval set, read from toolbar label
        if (!intervalText) {
            var intervalLabel = _tvScopedById(effectiveChartId, 'tvchart-interval-label');
            if (intervalLabel) intervalText = (intervalLabel.textContent || '').trim();
        }
        if (intervalText) {
            base = base + ' · ' + intervalText;
        }
    }

    titleEl.textContent = base;
    titleEl.style.display = base ? 'inline-flex' : 'none';
}

function _tvEmitLegendRefresh(chartId) {
    try {
        if (typeof window.CustomEvent === 'function') {
            window.dispatchEvent(new CustomEvent('pywry:legend-refresh', {
                detail: { chartId: chartId },
            }));
        }
    } catch (e) {}
}

function _tvLegendFormat(v) {
    if (v == null) return '--';
    return Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function _tvLegendFormatVol(v) {
    if (v == null) return '';
    if (v >= 1e9) return (v / 1e9).toFixed(2) + ' B';
    if (v >= 1e6) return (v / 1e6).toFixed(2) + ' M';
    if (v >= 1e3) return (v / 1e3).toFixed(2) + ' K';
    return Number(v).toFixed(0);
}

function _tvLegendColorize(val, ref) {
    var cs = getComputedStyle(document.documentElement);
    var _up = cs.getPropertyValue('--pywry-tvchart-up').trim() || '#089981';
    var _dn = cs.getPropertyValue('--pywry-tvchart-down').trim() || '#f23645';
    var _mt = cs.getPropertyValue('--pywry-tvchart-text-muted').trim() || '#aeb4c2';
    if (val == null || ref == null) return _mt;
    return val >= ref ? _up : _dn;
}

function _tvLegendDataset(chartId) {
    var legendBox = _tvScopedById(chartId, 'tvchart-legend-box');
    return legendBox ? legendBox.dataset : null;
}

function _tvLegendNormalizeTimeValue(value) {
    if (value == null) return null;
    if (typeof value === 'number') return value;
    if (typeof value === 'string') {
        var parsed = Date.parse(value);
        return isFinite(parsed) ? Math.floor(parsed / 1000) : value;
    }
    if (typeof value === 'object') {
        if (typeof value.timestamp === 'number') return value.timestamp;
        if (typeof value.year === 'number' && typeof value.month === 'number' && typeof value.day === 'number') {
            return Date.UTC(value.year, value.month - 1, value.day) / 1000;
        }
    }
    return null;
}

function _tvLegendMainKey(entry) {
    var keys = Object.keys((entry && entry.seriesMap) || {});
    return keys.indexOf('main') >= 0 ? 'main' : (keys[0] || null);
}

function _tvLegendResolvePoint(entry, seriesId, seriesApi, param) {
    var direct = (param && param.seriesData && seriesApi) ? param.seriesData.get(seriesApi) : null;
    if (direct) return direct;

    var rows = entry && entry._seriesRawData ? entry._seriesRawData[seriesId] : null;
    if (!rows || !rows.length) return null;
    if (!param || param.time == null) return rows[rows.length - 1] || null;

    var target = _tvLegendNormalizeTimeValue(param.time);
    if (target == null) return rows[rows.length - 1] || null;

    var best = null;
    var bestTime = null;
    for (var idx = 0; idx < rows.length; idx++) {
        var row = rows[idx];
        var rowTime = _tvLegendNormalizeTimeValue(row && row.time);
        if (rowTime == null) continue;
        if (rowTime === target) return row;
        if (rowTime <= target) {
            best = row;
            bestTime = rowTime;
            continue;
        }
        if (bestTime == null) return row;
        return best;
    }
    return best || rows[rows.length - 1] || null;
}

function _tvLegendSeriesLabel(entry, seriesId) {
    var sid = String(seriesId || 'main');
    if (sid === 'main') {
        var ds = _tvLegendDataset(entry && entry.chartId ? entry.chartId : null) || {};
        var base = ds.baseTitle ? String(ds.baseTitle) : '';
        if (!base && entry && entry.payload && entry.payload.title) base = String(entry.payload.title);
        return base || 'Main';
    }
    if (entry && entry._compareLabels && entry._compareLabels[sid]) return String(entry._compareLabels[sid]);
    if (entry && entry._compareSymbolInfo && entry._compareSymbolInfo[sid]) {
        var info = entry._compareSymbolInfo[sid] || {};
        var display = String(info.displaySymbol || info.ticker || '').trim();
        if (display) return display.toUpperCase();
        var full = String(info.fullName || '').trim();
        if (full) return full;
        var rawInfoSymbol = String(info.symbol || '').trim();
        if (rawInfoSymbol) {
            return rawInfoSymbol.indexOf(':') >= 0 ? rawInfoSymbol.split(':').pop().trim().toUpperCase() : rawInfoSymbol.toUpperCase();
        }
    }
    if (entry && entry._compareSymbols && entry._compareSymbols[sid]) {
        var raw = String(entry._compareSymbols[sid]);
        return raw.indexOf(':') >= 0 ? raw.split(':').pop().trim().toUpperCase() : raw.toUpperCase();
    }
    return sid;
}

function _tvLegendSeriesColor(entry, seriesId, dataPoint, ds) {
    var sid = String(seriesId || 'main');
    if (entry && entry._legendSeriesColors && entry._legendSeriesColors[sid]) {
        return String(entry._legendSeriesColors[sid]);
    }
    if (dataPoint && dataPoint.open !== undefined) {
        return _tvLegendColorize(dataPoint.close, dataPoint.open);
    }
    return (ds && ds.lineColor) ? ds.lineColor : (getComputedStyle(document.documentElement).getPropertyValue('--pywry-tvchart-session-breaks').trim() || '#4c87ff');
}

function _tvRenderLegendSeriesRows(chartId, entry, param) {
    var seriesEl = _tvScopedById(chartId, 'tvchart-legend-series');
    if (!seriesEl || !entry) return;

    var ds = _tvLegendDataset(chartId) || {};
    var currentMainKey = _tvLegendMainKey(entry);
    var keys = Object.keys(entry.seriesMap || {});
    var existing = {};
    var existingRows = seriesEl.querySelectorAll('.tvchart-legend-series-row');
    for (var ri = 0; ri < existingRows.length; ri++) {
        var existingId = existingRows[ri].getAttribute('data-series-id') || '';
        if (existingId) existing[existingId] = existingRows[ri];
    }

    var activeCount = 0;
    for (var i = 0; i < keys.length; i++) {
        var sid = keys[i];
        if (String(sid) === String(currentMainKey) || String(sid) === 'volume' || String(sid).indexOf('ind_') === 0) continue;
        if (entry._indicatorSourceSeries && entry._indicatorSourceSeries[sid]) continue;
        var sApi = entry.seriesMap[sid];
        if (!sApi) continue;

        var d = _tvLegendResolvePoint(entry, sid, sApi, param);
        var value = null;
        if (d && d.open !== undefined) value = Number(d.close);
        else if (d && d.value !== undefined) value = Number(d.value);

        var row = existing[sid] || document.createElement('div');
        if (!existing[sid]) {
            row.className = 'tvchart-legend-row tvchart-legend-series-row';
            row.setAttribute('data-series-id', sid);
            row.innerHTML =
                '<span class="tvchart-legend-series-dot"></span>' +
                '<span class="tvchart-legend-series-name"></span>' +
                '<span class="tvchart-legend-series-value"></span>' +
                '<span class="tvchart-legend-row-actions tvchart-legend-series-actions"></span>';
            seriesEl.appendChild(row);
        }
        delete existing[sid];
        activeCount += 1;

        var dot = row.querySelector('.tvchart-legend-series-dot');
        var name = row.querySelector('.tvchart-legend-series-name');
        var valueEl = row.querySelector('.tvchart-legend-series-value');
        var color = _tvLegendSeriesColor(entry, sid, d, ds);
        if (dot) dot.style.background = color;
        if (name) name.textContent = _tvLegendSeriesLabel(entry, sid);
        if (valueEl) {
            valueEl.textContent = value == null ? '--' : _tvLegendFormat(value);
            valueEl.style.color = color;
        }
    }

    var obsoleteIds = Object.keys(existing);
    for (var oi = 0; oi < obsoleteIds.length; oi++) {
        var obsoleteRow = existing[obsoleteIds[oi]];
        if (obsoleteRow && obsoleteRow.parentNode) obsoleteRow.parentNode.removeChild(obsoleteRow);
    }
    seriesEl.style.display = activeCount ? 'block' : 'none';
}

function _tvRenderHoverLegend(chartId, param) {
    var resolved = _tvResolveChartEntry(chartId);
    var entry = resolved ? resolved.entry : null;
    var effectiveChartId = resolved ? resolved.chartId : chartId;
    if (!entry) return;

    var titleEl = _tvScopedById(effectiveChartId, 'tvchart-legend-title');
    var ohlcEl = _tvScopedById(effectiveChartId, 'tvchart-legend-ohlc');
    var mainRowEl = _tvScopedById(effectiveChartId, 'tvchart-legend-main-row');
    if (!titleEl || !ohlcEl) return;

    var ds = _tvLegendDataset(effectiveChartId) || {};
    _tvRefreshLegendTitle(effectiveChartId);

    var mainKey = _tvLegendMainKey(entry);
    var mainSeries = entry.seriesMap ? entry.seriesMap[mainKey] : null;
    var d = _tvLegendResolvePoint(entry, mainKey, mainSeries, param);
    var legendMainHtml = '';
    var highLowMode = ds.highLowMode || 'Hidden';
    var _csHL = getComputedStyle(document.documentElement);
    var highLowColor = ds.highLowColor || (_csHL.getPropertyValue('--pywry-tvchart-down').trim() || '#f23645');
    var lineColor = ds.lineColor || (_csHL.getPropertyValue('--pywry-tvchart-up').trim() || '#089981');
    var symbolMode = ds.symbolMode || 'Value, line';

    if (d && d.open !== undefined) {
        var chg = Number(d.close) - Number(d.open);
        var chgPct = Number(d.open) !== 0 ? ((chg / Number(d.open)) * 100) : 0;
        var clr = _tvLegendColorize(d.close, d.open);
        var parts = [];
        if (symbolMode !== 'Line only') {
            parts.push('<span style="color:var(--pywry-tvchart-text-dim)">O</span> <span style="color:' + clr + '">' + _tvLegendFormat(d.open) + '</span>');
            if (highLowMode !== 'Hidden') {
                parts.push('<span style="color:' + highLowColor + '">H</span> <span style="color:' + clr + '">' + _tvLegendFormat(d.high) + '</span>');
                parts.push('<span style="color:' + highLowColor + '">L</span> <span style="color:' + clr + '">' + _tvLegendFormat(d.low) + '</span>');
            }
            parts.push('<span style="color:var(--pywry-tvchart-text-dim)">C</span> <span style="color:' + clr + '">' + _tvLegendFormat(d.close) + '</span>');
        } else {
            parts.push('<span style="color:' + lineColor + '">—</span>');
        }
        parts.push('<span style="color:' + clr + '">' + (chg >= 0 ? '+' : '') + _tvLegendFormat(chg) + ' (' + (chg >= 0 ? '+' : '') + chgPct.toFixed(2) + '%)</span>');
        legendMainHtml = parts.join(' ');
    } else if (d && d.value !== undefined) {
        legendMainHtml = symbolMode === 'Line only'
            ? '<span style="color:' + lineColor + '">—</span>'
            : '<span style="color:' + lineColor + '">' + _tvLegendFormat(d.value) + '</span>';
    }

    ohlcEl.innerHTML = legendMainHtml;
    if (mainRowEl) {
        var showMainRow = !!(titleEl.textContent || ohlcEl.textContent || ohlcEl.innerHTML);
        mainRowEl.style.display = showMainRow ? 'flex' : 'none';
    }

    // Volume content and vol row visibility are managed by
    // _tvSetupLegendControls (11-legend.js) — do not touch volEl / volRowEl
    // here to avoid conflicting display changes.

    _tvRenderLegendSeriesRows(effectiveChartId, entry, param);
}

function _tvClamp(v, min, max) {
    if (v < min) return min;
    if (v > max) return max;
    return v;
}

function _tvToNumber(v, fallback) {
    var n = Number(v);
    return isFinite(n) ? n : fallback;
}

function _tvColorToHex(color, fallback) {
    if (!color || typeof color !== 'string') return fallback || '#aeb4c2';
    var c = color.trim();
    if (/^#[0-9a-f]{6}$/i.test(c)) return c;
    if (/^#[0-9a-f]{3}$/i.test(c)) {
        return '#' + c[1] + c[1] + c[2] + c[2] + c[3] + c[3];
    }
    var m = c.match(/rgba?\s*\(([^)]+)\)/i);
    if (!m) return fallback || '#aeb4c2';
    var parts = m[1].split(',');
    if (parts.length < 3) return fallback || '#aeb4c2';
    var r = _tvClamp(Math.round(_tvToNumber(parts[0], 0)), 0, 255);
    var g = _tvClamp(Math.round(_tvToNumber(parts[1], 0)), 0, 255);
    var b = _tvClamp(Math.round(_tvToNumber(parts[2], 0)), 0, 255);
    var hex = '#';
    var vals = [r, g, b];
    for (var i = 0; i < vals.length; i++) {
        var h = vals[i].toString(16);
        if (h.length < 2) h = '0' + h;
        hex += h;
    }
    return hex;
}

function _tvColorOpacityPercent(color, fallback) {
    if (!color || typeof color !== 'string') return fallback != null ? fallback : 100;
    var m = color.trim().match(/rgba\s*\(([^)]+)\)/i);
    if (!m) return fallback != null ? fallback : 100;
    var parts = m[1].split(',');
    if (parts.length < 4) return fallback != null ? fallback : 100;
    var alpha = _tvClamp(_tvToNumber(parts[3], 1), 0, 1);
    return Math.round(alpha * 100);
}

function _tvColorWithOpacity(color, opacityPercent, fallback) {
    var baseHex = _tvColorToHex(color, fallback || '#aeb4c2');
    var rgb = _hexToRgb(baseHex);
    var alpha = _tvClamp(_tvToNumber(opacityPercent, 100), 0, 100) / 100;
    return 'rgba(' + rgb[0] + ', ' + rgb[1] + ', ' + rgb[2] + ', ' + alpha.toFixed(2) + ')';
}

function _tvHexToRgba(color, alpha) {
    var hex = _tvColorToHex(color, '#aeb4c2');
    var rgb = _hexToRgb(hex);
    var a = typeof alpha === 'number' ? alpha : 1;
    return 'rgba(' + rgb[0] + ', ' + rgb[1] + ', ' + rgb[2] + ', ' + a.toFixed(2) + ')';
}

function _tvLineStyleFromName(name) {
    if (name === 'Dashed') return 2;
    if (name === 'Dotted') return 1;
    return 0;
}

function _tvGetMainSeries(entry) {
    if (!entry || !entry.seriesMap) return null;
    var keys = Object.keys(entry.seriesMap);
    if (!keys.length) return null;
    return entry.seriesMap[keys[0]];
}

function _tvBuildCurrentSettings(entry) {
    var mainSeries = _tvGetMainSeries(entry);
    var mainOpts = {};
    try {
        if (mainSeries && typeof mainSeries.options === 'function') {
            mainOpts = mainSeries.options() || {};
        }
    } catch (e) {
        mainOpts = {};
    }

    var prefs = entry && entry._chartPrefs ? entry._chartPrefs : {};
    var intervalEl = _tvScopedById(entry && entry.chartId ? entry.chartId : null, 'tvchart-interval-label');
    var hasVolume = !!(entry && entry.volumeMap && entry.volumeMap.main);
    // In datafeed mode, volume loads asynchronously — default to true
    if (!hasVolume && entry && entry.payload && entry.payload.useDatafeed) {
        hasVolume = true;
    }
    var palette = TVCHART_THEMES._get((entry && entry.theme) || _tvDetectTheme());

    return {
        'Color bars based on previous close': !!prefs.colorBarsBasedOnPrevClose,
        'Body': prefs.bodyVisible !== false,
        'Body-Up Color': prefs.bodyUpColor || mainOpts.upColor || palette.upColor,
        'Body-Down Color': prefs.bodyDownColor || mainOpts.downColor || palette.downColor,
        'Body-Up Color-Opacity': prefs.bodyUpOpacity != null ? String(prefs.bodyUpOpacity) : String(_tvColorOpacityPercent(mainOpts.upColor || palette.upColor, prefs.bodyOpacity != null ? prefs.bodyOpacity : 100)),
        'Body-Down Color-Opacity': prefs.bodyDownOpacity != null ? String(prefs.bodyDownOpacity) : String(_tvColorOpacityPercent(mainOpts.downColor || palette.downColor, prefs.bodyOpacity != null ? prefs.bodyOpacity : 100)),
        'Body-Opacity': prefs.bodyOpacity != null ? String(prefs.bodyOpacity) : String(_tvColorOpacityPercent(mainOpts.upColor || palette.upColor, 100)),
        'Borders': prefs.bordersVisible !== false,
        'Borders-Up Color': prefs.borderUpColor || mainOpts.borderUpColor || palette.borderUpColor,
        'Borders-Down Color': prefs.borderDownColor || mainOpts.borderDownColor || palette.borderDownColor,
        'Borders-Up Color-Opacity': prefs.borderUpOpacity != null ? String(prefs.borderUpOpacity) : String(_tvColorOpacityPercent(mainOpts.borderUpColor || palette.borderUpColor, prefs.borderOpacity != null ? prefs.borderOpacity : 100)),
        'Borders-Down Color-Opacity': prefs.borderDownOpacity != null ? String(prefs.borderDownOpacity) : String(_tvColorOpacityPercent(mainOpts.borderDownColor || palette.borderDownColor, prefs.borderOpacity != null ? prefs.borderOpacity : 100)),
        'Borders-Opacity': prefs.borderOpacity != null ? String(prefs.borderOpacity) : String(_tvColorOpacityPercent(mainOpts.borderUpColor || palette.borderUpColor, 100)),
        'Wick': prefs.wickVisible !== false,
        'Wick-Up Color': prefs.wickUpColor || mainOpts.wickUpColor || palette.wickUpColor,
        'Wick-Down Color': prefs.wickDownColor || mainOpts.wickDownColor || palette.wickDownColor,
        'Wick-Up Color-Opacity': prefs.wickUpOpacity != null ? String(prefs.wickUpOpacity) : String(_tvColorOpacityPercent(mainOpts.wickUpColor || palette.wickUpColor, prefs.wickOpacity != null ? prefs.wickOpacity : 100)),
        'Wick-Down Color-Opacity': prefs.wickDownOpacity != null ? String(prefs.wickDownOpacity) : String(_tvColorOpacityPercent(mainOpts.wickDownColor || palette.wickDownColor, prefs.wickOpacity != null ? prefs.wickOpacity : 100)),
        'Wick-Opacity': prefs.wickOpacity != null ? String(prefs.wickOpacity) : String(_tvColorOpacityPercent(mainOpts.wickUpColor || palette.wickUpColor, 100)),
        // Bar-specific
        'Bar Up Color': prefs.barUpColor || mainOpts.upColor || palette.upColor,
        'Bar Down Color': prefs.barDownColor || mainOpts.downColor || palette.downColor,
        // Area-specific
        'Area Fill Top': prefs.areaFillTop || mainOpts.topColor || 'rgba(38, 166, 154, 0.4)',
        'Area Fill Bottom': prefs.areaFillBottom || mainOpts.bottomColor || 'rgba(38, 166, 154, 0)',
        // Baseline-specific
        'Baseline Level': prefs.baselineLevel != null ? String(prefs.baselineLevel) : String((mainOpts.baseValue && mainOpts.baseValue.price) || 0),
        'Baseline Top Line': prefs.baselineTopLine || mainOpts.topLineColor || palette.upColor,
        'Baseline Bottom Line': prefs.baselineBottomLine || mainOpts.bottomLineColor || palette.downColor,
        'Baseline Top Fill 1': prefs.baselineTopFill1 || mainOpts.topFillColor1 || 'rgba(38, 166, 154, 0.28)',
        'Baseline Top Fill 2': prefs.baselineTopFill2 || mainOpts.topFillColor2 || 'rgba(38, 166, 154, 0.05)',
        'Baseline Bottom Fill 1': prefs.baselineBottomFill1 || mainOpts.bottomFillColor1 || 'rgba(239, 83, 80, 0.05)',
        'Baseline Bottom Fill 2': prefs.baselineBottomFill2 || mainOpts.bottomFillColor2 || 'rgba(239, 83, 80, 0.28)',
        'Session': prefs.session || 'Regular trading hours',
        'Precision': prefs.precision || 'Default',
        'Timezone': prefs.timezone || 'UTC',
        'Logo': prefs.showLogo !== undefined ? prefs.showLogo : false,
        'Title': prefs.showTitle !== undefined ? prefs.showTitle : true,
        'Description': prefs.description || 'Description',
        'Chart values': prefs.showChartValues !== undefined ? prefs.showChartValues : true,
        'Bar change values': prefs.showBarChange !== undefined ? prefs.showBarChange : true,
        'Volume': prefs.showVolume !== undefined ? prefs.showVolume : hasVolume,
        'Titles': prefs.showIndicatorTitles !== undefined ? prefs.showIndicatorTitles : true,
        'Inputs': prefs.showIndicatorInputs !== undefined ? prefs.showIndicatorInputs : true,
        'Values': prefs.showIndicatorValues !== undefined ? prefs.showIndicatorValues : true,
        'Background-Enabled': prefs.backgroundEnabled !== false,
        'Background-Opacity': prefs.backgroundOpacity != null ? String(prefs.backgroundOpacity) : '50',
        'Line style': mainOpts.lineStyle === 2 ? 'Dashed' : (mainOpts.lineStyle === 1 ? 'Dotted' : 'Solid'),
        'Line width': String(mainOpts.lineWidth || 1),
        'Line color': mainOpts.color || mainOpts.lineColor || prefs.lineColor || _cssVar('--pywry-tvchart-up', ''),
        'Scale modes (A and L)': prefs.scaleModesVisibility || 'Visible on mouse over',
        'Lock price to bar ratio': !!prefs.lockPriceToBarRatio,
        'Lock price to bar ratio (value)': prefs.lockPriceToBarRatioValue != null ? String(prefs.lockPriceToBarRatioValue) : '0.018734',
        'Scales placement': prefs.scalesPlacement || 'Auto',
        'No overlapping labels': prefs.noOverlappingLabels !== false,
        'Plus button': !!prefs.plusButton,
        'Countdown to bar close': !!prefs.countdownToBarClose,
        'Symbol': prefs.symbolMode || (function() {
            var pv = mainOpts.priceLineVisible !== false;
            var lv = mainOpts.lastValueVisible !== false;
            if (pv && lv) return 'Value, line';
            if (pv && !lv) return 'Line';
            if (!pv && lv) return 'Label';
            return 'Hidden';
        })(),
        'Symbol color': prefs.symbolColor || mainOpts.color || mainOpts.lineColor || _cssVar('--pywry-tvchart-up', ''),
        'Value according to scale': prefs.valueAccordingToScale || 'Value according to scale',
        'Value according to sc...': prefs.valueAccordingToScale || 'Value according to scale',
        'Indicators and financials': prefs.indicatorsAndFinancials || 'Value',
        'High and low': prefs.highAndLow || 'Hidden',
        'High and low color': prefs.highAndLowColor || _cssVar('--pywry-tvchart-down', ''),
        'Day of week on labels': prefs.dayOfWeekOnLabels !== false,
        'Date format': prefs.dateFormat || 'Mon 29 Sep \'97',
        'Time hours format': prefs.timeHoursFormat || '24-hours',
        'Background': 'Solid',
        'Background-Color': prefs.backgroundColor || palette.background,
        'Grid lines': prefs.gridVisible === false ? 'Hidden' : (prefs.gridMode || 'Vert and horz'),
        'Grid-Color': prefs.gridColor || _cssVar('--pywry-tvchart-grid'),
        'Pane-Separators-Color': prefs.paneSeparatorsColor || _cssVar('--pywry-tvchart-grid'),
        'Crosshair-Enabled': prefs.crosshairEnabled === true,
        'Crosshair-Color': prefs.crosshairColor || _cssVar('--pywry-tvchart-crosshair-color'),
        'Watermark': prefs.watermarkVisible ? 'Visible' : 'Hidden',
        'Watermark-Color': prefs.watermarkColor || 'rgba(255,255,255,0.08)',
        'Text-Color': prefs.textColor || _cssVar('--pywry-tvchart-text'),
        'Lines-Color': prefs.linesColor || _cssVar('--pywry-tvchart-grid'),
        'Navigation': prefs.navigation || 'Visible on mouse over',
        'Pane': prefs.pane || 'Visible on mouse over',
        'Margin Top': prefs.marginTop != null ? String(prefs.marginTop) : '10',
        'Margin Bottom': prefs.marginBottom != null ? String(prefs.marginBottom) : '8',
        'Interval': intervalEl ? (intervalEl.textContent || '').trim() : '',
    };
}

function _tvSetToolbarVisibility(settings, chartId) {
    var leftToolbar = _tvScopedQuery(chartId, '.tvchart-left');
    var bottomToolbar = _tvScopedQuery(chartId, '.tvchart-bottom');
    if (leftToolbar) {
        leftToolbar.style.display = settings['Navigation'] === 'Hidden' ? 'none' : '';
    }
    if (bottomToolbar) {
        bottomToolbar.style.display = settings['Pane'] === 'Hidden' ? 'none' : '';
    }

    var autoScaleEl = _tvScopedQuery(chartId, '[data-component-id="tvchart-auto-scale"]');
    var logScaleEl = _tvScopedQuery(chartId, '[data-component-id="tvchart-log-scale"]');
    var pctScaleEl = _tvScopedQuery(chartId, '[data-component-id="tvchart-pct-scale"]');
    var showScaleButtons = settings['Scale modes (A and L)'] !== 'Hidden';
    if (autoScaleEl) autoScaleEl.style.display = showScaleButtons ? '' : 'none';
    if (logScaleEl) logScaleEl.style.display = showScaleButtons ? '' : 'none';
    if (pctScaleEl) pctScaleEl.style.display = showScaleButtons ? '' : 'none';
}

function _tvApplySettingsToChart(chartId, entry, settings, opts) {
    if (!entry || !entry.chart) return;
    opts = opts || {};

    var chartOptions = {};
    var rightPriceScale = {};
    var leftPriceScale = {};
    var timeScale = {};
    var localization = {};

    // Canvas: grid visibility
    var gridMode = settings['Grid lines'] || 'Vert and horz';
    var gridColor = settings['Grid-Color'] || settings['Lines-Color'] || undefined;
    chartOptions.grid = {
        vertLines: {
            visible: gridMode === 'Vert and horz' || gridMode === 'Vert only',
            color: gridColor,
        },
        horzLines: {
            visible: gridMode === 'Vert and horz' || gridMode === 'Horz only',
            color: gridColor,
        },
    };

    // Canvas: background + text + crosshair
    var bgOpacity = _tvClamp(_tvToNumber(settings['Background-Opacity'], 50), 0, 100) / 100;
    var bgEnabled = settings['Background-Enabled'] !== false;
    var _bgPalette = TVCHART_THEMES._get((entry && entry.theme) || _tvDetectTheme());
    var bgColor = settings['Background-Color'] || _bgPalette.background;
    // Apply opacity to background color
    var bgHex = _tvColorToHex(bgColor, _bgPalette.background);
    var bgFinal = bgEnabled ? _tvColorWithOpacity(bgHex, bgOpacity * 100, bgHex) : 'transparent';
    chartOptions.layout = {
        attributionLogo: false,
        textColor: settings['Text-Color'] || undefined,
        background: {
            type: 'solid',
            color: bgFinal,
        },
    };

    var _chEn = settings['Crosshair-Enabled'] === true;
    chartOptions.crosshair = {
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine: {
            color: settings['Crosshair-Color'] || undefined,
            visible: _chEn,
            labelVisible: true,
            style: 2,
            width: 1,
        },
        horzLine: {
            color: settings['Crosshair-Color'] || undefined,
            visible: _chEn,
            labelVisible: _chEn,
            style: 2,
            width: 1,
        },
    };

    // Status/scales — apply same config to both sides
    var scaleAutoScale = settings['Auto Scale'] !== false;
    var scaleMode = settings['Log scale'] === true ? 1 : 0;
    var scaleAlignLabels = settings['No overlapping labels'] !== false;
    var scaleTextColor = settings['Text-Color'] || undefined;
    var scaleBorderColor = settings['Lines-Color'] || undefined;

    rightPriceScale.autoScale = scaleAutoScale;
    rightPriceScale.mode = scaleMode;
    rightPriceScale.alignLabels = scaleAlignLabels;
    rightPriceScale.textColor = scaleTextColor;
    rightPriceScale.borderColor = scaleBorderColor;

    leftPriceScale.autoScale = scaleAutoScale;
    leftPriceScale.mode = scaleMode;
    leftPriceScale.alignLabels = scaleAlignLabels;
    leftPriceScale.textColor = scaleTextColor;
    leftPriceScale.borderColor = scaleBorderColor;

    var topMargin = _tvClamp(_tvToNumber(settings['Margin Top'], 10), 0, 90) / 100;
    var bottomMargin = _tvClamp(_tvToNumber(settings['Margin Bottom'], 8), 0, 90) / 100;
    if (entry.volumeMap && entry.volumeMap.main) {
        bottomMargin = Math.max(bottomMargin, 0.14);
    }
    rightPriceScale.scaleMargins = { top: topMargin, bottom: bottomMargin };
    leftPriceScale.scaleMargins = { top: topMargin, bottom: bottomMargin };

    if (settings['Lock price to bar ratio']) {
        var ratio = _tvClamp(_tvToNumber(settings['Lock price to bar ratio (value)'], 0.018734), 0.001, 0.95);
        var lockedMargins = {
            top: _tvClamp(ratio, 0.0, 0.9),
            bottom: _tvClamp(1 - ratio - 0.05, 0.0, 0.9),
        };
        rightPriceScale.autoScale = false;
        rightPriceScale.scaleMargins = lockedMargins;
        leftPriceScale.autoScale = false;
        leftPriceScale.scaleMargins = lockedMargins;
    }

    var placement = settings['Scales placement'] || 'Auto';
    if (placement === 'Left') {
        leftPriceScale.visible = true;
        rightPriceScale.visible = false;
    } else if (placement === 'Right') {
        leftPriceScale.visible = false;
        rightPriceScale.visible = true;
    } else {
        leftPriceScale.visible = false;
        rightPriceScale.visible = true;
    }

    timeScale.borderColor = settings['Lines-Color'] || undefined;
    timeScale.secondsVisible = false;
    // Daily+ charts should never show time on the x-axis
    var _resIsDaily = (function() {
        var r = entry._currentResolution || '';
        return /^[1-9]?[DWM]$/.test(r) || /^\d+[DWM]$/.test(r);
    })();

    // Skip timeVisible and localization overrides when the datafeed already
    // set timezone-aware formatters (deferred re-apply after series creation).
    if (!opts.skipLocalization) {
        timeScale.timeVisible = !_resIsDaily;

        var showDOW = settings['Day of week on labels'] !== false;
        var use24h = (settings['Time hours format'] || '24-hours') === '24-hours';
        var dateFmt = settings['Date format'] || 'Mon 29 Sep \'97';
        var useUTC = (settings['Timezone'] || 'UTC') === 'UTC';
        localization.timeFormatter = function(t) {
        var d;
        if (typeof t === 'number') {
            d = new Date(t * 1000);
        } else if (t && typeof t.year === 'number') {
            d = useUTC
                ? new Date(Date.UTC(t.year, (t.month || 1) - 1, t.day || 1))
                : new Date(t.year, (t.month || 1) - 1, t.day || 1);
        } else {
            return '';
        }
        var days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        var monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        var month = useUTC ? d.getUTCMonth() : d.getMonth();
        var day = useUTC ? d.getUTCDate() : d.getDate();
        var year = useUTC ? d.getUTCFullYear() : d.getFullYear();
        var hour = useUTC ? d.getUTCHours() : d.getHours();
        var minute = useUTC ? d.getUTCMinutes() : d.getMinutes();
        var weekDay = useUTC ? d.getUTCDay() : d.getDay();
        var mm = String(month + 1);
        var dd = String(day);
        var yyyy = String(year);
        var yy = yyyy.slice(-2);
        var hours = use24h ? hour : ((hour % 12) || 12);
        var mins = String(minute).padStart(2, '0');
        var ampm = hour >= 12 ? ' PM' : ' AM';
        var time = use24h ? String(hours).padStart(2, '0') + ':' + mins : String(hours) + ':' + mins + ampm;
        var datePart;
        if (dateFmt === 'MM/DD/YY') {
            datePart = mm.padStart(2, '0') + '/' + dd.padStart(2, '0') + '/' + yy;
        } else if (dateFmt === 'DD/MM/YY') {
            datePart = dd.padStart(2, '0') + '/' + mm.padStart(2, '0') + '/' + yy;
        } else {
            datePart = dd.padStart(2, '0') + ' ' + monthNames[month] + " '" + yy;
        }
        if (_resIsDaily) {
            return (showDOW ? (days[weekDay] + ' ') : '') + datePart;
        }
        return (showDOW ? (days[weekDay] + ' ') : '') + datePart + ' ' + time;
    };
    } // end skipLocalization guard
    chartOptions.rightPriceScale = rightPriceScale;
    chartOptions.leftPriceScale = leftPriceScale;
    chartOptions.timeScale = timeScale;
    chartOptions.localization = localization;
    chartOptions = _tvMerge(chartOptions, _tvInteractiveNavigationOptions());

    // Watermark
    var wmColor = settings['Watermark-Color'] || 'rgba(255,255,255,0.08)';
    chartOptions.watermark = {
        visible: settings['Watermark'] === 'Visible',
        text: settings['Title'] === false ? '' : 'OHLCV Demo',
        color: wmColor,
        fontSize: 24,
    };

    entry.chart.applyOptions(chartOptions);
    _tvEnsureInteractiveNavigation(entry);
    _tvApplyHoverReadoutMode(entry);

    // Move main series to the correct price scale side
    var targetScaleId = placement === 'Left' ? 'left' : 'right';
    var mainSeries = _tvGetMainSeries(entry);
    if (mainSeries) {
        try { mainSeries.applyOptions({ priceScaleId: targetScaleId }); } catch (e) {}
    }

    _tvApplyCustomScaleSide(entry, targetScaleId, {
        alignLabels: settings['No overlapping labels'] !== false,
        textColor: settings['Text-Color'] || undefined,
        borderColor: settings['Lines-Color'] || undefined,
    });

    // Apply main-series options (price labels and line from Symbol mode)
    if (!mainSeries) mainSeries = _tvGetMainSeries(entry);
    if (mainSeries) {
        var stype = _tvGuessSeriesType(mainSeries);
        var lineColor = settings['Line color'] || settings['Symbol color'] || undefined;
        var lw = _tvClamp(_tvToNumber(settings['Line width'], 1), 1, 4);
        var ls = _tvLineStyleFromName(settings['Line style']);
        // Derive price line/label visibility from Symbol dropdown (Scales & Lines tab)
        var symbolMode = settings['Symbol'] || 'Value, line';
        var showPriceLabel = symbolMode === 'Value, line' || symbolMode === 'Label';
        var showPriceLine = symbolMode === 'Value, line' || symbolMode === 'Line';
        var symbolColor = settings['Symbol color'] || _cssVar('--pywry-tvchart-up', '#26a69a');
        var sOpts = {
            lastValueVisible: showPriceLabel,
            priceLineVisible: showPriceLine,
            priceLineColor: symbolColor,
        };
        if (stype === 'Line' || stype === 'Area' || stype === 'Baseline' || stype === 'Histogram') {
            sOpts.lineStyle = ls;
            sOpts.lineWidth = lw;
            sOpts.color = lineColor;
            sOpts.lineColor = lineColor;
        }
        if (stype === 'Area') {
            if (settings['Area Fill Top']) sOpts.topColor = settings['Area Fill Top'];
            if (settings['Area Fill Bottom']) sOpts.bottomColor = settings['Area Fill Bottom'];
        }
        if (stype === 'Baseline') {
            var bLevel = _tvToNumber(settings['Baseline Level'], 0);
            sOpts.baseValue = { price: bLevel, type: 'price' };
            if (settings['Baseline Top Line']) sOpts.topLineColor = settings['Baseline Top Line'];
            if (settings['Baseline Bottom Line']) sOpts.bottomLineColor = settings['Baseline Bottom Line'];
            if (settings['Baseline Top Fill 1']) sOpts.topFillColor1 = settings['Baseline Top Fill 1'];
            if (settings['Baseline Top Fill 2']) sOpts.topFillColor2 = settings['Baseline Top Fill 2'];
            if (settings['Baseline Bottom Fill 1']) sOpts.bottomFillColor1 = settings['Baseline Bottom Fill 1'];
            if (settings['Baseline Bottom Fill 2']) sOpts.bottomFillColor2 = settings['Baseline Bottom Fill 2'];
        }
        if (stype === 'Bar') {
            if (settings['Bar Up Color']) sOpts.upColor = settings['Bar Up Color'];
            if (settings['Bar Down Color']) sOpts.downColor = settings['Bar Down Color'];
        }
        if (stype === 'Candlestick' || stype === 'Bar') {
            var bodyVisible = settings['Body'] !== false;
            var bodyUpOpacity = _tvClamp(_tvToNumber(settings['Body-Up Color-Opacity'], settings['Body-Opacity']), 0, 100);
            var bodyDownOpacity = _tvClamp(_tvToNumber(settings['Body-Down Color-Opacity'], settings['Body-Opacity']), 0, 100);
            var borderUpOpacity = _tvClamp(_tvToNumber(settings['Borders-Up Color-Opacity'], settings['Borders-Opacity']), 0, 100);
            var borderDownOpacity = _tvClamp(_tvToNumber(settings['Borders-Down Color-Opacity'], settings['Borders-Opacity']), 0, 100);
            var wickUpOpacity = _tvClamp(_tvToNumber(settings['Wick-Up Color-Opacity'], settings['Wick-Opacity']), 0, 100);
            var wickDownOpacity = _tvClamp(_tvToNumber(settings['Wick-Down Color-Opacity'], settings['Wick-Opacity']), 0, 100);
            var bodyHidden = _cssVar('--pywry-tvchart-hidden') || 'rgba(0, 0, 0, 0)';
            sOpts.upColor = bodyVisible ? _tvColorWithOpacity(settings['Body-Up Color'], bodyUpOpacity, _cssVar('--pywry-tvchart-up', '#26a69a')) : bodyHidden;
            sOpts.downColor = bodyVisible ? _tvColorWithOpacity(settings['Body-Down Color'], bodyDownOpacity, _cssVar('--pywry-tvchart-down', '#ef5350')) : bodyHidden;
            sOpts.borderVisible = settings['Borders'] !== false;
            sOpts.borderUpColor = _tvColorWithOpacity(settings['Borders-Up Color'], borderUpOpacity, _cssVar('--pywry-tvchart-border-up', '#26a69a'));
            sOpts.borderDownColor = _tvColorWithOpacity(settings['Borders-Down Color'], borderDownOpacity, _cssVar('--pywry-tvchart-border-down', '#ef5350'));
            sOpts.wickVisible = settings['Wick'] !== false;
            sOpts.wickUpColor = _tvColorWithOpacity(settings['Wick-Up Color'], wickUpOpacity, _cssVar('--pywry-tvchart-wick-up', '#26a69a'));
            sOpts.wickDownColor = _tvColorWithOpacity(settings['Wick-Down Color'], wickDownOpacity, _cssVar('--pywry-tvchart-wick-down', '#ef5350'));
        }
        if (settings['Precision'] && settings['Precision'] !== 'Default') {
            var minMove = Number(settings['Precision']);
            if (isFinite(minMove) && minMove > 0) {
                var decimals = String(settings['Precision']).indexOf('.') >= 0
                    ? String(settings['Precision']).split('.')[1].length
                    : 0;
                sOpts.priceFormat = { type: 'price', precision: decimals, minMove: minMove };
            }
        }
        mainSeries.applyOptions(sOpts);
    }

    // Volume label visibility in the status line / legend.
    // This does NOT create or destroy the volume subplot — it only controls
    // whether the "Volume 31.29 M" text appears in the legend header.
    // The legend updater reads legendBox.dataset.showVolume below.

    _tvSetToolbarVisibility(settings, chartId);

    // Persist legend and scale behavior flags for the legend updater script.
    var legendBox = _tvScopedById(chartId, 'tvchart-legend-box');
    if (legendBox) {
        var baseTitle = 'Symbol';
        if (entry.payload && entry.payload.useDatafeed && entry.payload.series && entry.payload.series[0] && entry.payload.series[0].symbol) {
            baseTitle = String(entry.payload.series[0].symbol);
        } else if (entry.payload && entry.payload.title) {
            baseTitle = String(entry.payload.title);
        } else if (entry.payload && entry.payload.series && entry.payload.series[0] && entry.payload.series[0].seriesId) {
            var sid = String(entry.payload.series[0].seriesId);
            if (sid && sid !== 'main') baseTitle = sid;
        }
        var intervalEl = _tvScopedById(chartId, 'tvchart-interval-label');

        legendBox.dataset.baseTitle = baseTitle;
        legendBox.dataset.interval = intervalEl ? (intervalEl.textContent || '').trim() : '';
        legendBox.dataset.showLogo = settings['Logo'] === false ? '0' : '1';
        legendBox.dataset.showTitle = settings['Title'] === false ? '0' : '1';
        legendBox.dataset.description = settings['Description'] || 'Description';
        legendBox.dataset.showChartValues = settings['Chart values'] === false ? '0' : '1';
        legendBox.dataset.showBarChange = settings['Bar change values'] === false ? '0' : '1';
        legendBox.dataset.showVolume = settings['Volume'] !== false ? '1' : '0';
        legendBox.dataset.showIndicatorTitles = settings['Titles'] === false ? '0' : '1';
        legendBox.dataset.showIndicatorInputs = settings['Inputs'] === false ? '0' : '1';
        legendBox.dataset.showIndicatorValues = settings['Values'] === false ? '0' : '1';
        legendBox.dataset.showStatusValues = settings['Chart values'] === false ? '0' : '1';
        legendBox.dataset.symbolMode = settings['Symbol'] || 'Value, line';
        legendBox.dataset.valueMode = settings['Value according to scale'] || settings['Value according to sc...'] || 'Value according to scale';
        legendBox.dataset.financialsMode = settings['Indicators and financials'] || 'Value';
        legendBox.dataset.highLowMode = settings['High and low'] || 'Hidden';
        legendBox.dataset.symbolColor = settings['Symbol color'] || '';
        legendBox.dataset.highLowColor = settings['High and low color'] || '';
        legendBox.dataset.lineColor = settings['Line color'] || '';
        legendBox.dataset.textColor = settings['Text-Color'] || '';
    }

    // Plus button mock on right scale edge.
    var container = entry.container || (entry.chart && entry.chart._container) || null;
    if (container) {
        var plusId = 'tvchart-plus-button-' + chartId;
        var plusEl = document.getElementById(plusId);
        if (!plusEl) {
            plusEl = document.createElement('div');
            plusEl.id = plusId;
            plusEl.className = 'pywry-tvchart-plus-button';
            plusEl.textContent = '+';
            container.appendChild(plusEl);
        }
        plusEl.style.display = settings['Plus button'] ? 'block' : 'none';

        var cdId = 'tvchart-countdown-label-' + chartId;
        var cdEl = document.getElementById(cdId);
        if (!cdEl) {
            cdEl = document.createElement('div');
            cdEl.id = cdId;
            cdEl.className = 'pywry-tvchart-countdown';
            container.appendChild(cdEl);
        }
        if (settings['Countdown to bar close']) {
            cdEl.style.display = 'block';
            cdEl.textContent = 'CLOSE TIMER';
        } else {
            cdEl.style.display = 'none';
        }
    }

    // Notify legend to re-render with updated dataset flags
    try {
        window.dispatchEvent(new CustomEvent('pywry:legend-refresh', { detail: { chartId: chartId } }));
    } catch (_e) {}

}

function _tvToPixel(chartId, time, price) {
    var e = window.__PYWRY_TVCHARTS__[chartId];
    if (!e || !e.chart) return null;
    var s = _tvMainSeries(chartId);
    var x = e.chart.timeScale().timeToCoordinate(time);
    var y = s ? s.priceToCoordinate(price) : null;
    if (x === null || y === null) return null;
    return { x: x, y: y };
}

function _tvFromPixel(chartId, x, y) {
    var e = window.__PYWRY_TVCHARTS__[chartId];
    if (!e || !e.chart) return null;
    var s = _tvMainSeries(chartId);
    var time  = e.chart.timeScale().coordinateToTime(x);
    var price = s ? s.coordinateToPrice(y) : null;
    return { time: time, price: price };
}

// ---- Get drawing anchor points in pixel coords ----
function _tvDrawAnchors(chartId, d) {
    var s = _tvMainSeries(chartId);
    if (!s) return [];
    if (d.type === 'hline') {
        var yH = s.priceToCoordinate(d.price);
        var viewport = _tvGetDrawingViewport(chartId);
        return yH !== null ? [{ key: 'price', x: Math.min(viewport.right - 24, viewport.left + 40), y: yH }] : [];
    }
    if (d.type === 'vline') {
        var vA = _tvToPixel(chartId, d.t1, 0);
        return vA ? [{ key: 'p1', x: vA.x, y: vA.y || 40 }] : [];
    }
    if (d.type === 'crossline') {
        var clA = _tvToPixel(chartId, d.t1, d.p1);
        return clA ? [{ key: 'p1', x: clA.x, y: clA.y }] : [];
    }
    if (d.type === 'flat_channel') {
        var fcY1 = s.priceToCoordinate(d.p1);
        var fcY2 = s.priceToCoordinate(d.p2);
        var fcVp = _tvGetDrawingViewport(chartId);
        var fcPts = [];
        if (fcY1 !== null) fcPts.push({ key: 'p1', x: fcVp.left + 40, y: fcY1 });
        if (fcY2 !== null) fcPts.push({ key: 'p2', x: fcVp.left + 40, y: fcY2 });
        return fcPts;
    }
    if (d.type === 'brush' || d.type === 'highlighter') {
        // No draggable anchors for brush/highlighter strokes
        return [];
    }
    if (d.type === 'path' || d.type === 'polyline') {
        // Anchors at each vertex
        var mpts = d.points;
        var anchors = [];
        if (mpts) {
            for (var mi = 0; mi < mpts.length; mi++) {
                var mpp = _tvToPixel(chartId, mpts[mi].t, mpts[mi].p);
                if (mpp) anchors.push({ key: 'pt' + mi, x: mpp.x, y: mpp.y });
            }
        }
        return anchors;
    }
    // Single-point tools
    var singlePointTools = ['arrow_mark_up', 'arrow_mark_down', 'arrow_mark_left', 'arrow_mark_right', 'anchored_vwap'];
    if (singlePointTools.indexOf(d.type) !== -1) {
        var sp = _tvToPixel(chartId, d.t1, d.p1);
        return sp ? [{ key: 'p1', x: sp.x, y: sp.y }] : [];
    }
    var pts = [];
    if (d.t1 !== undefined) {
        var a = _tvToPixel(chartId, d.t1, d.p1);
        if (a) pts.push({ key: 'p1', x: a.x, y: a.y });
    }
    if (d.t2 !== undefined) {
        var b = _tvToPixel(chartId, d.t2, d.p2);
        if (b) pts.push({ key: 'p2', x: b.x, y: b.y });
    }
    var threePointAnchors = ['fib_extension', 'fib_channel', 'fib_wedge', 'pitchfan', 'fib_time',
                             'rotated_rect', 'triangle', 'shape_arc', 'double_curve'];
    if (d.t3 !== undefined && threePointAnchors.indexOf(d.type) !== -1) {
        var c = _tvToPixel(chartId, d.t3, d.p3);
        if (c) pts.push({ key: 'p3', x: c.x, y: c.y });
    }
    return pts;
}

// ---- Hit-testing: find drawing near pixel x,y ----
function _tvHitTest(chartId, mx, my) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds) return -1;
    var viewport = _tvGetDrawingViewport(chartId);
    if (mx < viewport.left || mx > viewport.right || my < viewport.top || my > viewport.bottom) return -1;
    var THRESH = 8;
    // Iterate in reverse so topmost drawing is picked first
    for (var i = ds.drawings.length - 1; i >= 0; i--) {
        var d = ds.drawings[i];
        if (d.hidden) continue;
        if (_tvDrawHit(chartId, d, mx, my, THRESH)) return i;
    }
    return -1;
}

function _tvDrawHit(chartId, d, mx, my, T) {
    var s = _tvMainSeries(chartId);
    if (!s) return false;
    var viewport = _tvGetDrawingViewport(chartId);

    if (mx < viewport.left - T || mx > viewport.right + T || my < viewport.top - T || my > viewport.bottom + T) {
        return false;
    }

    if (d.type === 'hline') {
        var yH = s.priceToCoordinate(d.price);
        return yH !== null && mx >= viewport.left && mx <= viewport.right && Math.abs(my - yH) < T;
    }
    if (d.type === 'trendline' || d.type === 'channel' || d.type === 'ray' || d.type === 'extended_line' || d.type === 'regression_channel') {
        var a = _tvToPixel(chartId, d.t1, d.p1);
        var b = _tvToPixel(chartId, d.t2, d.p2);
        if (!a || !b) return false;
        // For ray: extend from a through b
        if (d.type === 'ray') {
            var rdx = b.x - a.x, rdy = b.y - a.y;
            var rlen = Math.sqrt(rdx * rdx + rdy * rdy);
            if (rlen > 0) {
                var bExt = { x: a.x + (rdx / rlen) * 4000, y: a.y + (rdy / rlen) * 4000 };
                if (_distToSeg(mx, my, a.x, a.y, bExt.x, bExt.y) < T) return true;
            }
            return false;
        }
        // For extended_line: extend in both directions
        if (d.type === 'extended_line') {
            var edx = b.x - a.x, edy = b.y - a.y;
            var elen = Math.sqrt(edx * edx + edy * edy);
            if (elen > 0) {
                var aExt = { x: a.x - (edx / elen) * 4000, y: a.y - (edy / elen) * 4000 };
                var bExt2 = { x: b.x + (edx / elen) * 4000, y: b.y + (edy / elen) * 4000 };
                if (_distToSeg(mx, my, aExt.x, aExt.y, bExt2.x, bExt2.y) < T) return true;
            }
            return false;
        }
        if (_distToSeg(mx, my, a.x, a.y, b.x, b.y) < T) return true;
        if (d.type === 'channel') {
            var off = d.offset || 30;
            if (_distToSeg(mx, my, a.x, a.y + off, b.x, b.y + off) < T) return true;
            // Inside fill
            var minY = Math.min(a.y, b.y);
            var maxY = Math.max(a.y, b.y) + off;
            var minX = Math.min(a.x, b.x);
            var maxX = Math.max(a.x, b.x);
            if (mx >= minX && mx <= maxX && my >= minY && my <= maxY) return true;
        }
        if (d.type === 'regression_channel') {
            var rcOff = d.offset || 30;
            if (_distToSeg(mx, my, a.x, a.y - rcOff, b.x, b.y - rcOff) < T) return true;
            if (_distToSeg(mx, my, a.x, a.y + rcOff, b.x, b.y + rcOff) < T) return true;
        }
        return false;
    }
    if (d.type === 'hray') {
        var hrY = s.priceToCoordinate(d.p1);
        var hrA = _tvToPixel(chartId, d.t1, d.p1);
        if (hrY === null || !hrA) return false;
        // Hit if near the horizontal line from anchor to right edge
        if (Math.abs(my - hrY) < T && mx >= hrA.x - T) return true;
        return false;
    }
    if (d.type === 'vline') {
        var vA = _tvToPixel(chartId, d.t1, d.p1 || 0);
        if (!vA) return false;
        if (Math.abs(mx - vA.x) < T) return true;
        return false;
    }
    if (d.type === 'crossline') {
        var clA = _tvToPixel(chartId, d.t1, d.p1);
        var clY = s.priceToCoordinate(d.p1);
        if (!clA || clY === null) return false;
        if (Math.abs(mx - clA.x) < T || Math.abs(my - clY) < T) return true;
        return false;
    }
    if (d.type === 'flat_channel') {
        var fcY1 = s.priceToCoordinate(d.p1);
        var fcY2 = s.priceToCoordinate(d.p2);
        if (fcY1 === null || fcY2 === null) return false;
        if (Math.abs(my - fcY1) < T || Math.abs(my - fcY2) < T) return true;
        var fcMin = Math.min(fcY1, fcY2), fcMax = Math.max(fcY1, fcY2);
        if (my >= fcMin && my <= fcMax) return true;
        return false;
    }
    if (d.type === 'brush') {
        var bpts = d.points;
        if (!bpts || bpts.length < 2) return false;
        for (var bi = 0; bi < bpts.length - 1; bi++) {
            var bpA = _tvToPixel(chartId, bpts[bi].t, bpts[bi].p);
            var bpB = _tvToPixel(chartId, bpts[bi + 1].t, bpts[bi + 1].p);
            if (bpA && bpB && _distToSeg(mx, my, bpA.x, bpA.y, bpB.x, bpB.y) < T) return true;
        }
        return false;
    }
    if (d.type === 'highlighter') {
        var hpts = d.points;
        if (!hpts || hpts.length < 2) return false;
        for (var hi = 0; hi < hpts.length - 1; hi++) {
            var hpA = _tvToPixel(chartId, hpts[hi].t, hpts[hi].p);
            var hpB = _tvToPixel(chartId, hpts[hi + 1].t, hpts[hi + 1].p);
            if (hpA && hpB && _distToSeg(mx, my, hpA.x, hpA.y, hpB.x, hpB.y) < T + 5) return true;
        }
        return false;
    }
    if (d.type === 'path' || d.type === 'polyline') {
        var mpts = d.points;
        if (!mpts || mpts.length < 2) return false;
        for (var mi = 0; mi < mpts.length - 1; mi++) {
            var mpA = _tvToPixel(chartId, mpts[mi].t, mpts[mi].p);
            var mpB = _tvToPixel(chartId, mpts[mi + 1].t, mpts[mi + 1].p);
            if (mpA && mpB && _distToSeg(mx, my, mpA.x, mpA.y, mpB.x, mpB.y) < T) return true;
        }
        // For path, also check closing segment
        if (d.type === 'path' && mpts.length > 2) {
            var mpFirst = _tvToPixel(chartId, mpts[0].t, mpts[0].p);
            var mpLast = _tvToPixel(chartId, mpts[mpts.length - 1].t, mpts[mpts.length - 1].p);
            if (mpFirst && mpLast && _distToSeg(mx, my, mpFirst.x, mpFirst.y, mpLast.x, mpLast.y) < T) return true;
        }
        return false;
    }
    if (d.type === 'rect') {
        var r1 = _tvToPixel(chartId, d.t1, d.p1);
        var r2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!r1 || !r2) return false;
        var lx = Math.min(r1.x, r2.x);
        var ly = Math.min(r1.y, r2.y);
        var rx = Math.max(r1.x, r2.x);
        var ry = Math.max(r1.y, r2.y);
        if (mx >= lx - T && mx <= rx + T && my >= ly - T && my <= ry + T) return true;
        return false;
    }
    if (d.type === 'fibonacci') {
        var fT = s.priceToCoordinate(d.p1);
        var fB = s.priceToCoordinate(d.p2);
        if (fT === null || fB === null) return false;
        var minFy = Math.min(fT, fB);
        var maxFy = Math.max(fT, fB);
        if (my >= minFy - T && my <= maxFy + T) return true;
        return false;
    }
    if (d.type === 'fib_extension') {
        var feA = _tvToPixel(chartId, d.t1, d.p1);
        var feB = _tvToPixel(chartId, d.t2, d.p2);
        if (!feA || !feB) return false;
        if (_distToSeg(mx, my, feA.x, feA.y, feB.x, feB.y) < T) return true;
        if (d.t3 !== undefined) {
            var feC = _tvToPixel(chartId, d.t3, d.p3);
            if (feC && _distToSeg(mx, my, feB.x, feB.y, feC.x, feC.y) < T) return true;
            // Hit on any visible extension level line
            if (feC) {
                var abR = d.p2 - d.p1;
                var fLvls = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
                for (var fi = 0; fi < fLvls.length; fi++) {
                    var yy = s.priceToCoordinate(d.p3 + abR * fLvls[fi]);
                    if (yy !== null && Math.abs(my - yy) < T) return true;
                }
            }
        }
        return false;
    }
    if (d.type === 'fib_channel') {
        var fcA = _tvToPixel(chartId, d.t1, d.p1);
        var fcB = _tvToPixel(chartId, d.t2, d.p2);
        if (!fcA || !fcB) return false;
        if (_distToSeg(mx, my, fcA.x, fcA.y, fcB.x, fcB.y) < T) return true;
        if (d.t3 !== undefined) {
            var fcC = _tvToPixel(chartId, d.t3, d.p3);
            if (fcC) {
                var abDx = fcB.x - fcA.x, abDy = fcB.y - fcA.y;
                var abLen = Math.sqrt(abDx * abDx + abDy * abDy);
                if (abLen > 0) {
                    var cOff = ((fcC.x - fcA.x) * (-abDy / abLen) + (fcC.y - fcA.y) * (abDx / abLen));
                    var px = -abDy / abLen, py = abDx / abLen;
                    if (_distToSeg(mx, my, fcA.x + px * cOff, fcA.y + py * cOff, fcB.x + px * cOff, fcB.y + py * cOff) < T) return true;
                }
            }
        }
        return false;
    }
    if (d.type === 'fib_timezone') {
        var ftzA = _tvToPixel(chartId, d.t1, d.p1);
        var ftzB = _tvToPixel(chartId, d.t2, d.p2);
        if (!ftzA || !ftzB) return false;
        if (_distToSeg(mx, my, ftzA.x, ftzA.y, ftzB.x, ftzB.y) < T) return true;
        var tDiff = d.t2 - d.t1;
        var fibNums = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144];
        for (var fi = 0; fi < fibNums.length; fi++) {
            var xPx = _tvToPixel(chartId, d.t1 + tDiff * fibNums[fi], d.p1);
            if (xPx && Math.abs(mx - xPx.x) < T) return true;
        }
        return false;
    }
    if (d.type === 'fib_fan' || d.type === 'pitchfan') {
        var ffA = _tvToPixel(chartId, d.t1, d.p1);
        var ffB = _tvToPixel(chartId, d.t2, d.p2);
        if (!ffA || !ffB) return false;
        if (_distToSeg(mx, my, ffA.x, ffA.y, ffB.x, ffB.y) < T) return true;
        if (d.t3 !== undefined) {
            var ffC = _tvToPixel(chartId, d.t3, d.p3);
            if (ffC && _distToSeg(mx, my, ffA.x, ffA.y, ffC.x, ffC.y) < T) return true;
        }
        return false;
    }
    if (d.type === 'fib_arc' || d.type === 'fib_circle') {
        var faA = _tvToPixel(chartId, d.t1, d.p1);
        var faB = _tvToPixel(chartId, d.t2, d.p2);
        if (!faA || !faB) return false;
        if (_distToSeg(mx, my, faA.x, faA.y, faB.x, faB.y) < T) return true;
        var dist = Math.sqrt(Math.pow(faB.x - faA.x, 2) + Math.pow(faB.y - faA.y, 2));
        var ctrX = d.type === 'fib_circle' ? (faA.x + faB.x) / 2 : faA.x;
        var ctrY = d.type === 'fib_circle' ? (faA.y + faB.y) / 2 : faA.y;
        var baseR = d.type === 'fib_circle' ? dist / 2 : dist;
        var mDist = Math.sqrt(Math.pow(mx - ctrX, 2) + Math.pow(my - ctrY, 2));
        var fLvls = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
        for (var fi = 0; fi < fLvls.length; fi++) {
            if (fLvls[fi] === 0) continue;
            if (Math.abs(mDist - baseR * fLvls[fi]) < T) return true;
        }
        return false;
    }
    if (d.type === 'fib_wedge') {
        var fwA = _tvToPixel(chartId, d.t1, d.p1);
        var fwB = _tvToPixel(chartId, d.t2, d.p2);
        if (!fwA || !fwB) return false;
        if (_distToSeg(mx, my, fwA.x, fwA.y, fwB.x, fwB.y) < T) return true;
        if (d.t3 !== undefined) {
            var fwC = _tvToPixel(chartId, d.t3, d.p3);
            if (fwC && _distToSeg(mx, my, fwA.x, fwA.y, fwC.x, fwC.y) < T) return true;
        }
        return false;
    }
    if (d.type === 'fib_time') {
        var ftA = _tvToPixel(chartId, d.t1, d.p1);
        var ftB = _tvToPixel(chartId, d.t2, d.p2);
        if (!ftA || !ftB) return false;
        if (_distToSeg(mx, my, ftA.x, ftA.y, ftB.x, ftB.y) < T) return true;
        if (d.t3 !== undefined) {
            var ftC = _tvToPixel(chartId, d.t3, d.p3);
            if (ftC && _distToSeg(mx, my, ftB.x, ftB.y, ftC.x, ftC.y) < T) return true;
            var tDiff = d.t2 - d.t1;
            var ftLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : [0, 0.382, 0.5, 0.618, 1, 1.382, 1.618, 2, 2.618, 4.236];
            for (var fi = 0; fi < ftLevels.length; fi++) {
                var xPx = _tvToPixel(chartId, d.t3 + tDiff * ftLevels[fi], d.p3);
                if (xPx && Math.abs(mx - xPx.x) < T) return true;
            }
        }
        return false;
    }
    if (d.type === 'fib_spiral') {
        var fsA = _tvToPixel(chartId, d.t1, d.p1);
        var fsB = _tvToPixel(chartId, d.t2, d.p2);
        if (!fsA || !fsB) return false;
        if (_distToSeg(mx, my, fsA.x, fsA.y, fsB.x, fsB.y) < T) return true;
        var fsDist = Math.sqrt(Math.pow(mx - fsA.x, 2) + Math.pow(my - fsA.y, 2));
        var fsR = Math.sqrt(Math.pow(fsB.x - fsA.x, 2) + Math.pow(fsB.y - fsA.y, 2));
        if (fsR > 0) {
            var fsAngle = Math.atan2(my - fsA.y, mx - fsA.x) - Math.atan2(fsB.y - fsA.y, fsB.x - fsA.x);
            var fsPhi = 1.6180339887;
            var fsB2 = Math.log(fsPhi) / (Math.PI / 2);
            var fsExpected = fsR * Math.exp(fsB2 * fsAngle);
            if (Math.abs(fsDist - fsExpected) < T * 2) return true;
        }
        return false;
    }
    if (d.type === 'gann_box' || d.type === 'gann_square_fixed' || d.type === 'gann_square') {
        var gbA = _tvToPixel(chartId, d.t1, d.p1);
        var gbB = _tvToPixel(chartId, d.t2, d.p2);
        if (!gbA || !gbB) return false;
        var gblx = Math.min(gbA.x, gbB.x), gbrx = Math.max(gbA.x, gbB.x);
        var gbty = Math.min(gbA.y, gbB.y), gbby = Math.max(gbA.y, gbB.y);
        if (mx >= gblx - T && mx <= gbrx + T && my >= gbty - T && my <= gbby + T) return true;
        return false;
    }
    if (d.type === 'gann_fan') {
        var gfA = _tvToPixel(chartId, d.t1, d.p1);
        var gfB = _tvToPixel(chartId, d.t2, d.p2);
        if (!gfA || !gfB) return false;
        if (_distToSeg(mx, my, gfA.x, gfA.y, gfB.x, gfB.y) < T) return true;
        var gfDx = gfB.x - gfA.x, gfDy = gfB.y - gfA.y;
        var gfAngles = [0.125, 0.25, 0.333, 0.5, 1, 2, 3, 4, 8];
        for (var gi = 0; gi < gfAngles.length; gi++) {
            var gRatio = gfAngles[gi];
            var gfEndX = gfA.x + gfDx;
            var gfEndY = gfA.y + gfDy * gRatio;
            if (_distToSeg(mx, my, gfA.x, gfA.y, gfEndX, gfEndY) < T) return true;
        }
        return false;
    }
    if (d.type === 'measure') {
        var mp1 = _tvToPixel(chartId, d.t1, d.p1);
        var mp2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!mp1 || !mp2) return false;
        if (_distToSeg(mx, my, mp1.x, mp1.y, mp2.x, mp2.y) < T) return true;
        return false;
    }
    if (d.type === 'text') {
        var tp = _tvToPixel(chartId, d.t1, d.p1);
        if (!tp) return false;
        var tw = (d.text || 'Text').length * 8;
        if (mx >= tp.x - 4 && mx <= tp.x + tw + 4 && my >= tp.y - 16 && my <= tp.y + 4) return true;
        return false;
    }
    // Single-point text tools — bounding box hit test
    var _txtNoteTools = ['anchored_text', 'note', 'price_note', 'pin', 'comment', 'price_label', 'signpost', 'flag_mark'];
    if (_txtNoteTools.indexOf(d.type) !== -1) {
        var tnp = _tvToPixel(chartId, d.t1, d.p1);
        if (!tnp) return false;
        var tnR = 25;
        if (Math.abs(mx - tnp.x) < tnR + T && Math.abs(my - tnp.y) < tnR + T) return true;
        return false;
    }
    if (d.type === 'callout') {
        var clp1 = _tvToPixel(chartId, d.t1, d.p1);
        if (!clp1) return false;
        if (Math.abs(mx - clp1.x) < 60 && my >= clp1.y - 40 && my <= clp1.y + 4) return true;
        if (d.t2 !== undefined) {
            var clp2 = _tvToPixel(chartId, d.t2, d.p2);
            if (clp2 && _distToSeg(mx, my, clp1.x, clp1.y, clp2.x, clp2.y) < T) return true;
        }
        return false;
    }
    if (d.type === 'arrow_marker') {
        var ap1 = _tvToPixel(chartId, d.t1, d.p1);
        var ap2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!ap1 || !ap2) return false;
        var amdx = ap2.x - ap1.x, amdy = ap2.y - ap1.y;
        var amLen = Math.sqrt(amdx * amdx + amdy * amdy);
        if (amLen < 1) return false;
        var amHeadW = Math.max(amLen * 0.22, 16);
        if (_distToSeg(mx, my, ap1.x, ap1.y, ap2.x, ap2.y) < amHeadW + T) return true;
        return false;
    }
    if (d.type === 'arrow') {
        var ap1 = _tvToPixel(chartId, d.t1, d.p1);
        var ap2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!ap1 || !ap2) return false;
        return _distToSeg(mx, my, ap1.x, ap1.y, ap2.x, ap2.y) < T;
    }
    var arrowMarks = ['arrow_mark_up', 'arrow_mark_down', 'arrow_mark_left', 'arrow_mark_right'];
    if (arrowMarks.indexOf(d.type) !== -1) {
        var amp = _tvToPixel(chartId, d.t1, d.p1);
        if (!amp) return false;
        var amR = (d.size || 30) / 2;
        return Math.abs(mx - amp.x) < amR && Math.abs(my - amp.y) < amR;
    }
    if (d.type === 'circle') {
        var cp1 = _tvToPixel(chartId, d.t1, d.p1);
        var cp2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!cp1 || !cp2) return false;
        var ccx = (cp1.x + cp2.x) / 2, ccy = (cp1.y + cp2.y) / 2;
        var cr = Math.sqrt(Math.pow(cp2.x - cp1.x, 2) + Math.pow(cp2.y - cp1.y, 2)) / 2;
        var cDist = Math.sqrt(Math.pow(mx - ccx, 2) + Math.pow(my - ccy, 2));
        return Math.abs(cDist - cr) < T;
    }
    if (d.type === 'ellipse') {
        var ep1 = _tvToPixel(chartId, d.t1, d.p1);
        var ep2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!ep1 || !ep2) return false;
        var ecx = (ep1.x + ep2.x) / 2, ecy = (ep1.y + ep2.y) / 2;
        var erx = Math.abs(ep2.x - ep1.x) / 2, ery = Math.abs(ep2.y - ep1.y) / 2;
        if (erx < 1 || ery < 1) return false;
        var eNorm = Math.pow((mx - ecx) / erx, 2) + Math.pow((my - ecy) / ery, 2);
        return Math.abs(eNorm - 1) < 0.3;
    }
    if (d.type === 'triangle') {
        var tr1 = _tvToPixel(chartId, d.t1, d.p1);
        var tr2 = _tvToPixel(chartId, d.t2, d.p2);
        var tr3 = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
        if (!tr1 || !tr2 || !tr3) return false;
        if (_distToSeg(mx, my, tr1.x, tr1.y, tr2.x, tr2.y) < T) return true;
        if (_distToSeg(mx, my, tr2.x, tr2.y, tr3.x, tr3.y) < T) return true;
        if (_distToSeg(mx, my, tr3.x, tr3.y, tr1.x, tr1.y) < T) return true;
        return false;
    }
    if (d.type === 'rotated_rect') {
        var rr1 = _tvToPixel(chartId, d.t1, d.p1);
        var rr2 = _tvToPixel(chartId, d.t2, d.p2);
        var rr3 = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
        if (!rr1 || !rr2 || !rr3) return false;
        var rdx = rr2.x - rr1.x, rdy = rr2.y - rr1.y;
        var rlen = Math.sqrt(rdx * rdx + rdy * rdy);
        if (rlen < 1) return false;
        var rnx = -rdy / rlen, rny = rdx / rlen;
        var rprojW = (rr3.x - rr1.x) * rnx + (rr3.y - rr1.y) * rny;
        var rc = rr1, rd = rr2;
        var re = { x: rr2.x + rnx * rprojW, y: rr2.y + rny * rprojW };
        var rf = { x: rr1.x + rnx * rprojW, y: rr1.y + rny * rprojW };
        if (_distToSeg(mx, my, rc.x, rc.y, rd.x, rd.y) < T) return true;
        if (_distToSeg(mx, my, rd.x, rd.y, re.x, re.y) < T) return true;
        if (_distToSeg(mx, my, re.x, re.y, rf.x, rf.y) < T) return true;
        if (_distToSeg(mx, my, rf.x, rf.y, rc.x, rc.y) < T) return true;
        return false;
    }
    if (d.type === 'shape_arc' || d.type === 'curve') {
        var scp1 = _tvToPixel(chartId, d.t1, d.p1);
        var scp2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!scp1 || !scp2) return false;
        if (_distToSeg(mx, my, scp1.x, scp1.y, scp2.x, scp2.y) < T + 10) return true;
        return false;
    }
    if (d.type === 'double_curve') {
        var dc1 = _tvToPixel(chartId, d.t1, d.p1);
        var dc2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!dc1 || !dc2) return false;
        if (_distToSeg(mx, my, dc1.x, dc1.y, dc2.x, dc2.y) < T + 10) return true;
        return false;
    }
    if (d.type === 'long_position' || d.type === 'short_position') {
        var lp1 = _tvToPixel(chartId, d.t1, d.p1);
        var lp2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!lp1 || !lp2) return false;
        var lpL = Math.min(lp1.x, lp2.x), lpR = Math.max(lp1.x, lp2.x);
        if (lpR - lpL < 20) lpR = lpL + 150;
        var lpStopY = lp1.y + (lp1.y - lp2.y);
        var lpTopY = Math.min(lp2.y, lpStopY), lpBotY = Math.max(lp2.y, lpStopY);
        if (mx >= lpL - T && mx <= lpR + T && my >= lpTopY - T && my <= lpBotY + T) return true;
        return false;
    }
    if (d.type === 'forecast' || d.type === 'ghost_feed') {
        var fg1 = _tvToPixel(chartId, d.t1, d.p1);
        var fg2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!fg1 || !fg2) return false;
        return _distToSeg(mx, my, fg1.x, fg1.y, fg2.x, fg2.y) < T;
    }
    if (d.type === 'bars_pattern' || d.type === 'projection' || d.type === 'fixed_range_vol' || d.type === 'date_price_range') {
        var bx1 = _tvToPixel(chartId, d.t1, d.p1);
        var bx2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!bx1 || !bx2) return false;
        var bxL = Math.min(bx1.x, bx2.x), bxR = Math.max(bx1.x, bx2.x);
        var bxT = Math.min(bx1.y, bx2.y), bxB = Math.max(bx1.y, bx2.y);
        if (mx >= bxL - T && mx <= bxR + T && my >= bxT - T && my <= bxB + T) return true;
        return false;
    }
    if (d.type === 'anchored_vwap') {
        var avp = _tvToPixel(chartId, d.t1, d.p1);
        if (!avp) return false;
        return Math.abs(mx - avp.x) < T;
    }
    if (d.type === 'price_range') {
        var prp1 = _tvToPixel(chartId, d.t1, d.p1);
        var prp2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!prp1 || !prp2) return false;
        if (Math.abs(my - prp1.y) < T || Math.abs(my - prp2.y) < T) return true;
        if (Math.abs(mx - prp1.x) < T && my >= Math.min(prp1.y, prp2.y) && my <= Math.max(prp1.y, prp2.y)) return true;
        return false;
    }
    if (d.type === 'date_range') {
        var drp1 = _tvToPixel(chartId, d.t1, d.p1);
        var drp2 = _tvToPixel(chartId, d.t2, d.p2);
        if (!drp1 || !drp2) return false;
        if (Math.abs(mx - drp1.x) < T || Math.abs(mx - drp2.x) < T) return true;
        return false;
    }
    return false;
}

function _distToSeg(px, py, x1, y1, x2, y2) {
    var dx = x2 - x1, dy = y2 - y1;
    var len2 = dx * dx + dy * dy;
    if (len2 === 0) return Math.sqrt((px - x1) * (px - x1) + (py - y1) * (py - y1));
    var t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / len2));
    var nx = x1 + t * dx, ny = y1 + t * dy;
    return Math.sqrt((px - nx) * (px - nx) + (py - ny) * (py - ny));
}

function _tvRoundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
}

// ---- Helpers for Pearson's R ----
function _tvGetSeriesDataBetween(chartId, t1, t2) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.series) return null;
    var data = entry.series.data ? entry.series.data() : null;
    if (!data || !data.length) return null;
    var lo = Math.min(t1, t2), hi = Math.max(t1, t2);
    var result = [];
    for (var i = 0; i < data.length; i++) {
        var pt = data[i];
        if (pt.time >= lo && pt.time <= hi) {
            var v = pt.close !== undefined ? pt.close : pt.value;
            if (v !== undefined && v !== null) result.push({ idx: i, value: v });
        }
    }
    return result.length > 1 ? result : null;
}

function _tvPearsonsR(vals) {
    var n = vals.length;
    if (n < 2) return null;
    var sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;
    for (var i = 0; i < n; i++) {
        var x = i, y = vals[i].value;
        sumX += x; sumY += y; sumXY += x * y; sumX2 += x * x; sumY2 += y * y;
    }
    var denom = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
    if (denom === 0) return 0;
    return (n * sumXY - sumX * sumY) / denom;
}

// ---- Rendering ----
function _tvRenderDrawings(chartId) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds) return;
    var ctx = ds.ctx;
    var w = ds.canvas.clientWidth;
    var h = ds.canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);

    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry || !entry.chart) return;

    var theme = entry.theme || 'dark';
    var defColor = _cssVar('--pywry-draw-default-color');
    var textColor = _cssVar('--pywry-tvchart-text');
    var viewport = _tvGetDrawingViewport(chartId);

    for (var i = 0; i < ds.drawings.length; i++) {
        if (ds.drawings[i].hidden) continue;
        var isSel = (_drawSelectedChart === chartId && _drawSelectedIdx === i);
        var isHov = (_drawHoverIdx === i && _drawSelectedChart === chartId && _drawSelectedIdx !== i);
        var isMouseOver = (_drawHoverIdx === i);
        _tvDrawOne(ctx, ds.drawings[i], chartId, defColor, textColor, w, h, isSel, isHov, isMouseOver, viewport);
    }
    if (_drawPending && _drawPending.chartId === chartId) {
        _tvDrawOne(ctx, _drawPending, chartId, defColor, textColor, w, h, false, false, false, viewport);
    }
}

function _tvDrawOne(ctx, d, chartId, defColor, textColor, w, h, selected, hovered, mouseOver, viewport) {
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;
    var series = _tvMainSeries(chartId);
    if (!series) return;
    viewport = viewport || _tvGetDrawingViewport(chartId);

    var col = d.color || defColor;
    var lw  = d.lineWidth || 2;
    if (hovered) { lw += 0.5; }

    ctx.save();
    ctx.strokeStyle = col;
    ctx.fillStyle   = col;
    ctx.lineWidth   = lw;
    ctx.lineJoin    = 'round';
    ctx.lineCap     = 'round';
    ctx.beginPath();
    ctx.rect(viewport.left, viewport.top, viewport.width, viewport.height);
    ctx.clip();

    // Line style
    if (d.lineStyle === 1) ctx.setLineDash([6, 4]);
    else if (d.lineStyle === 2) ctx.setLineDash([2, 3]);
    else ctx.setLineDash([]);

    // Pre-compute common anchor pixel positions used by many drawing types
    var p1 = (d.t1 !== undefined && d.p1 !== undefined) ? _tvToPixel(chartId, d.t1, d.p1) : null;
    var p2 = (d.t2 !== undefined && d.p2 !== undefined) ? _tvToPixel(chartId, d.t2, d.p2) : null;

    if (d.type === 'hline') {
        var yH = series.priceToCoordinate(d.price);
        if (yH !== null) {
            ctx.beginPath();
            ctx.moveTo(0, yH);
            ctx.lineTo(w, yH);
            ctx.stroke();
            // Canvas price-label box (supplements the native price-line label).
            // Only drawn when showPriceLabel is not explicitly false.
            if (d.showPriceLabel !== false) {
                var labelBoxColor = d.labelColor || col;
                var prLabel = (d.title ? d.title + ' ' : '') + Number(d.price).toFixed(2);
                ctx.font = 'bold 11px -apple-system,BlinkMacSystemFont,sans-serif';
                var pm = ctx.measureText(prLabel);
                var plw = pm.width + 10;
                var plh = 20;
                var plx = viewport.right - plw - 4;
                var ply = yH - plh / 2;
                ctx.fillStyle = labelBoxColor;
                ctx.beginPath();
                var r = 3;
                ctx.moveTo(plx + r, ply);
                ctx.lineTo(plx + plw - r, ply);
                ctx.quadraticCurveTo(plx + plw, ply, plx + plw, ply + r);
                ctx.lineTo(plx + plw, ply + plh - r);
                ctx.quadraticCurveTo(plx + plw, ply + plh, plx + plw - r, ply + plh);
                ctx.lineTo(plx + r, ply + plh);
                ctx.quadraticCurveTo(plx, ply + plh, plx, ply + plh - r);
                ctx.lineTo(plx, ply + r);
                ctx.quadraticCurveTo(plx, ply, plx + r, ply);
                ctx.fill();
                ctx.fillStyle = _cssVar('--pywry-draw-label-text');
                ctx.textBaseline = 'middle';
                ctx.fillText(prLabel, plx + 5, yH);
                ctx.textBaseline = 'alphabetic';
            }
        }
    } else if (d.type === 'trendline') {
        var a = _tvToPixel(chartId, d.t1, d.p1);
        var b = _tvToPixel(chartId, d.t2, d.p2);
        if (a && b) {
            var dx = b.x - a.x, dy = b.y - a.y;
            var len = Math.sqrt(dx * dx + dy * dy);
            if (len > 0) {
                var ext = 4000;
                var ux = dx / len, uy = dy / len;
                var startX = a.x, startY = a.y;
                var endX = b.x, endY = b.y;
                var extMode = d.extend || "Don't extend";
                if (d.ray) {
                    // Ray mode: start at A, extend through B to infinity
                    endX = b.x + ux * ext;
                    endY = b.y + uy * ext;
                } else if (extMode === 'Left' || extMode === 'Both') {
                    startX = a.x - ux * ext;
                    startY = a.y - uy * ext;
                }
                if (!d.ray && (extMode === 'Right' || extMode === 'Both')) {
                    endX = b.x + ux * ext;
                    endY = b.y + uy * ext;
                }
                ctx.beginPath();
                ctx.moveTo(startX, startY);
                ctx.lineTo(endX, endY);
                ctx.stroke();
            }
            // Middle point
            if (d.showMiddlePoint) {
                var midX = (a.x + b.x) / 2, midY = (a.y + b.y) / 2;
                ctx.beginPath();
                ctx.arc(midX, midY, 4, 0, Math.PI * 2);
                ctx.fillStyle = col;
                ctx.fill();
            }
            // Price labels at endpoints
            if (d.showPriceLabels) {
                ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                ctx.fillStyle = col;
                var p1Txt = d.p1 !== undefined ? d.p1.toFixed(2) : '';
                var p2Txt = d.p2 !== undefined ? d.p2.toFixed(2) : '';
                ctx.fillText(p1Txt, a.x + 4, a.y - 6);
                ctx.fillText(p2Txt, b.x + 4, b.y - 6);
            }
            // Text annotation (from Text tab in settings)
            if (d.text) {
                var tMidX = (a.x + b.x) / 2, tMidY = (a.y + b.y) / 2;
                var tFs = d.textFontSize || 12;
                var tStyle = (d.textItalic ? 'italic ' : '') + (d.textBold ? 'bold ' : '');
                ctx.font = tStyle + tFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
                ctx.fillStyle = d.textColor || col;
                ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
                ctx.fillText(d.text, tMidX, tMidY - 6);
                ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
            }
            // Stats (from Inputs tab: hidden/compact/values)
            if (d.stats && d.stats !== 'hidden' && a && b) {
                var sDx = d.p2 - d.p1, sPct = d.p1 !== 0 ? ((sDx / d.p1) * 100) : 0;
                var sBars = Math.abs(Math.round((d.t2 - d.t1) / 86400)); // approximate bar count
                var sText = '';
                if (d.stats === 'compact') {
                    sText = (sDx >= 0 ? '+' : '') + sDx.toFixed(2) + ' (' + (sPct >= 0 ? '+' : '') + sPct.toFixed(2) + '%)';
                } else {
                    sText = (sDx >= 0 ? '+' : '') + sDx.toFixed(2) + ' (' + (sPct >= 0 ? '+' : '') + sPct.toFixed(2) + '%)' + ' | ' + sBars + ' bars';
                }
                var sFs = 11;
                ctx.font = sFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
                ctx.fillStyle = col;
                var sAnchor = d.statsPosition === 'left' ? a : b;
                var sAlign = d.statsPosition === 'left' ? 'left' : 'right';
                ctx.textAlign = sAlign; ctx.textBaseline = 'top';
                ctx.fillText(sText, sAnchor.x, sAnchor.y + 6);
                ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
            }
        }
    } else if (d.type === 'rect') {
        var r1 = _tvToPixel(chartId, d.t1, d.p1);
        var r2 = _tvToPixel(chartId, d.t2, d.p2);
        if (r1 && r2) {
            var rx = Math.min(r1.x, r2.x), ry = Math.min(r1.y, r2.y);
            var rw = Math.abs(r2.x - r1.x), rh = Math.abs(r2.y - r1.y);
            if (d.fillEnabled !== false) {
                ctx.fillStyle = d.fillColor || col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.15;
                ctx.fillRect(rx, ry, rw, rh);
                ctx.globalAlpha = 1.0;
            }
            ctx.strokeRect(rx, ry, rw, rh);
        }
    } else if (d.type === 'text') {
        var tp = _tvToPixel(chartId, d.t1, d.p1);
        if (tp) {
            var fontStyle = (d.italic ? 'italic ' : '') + (d.bold !== false ? 'bold ' : '');
            ctx.font = fontStyle + (d.fontSize || 14) + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var textContent = d.text || 'Text';
            if (d.bgEnabled) {
                var tm = ctx.measureText(textContent);
                var pad = 4;
                ctx.fillStyle = d.bgColor || _cssVar('--pywry-draw-text-bg');
                ctx.globalAlpha = d.bgOpacity !== undefined ? d.bgOpacity : 0.7;
                ctx.fillRect(tp.x - pad, tp.y - (d.fontSize || 14) - pad, tm.width + pad * 2, (d.fontSize || 14) + pad * 2);
                ctx.globalAlpha = 1.0;
            }
            ctx.fillStyle = d.color || defColor;
            ctx.fillText(textContent, tp.x, tp.y);
        }
    } else if (d.type === 'anchored_text') {
        // Anchored Text: text with a dot anchor below
        var atp = _tvToPixel(chartId, d.t1, d.p1);
        if (atp) {
            var _atFs = d.fontSize || 14;
            var _atFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
            ctx.font = _atFw + _atFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var _atTxt = d.text || 'Text';
            var _atTm = ctx.measureText(_atTxt);
            if (d.bgEnabled) {
                var _atPad = 4;
                ctx.fillStyle = d.bgColor || '#2a2e39';
                ctx.globalAlpha = 0.7;
                ctx.fillRect(atp.x - _atTm.width / 2 - _atPad, atp.y - _atFs - _atPad, _atTm.width + _atPad * 2, _atFs + _atPad * 2);
                ctx.globalAlpha = 1.0;
            }
            ctx.fillStyle = d.color || defColor;
            ctx.textAlign = 'center';
            ctx.fillText(_atTxt, atp.x, atp.y);
            // Anchor dot
            ctx.beginPath();
            ctx.arc(atp.x, atp.y + 6, 3, 0, Math.PI * 2);
            ctx.fill();
            ctx.textAlign = 'start';
        }
    } else if (d.type === 'note') {
        // Note: text block with border
        var ntp = _tvToPixel(chartId, d.t1, d.p1);
        if (ntp) {
            var _nFs = d.fontSize || 14;
            var _nFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
            ctx.font = _nFw + _nFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var _nTxt = d.text || 'Note';
            var _nTm = ctx.measureText(_nTxt);
            var _nPad = 8;
            var _nW = _nTm.width + _nPad * 2;
            var _nH = _nFs + _nPad * 2;
            if (d.bgEnabled !== false) {
                ctx.fillStyle = d.bgColor || '#2a2e39';
                ctx.globalAlpha = 0.85;
                ctx.fillRect(ntp.x, ntp.y - _nH, _nW, _nH);
                ctx.globalAlpha = 1.0;
            }
            if (d.borderEnabled) {
                ctx.strokeStyle = d.borderColor || col;
                ctx.strokeRect(ntp.x, ntp.y - _nH, _nW, _nH);
                ctx.strokeStyle = col;
            }
            ctx.fillStyle = d.color || defColor;
            ctx.fillText(_nTxt, ntp.x + _nPad, ntp.y - _nPad);
        }
    } else if (d.type === 'price_note') {
        // Price Note: note anchored to a price level with horizontal dash
        var pnp = _tvToPixel(chartId, d.t1, d.p1);
        if (pnp) {
            var _pnFs = d.fontSize || 14;
            var _pnFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
            ctx.font = _pnFw + _pnFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var _pnTxt = d.text || 'Price Note';
            var _pnTm = ctx.measureText(_pnTxt);
            var _pnPad = 6;
            var _pnW = _pnTm.width + _pnPad * 2;
            var _pnH = _pnFs + _pnPad * 2;
            // Horizontal price dash
            ctx.setLineDash([4, 3]);
            ctx.beginPath();
            ctx.moveTo(pnp.x + _pnW + 4, pnp.y - _pnH / 2);
            ctx.lineTo(pnp.x + _pnW + 40, pnp.y - _pnH / 2);
            ctx.stroke();
            ctx.setLineDash(ls);
            if (d.bgEnabled !== false) {
                ctx.fillStyle = d.bgColor || '#2a2e39';
                ctx.globalAlpha = 0.85;
                ctx.fillRect(pnp.x, pnp.y - _pnH, _pnW, _pnH);
                ctx.globalAlpha = 1.0;
            }
            if (d.borderEnabled) {
                ctx.strokeStyle = d.borderColor || col;
                ctx.strokeRect(pnp.x, pnp.y - _pnH, _pnW, _pnH);
                ctx.strokeStyle = col;
            }
            ctx.fillStyle = d.color || defColor;
            ctx.fillText(_pnTxt, pnp.x + _pnPad, pnp.y - _pnPad);
        }
    } else if (d.type === 'pin') {
        // Pin: map-pin icon with text bubble above
        var pinP = _tvToPixel(chartId, d.t1, d.p1);
        if (pinP) {
            var pinCol = d.markerColor || col;
            // Draw pin marker (teardrop shape)
            var pinR = 8;
            ctx.beginPath();
            ctx.arc(pinP.x, pinP.y - pinR - 6, pinR, Math.PI, 0, false);
            ctx.lineTo(pinP.x, pinP.y);
            ctx.closePath();
            ctx.fillStyle = pinCol;
            ctx.fill();
            // Inner dot
            ctx.beginPath();
            ctx.arc(pinP.x, pinP.y - pinR - 6, 3, 0, Math.PI * 2);
            ctx.fillStyle = '#1e222d';
            ctx.fill();
            // Text bubble if text present (mouseover only)
            if (d.text && mouseOver) {
                var _pinFs = d.fontSize || 14;
                var _pinFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
                ctx.font = _pinFw + _pinFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
                var _pinTm = ctx.measureText(d.text);
                var _pinPad = 8;
                var _pinBW = _pinTm.width + _pinPad * 2;
                var _pinBH = _pinFs + _pinPad * 2;
                var _pinBY = pinP.y - pinR * 2 - 12 - _pinBH;
                var _pinBX = pinP.x - _pinBW / 2;
                // Bubble background
                ctx.fillStyle = d.bgColor || '#3a3e4a';
                ctx.globalAlpha = 0.9;
                _tvRoundRect(ctx, _pinBX, _pinBY, _pinBW, _pinBH, 4);
                ctx.fill();
                ctx.globalAlpha = 1.0;
                // Bubble pointer
                ctx.beginPath();
                ctx.moveTo(pinP.x - 5, _pinBY + _pinBH);
                ctx.lineTo(pinP.x, _pinBY + _pinBH + 6);
                ctx.lineTo(pinP.x + 5, _pinBY + _pinBH);
                ctx.fillStyle = d.bgColor || '#3a3e4a';
                ctx.fill();
                // Text
                ctx.fillStyle = d.color || defColor;
                ctx.textAlign = 'center';
                ctx.fillText(d.text, pinP.x, _pinBY + _pinBH - _pinPad);
                ctx.textAlign = 'start';
            }
            // Small anchor circle at bottom
            ctx.beginPath();
            ctx.arc(pinP.x, pinP.y + 3, 2, 0, Math.PI * 2);
            ctx.fillStyle = pinCol;
            ctx.fill();
        }
    } else if (d.type === 'callout') {
        // Callout: speech bubble with pointer from p2 to p1
        var clP1 = _tvToPixel(chartId, d.t1, d.p1);
        var clP2 = d.t2 !== undefined ? _tvToPixel(chartId, d.t2, d.p2) : null;
        if (clP1) {
            var _clFs = d.fontSize || 14;
            var _clFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
            ctx.font = _clFw + _clFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var _clTxt = d.text || 'Callout';
            var _clTm = ctx.measureText(_clTxt);
            var _clPad = 10;
            var _clW = _clTm.width + _clPad * 2;
            var _clH = _clFs + _clPad * 2;
            var _clX = clP1.x;
            var _clY = clP1.y - _clH;
            // Background
            ctx.fillStyle = d.bgColor || '#2a2e39';
            ctx.globalAlpha = 0.9;
            _tvRoundRect(ctx, _clX, _clY, _clW, _clH, 4);
            ctx.fill();
            ctx.globalAlpha = 1.0;
            if (d.borderEnabled) {
                ctx.strokeStyle = d.borderColor || col;
                _tvRoundRect(ctx, _clX, _clY, _clW, _clH, 4);
                ctx.stroke();
                ctx.strokeStyle = col;
            }
            // Pointer line to p2
            if (clP2) {
                ctx.beginPath();
                ctx.moveTo(_clX + _clW / 2, clP1.y);
                ctx.lineTo(clP2.x, clP2.y);
                ctx.stroke();
            }
            // Text
            ctx.fillStyle = d.color || defColor;
            ctx.fillText(_clTxt, _clX + _clPad, clP1.y - _clPad);
        }
    } else if (d.type === 'comment') {
        // Comment: circular bubble with text
        var cmP = _tvToPixel(chartId, d.t1, d.p1);
        if (cmP) {
            var _cmFs = d.fontSize || 14;
            var _cmFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
            ctx.font = _cmFw + _cmFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var _cmTxt = d.text || 'Comment';
            var _cmTm = ctx.measureText(_cmTxt);
            var _cmR = Math.max(_cmTm.width / 2 + 12, _cmFs + 8);
            // Background circle
            ctx.beginPath();
            ctx.arc(cmP.x, cmP.y - _cmR, _cmR, 0, Math.PI * 2);
            ctx.fillStyle = d.bgColor || '#2a2e39';
            ctx.globalAlpha = 0.85;
            ctx.fill();
            ctx.globalAlpha = 1.0;
            ctx.strokeStyle = d.borderEnabled ? (d.borderColor || col) : col;
            ctx.stroke();
            ctx.strokeStyle = col;
            // Pointer triangle
            ctx.beginPath();
            ctx.moveTo(cmP.x - 5, cmP.y - 2);
            ctx.lineTo(cmP.x, cmP.y + 6);
            ctx.lineTo(cmP.x + 5, cmP.y - 2);
            ctx.fillStyle = d.bgColor || '#2a2e39';
            ctx.fill();
            // Text
            ctx.fillStyle = d.color || defColor;
            ctx.textAlign = 'center';
            ctx.fillText(_cmTxt, cmP.x, cmP.y - _cmR + 4);
            ctx.textAlign = 'start';
        }
    } else if (d.type === 'price_label') {
        // Price Label: arrow-shaped label pointing right
        var plP = _tvToPixel(chartId, d.t1, d.p1);
        if (plP) {
            var _plFs = d.fontSize || 14;
            var _plFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
            ctx.font = _plFw + _plFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var _plTxt = d.text || 'Label';
            var _plTm = ctx.measureText(_plTxt);
            var _plPad = 6;
            var _plW = _plTm.width + _plPad * 2;
            var _plH = _plFs + _plPad * 2;
            var _plArr = 8;
            // Arrow-shaped polygon
            ctx.beginPath();
            ctx.moveTo(plP.x, plP.y - _plH / 2);
            ctx.lineTo(plP.x + _plW, plP.y - _plH / 2);
            ctx.lineTo(plP.x + _plW + _plArr, plP.y);
            ctx.lineTo(plP.x + _plW, plP.y + _plH / 2);
            ctx.lineTo(plP.x, plP.y + _plH / 2);
            ctx.closePath();
            ctx.fillStyle = d.bgColor || col;
            ctx.globalAlpha = 0.85;
            ctx.fill();
            ctx.globalAlpha = 1.0;
            ctx.stroke();
            // Text
            ctx.fillStyle = d.color || '#ffffff';
            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';
            ctx.fillText(_plTxt, plP.x + _plPad, plP.y);
            ctx.textBaseline = 'alphabetic';
        }
    } else if (d.type === 'signpost') {
        // Signpost: vertical pole with flag-like sign
        var spP = _tvToPixel(chartId, d.t1, d.p1);
        if (spP) {
            var spCol = d.markerColor || col;
            var _spFs = d.fontSize || 14;
            var _spFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
            ctx.font = _spFw + _spFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var _spTxt = d.text || 'Signpost';
            var _spTm = ctx.measureText(_spTxt);
            var _spPad = 6;
            var _spW = _spTm.width + _spPad * 2;
            var _spH = _spFs + _spPad * 2;
            // Vertical pole
            ctx.beginPath();
            ctx.moveTo(spP.x, spP.y);
            ctx.lineTo(spP.x, spP.y - _spH - 20);
            ctx.strokeStyle = spCol;
            ctx.stroke();
            // Sign shape (flag)
            ctx.beginPath();
            ctx.moveTo(spP.x, spP.y - _spH - 20);
            ctx.lineTo(spP.x + _spW, spP.y - _spH - 16);
            ctx.lineTo(spP.x + _spW, spP.y - 24);
            ctx.lineTo(spP.x, spP.y - 20);
            ctx.closePath();
            ctx.fillStyle = d.bgColor || spCol;
            ctx.globalAlpha = 0.85;
            ctx.fill();
            ctx.globalAlpha = 1.0;
            if (d.borderEnabled) {
                ctx.stroke();
            }
            // Text on sign
            ctx.fillStyle = d.color || '#ffffff';
            ctx.textBaseline = 'middle';
            ctx.fillText(_spTxt, spP.x + _spPad, spP.y - _spH / 2 - 20);
            ctx.textBaseline = 'alphabetic';
        }
    } else if (d.type === 'flag_mark') {
        // Flag Mark: small flag on a pole
        var fmP = _tvToPixel(chartId, d.t1, d.p1);
        if (fmP) {
            var fmCol = d.markerColor || col;
            var _fmFs = d.fontSize || 14;
            // Pole
            ctx.beginPath();
            ctx.moveTo(fmP.x, fmP.y);
            ctx.lineTo(fmP.x, fmP.y - 30);
            ctx.strokeStyle = fmCol;
            ctx.stroke();
            // Flag
            ctx.beginPath();
            ctx.moveTo(fmP.x, fmP.y - 30);
            ctx.lineTo(fmP.x + 20, fmP.y - 26);
            ctx.lineTo(fmP.x + 16, fmP.y - 22);
            ctx.lineTo(fmP.x + 20, fmP.y - 18);
            ctx.lineTo(fmP.x, fmP.y - 18);
            ctx.closePath();
            ctx.fillStyle = fmCol;
            ctx.fill();
            // Text below (mouseover only)
            if (d.text && mouseOver) {
                var _fmFw = (d.italic ? 'italic ' : '') + (d.bold ? 'bold ' : '');
                ctx.font = _fmFw + _fmFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
                ctx.fillStyle = d.color || defColor;
                ctx.textAlign = 'center';
                ctx.fillText(d.text, fmP.x, fmP.y + _fmFs + 4);
                ctx.textAlign = 'start';
            }
        }
    } else if (d.type === 'channel') {
        var c1 = _tvToPixel(chartId, d.t1, d.p1);
        var c2 = _tvToPixel(chartId, d.t2, d.p2);
        if (c1 && c2) {
            var chanOff = d.offset || 30;
            // Fill between lines
            if (d.fillEnabled !== false) {
                ctx.fillStyle = d.fillColor || col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.08;
                ctx.beginPath();
                ctx.moveTo(c1.x, c1.y);
                ctx.lineTo(c2.x, c2.y);
                ctx.lineTo(c2.x, c2.y + chanOff);
                ctx.lineTo(c1.x, c1.y + chanOff);
                ctx.closePath();
                ctx.fill();
                ctx.globalAlpha = 1.0;
            }
            // Main line
            ctx.beginPath();
            ctx.moveTo(c1.x, c1.y);
            ctx.lineTo(c2.x, c2.y);
            ctx.stroke();
            // Parallel line
            ctx.beginPath();
            ctx.moveTo(c1.x, c1.y + chanOff);
            ctx.lineTo(c2.x, c2.y + chanOff);
            ctx.stroke();
            // Middle dashed line
            if (d.showMiddleLine !== false) {
                ctx.setLineDash([4, 4]);
                ctx.globalAlpha = 0.5;
                ctx.beginPath();
                ctx.moveTo(c1.x, c1.y + chanOff / 2);
                ctx.lineTo(c2.x, c2.y + chanOff / 2);
                ctx.stroke();
                ctx.globalAlpha = 1.0;
            }
            ctx.setLineDash(d.lineStyle === 1 ? [6,4] : d.lineStyle === 2 ? [2,3] : []);
        }
    } else if (d.type === 'fibonacci') {
        var fTop = series.priceToCoordinate(d.p1);
        var fBot = series.priceToCoordinate(d.p2);
        if (fTop !== null && fBot !== null) {
            // Reverse swaps the direction of level interpolation
            var fibAnchorTop = d.reverse ? fBot : fTop;
            var fibAnchorBot = d.reverse ? fTop : fBot;
            var fibPriceTop = d.reverse ? d.p2 : d.p1;
            var fibPriceBot = d.reverse ? d.p1 : d.p2;
            var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
            var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
            var fibEnabled = d.fibEnabled || [];
            var showLbls = d.showLabels !== false;
            var showPrices = d.showPrices !== false;
            // Use user-set lineStyle; endpoints always solid
            var fibDash = d.lineStyle === 1 ? [6, 4] : d.lineStyle === 2 ? [2, 3] : [4, 3];
            for (var fi = 0; fi < fibLevels.length; fi++) {
                if (fibEnabled[fi] === false) continue;
                var lvl = fibEnabled.length ? fibLevels[fi] : _FIB_LEVELS[fi];
                var yFib = fibAnchorTop + (fibAnchorBot - fibAnchorTop) * lvl;
                var fc = fibColors[fi] || col;
                // Zone fill between this level and next
                if (fi < fibLevels.length - 1 && fibEnabled[fi + 1] !== false) {
                    var yNext = fibAnchorTop + (fibAnchorBot - fibAnchorTop) * fibLevels[fi + 1];
                    ctx.fillStyle = fc;
                    ctx.globalAlpha = 0.06;
                    ctx.fillRect(0, Math.min(yFib, yNext), w, Math.abs(yNext - yFib));
                    ctx.globalAlpha = 1.0;
                }
                // Level line — respect user lineStyle and lineWidth
                ctx.strokeStyle = fc;
                ctx.lineWidth = lvl === 0 || lvl === 1 ? lw : Math.max(1, lw - 1);
                ctx.setLineDash(lvl === 0 || lvl === 1 ? [] : fibDash);
                ctx.beginPath();
                ctx.moveTo(0, yFib);
                ctx.lineTo(w, yFib);
                ctx.stroke();
                // Label
                if (showLbls || showPrices) {
                    var priceFib = fibPriceTop + (fibPriceBot - fibPriceTop) * lvl;
                    ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                    ctx.fillStyle = fc;
                    var fibLabel = '';
                    if (showLbls) fibLabel += lvl.toFixed(3);
                    if (showPrices) fibLabel += (fibLabel ? '  ' : '') + '(' + priceFib.toFixed(2) + ')';
                    ctx.fillText(fibLabel, viewport.left + 8, yFib - 4);
                }
            }
            ctx.setLineDash([]);
            ctx.lineWidth = lw;

            // Trend line — diagonal dashed line connecting the two anchor points
            var fA1 = _tvToPixel(chartId, d.t1, d.p1);
            var fA2 = _tvToPixel(chartId, d.t2, d.p2);
            if (fA1 && fA2) {
                ctx.strokeStyle = col;
                ctx.lineWidth = lw;
                ctx.setLineDash([6, 4]);
                ctx.globalAlpha = 0.6;
                ctx.beginPath();
                ctx.moveTo(fA1.x, fA1.y);
                ctx.lineTo(fA2.x, fA2.y);
                ctx.stroke();
                ctx.globalAlpha = 1.0;
                ctx.setLineDash([]);
            }
        }
    } else if (d.type === 'fib_extension') {
        // Trend-Based Fib Extension: 3 anchor points (A, B, C)
        // Levels project from C using the A→B distance
        var feA = _tvToPixel(chartId, d.t1, d.p1);
        var feB = _tvToPixel(chartId, d.t2, d.p2);
        var feC = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
        if (feA && feB) {
            // Draw the A→B leg
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.setLineDash([]);
            ctx.beginPath(); ctx.moveTo(feA.x, feA.y); ctx.lineTo(feB.x, feB.y); ctx.stroke();
            if (feC) {
                // Draw B→C leg
                ctx.setLineDash([4, 3]);
                ctx.beginPath(); ctx.moveTo(feB.x, feB.y); ctx.lineTo(feC.x, feC.y); ctx.stroke();
                ctx.setLineDash([]);
                // Extension levels project from C using AB price range
                var abRange = d.p2 - d.p1;
                var extDefLevels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.618, 2.618, 4.236];
                var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : extDefLevels;
                var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
                var fibEnabled = d.fibEnabled || [];
                var showLbls = d.showLabels !== false;
                var showPrices = d.showPrices !== false;
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    if (fibEnabled[fi] === false) continue;
                    var lvl = fibLevels[fi];
                    var extPrice = d.p3 + abRange * lvl;
                    var yExt = series.priceToCoordinate(extPrice);
                    if (yExt === null) continue;
                    var fc = fibColors[fi % fibColors.length] || col;
                    // Zone fill between this level and next
                    if (d.fillEnabled !== false && fi < fibLevels.length - 1 && fibEnabled[fi + 1] !== false) {
                        var nextPrice = d.p3 + abRange * fibLevels[fi + 1];
                        var yNext = series.priceToCoordinate(nextPrice);
                        if (yNext !== null) {
                            ctx.fillStyle = fc;
                            ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.06;
                            ctx.fillRect(0, Math.min(yExt, yNext), w, Math.abs(yNext - yExt));
                            ctx.globalAlpha = 1.0;
                        }
                    }
                    ctx.strokeStyle = fc;
                    ctx.lineWidth = lvl === 0 || lvl === 1 ? lw : Math.max(1, lw - 1);
                    ctx.setLineDash(lvl === 0 || lvl === 1 ? [] : [4, 3]);
                    ctx.beginPath(); ctx.moveTo(0, yExt); ctx.lineTo(w, yExt); ctx.stroke();
                    if (showLbls || showPrices) {
                        ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                        ctx.fillStyle = fc;
                        var lbl = '';
                        if (showLbls) lbl += lvl.toFixed(3);
                        if (showPrices) lbl += (lbl ? '  (' : '') + extPrice.toFixed(2) + (lbl ? ')' : '');
                        ctx.fillText(lbl, viewport.left + 8, yExt - 4);
                    }
                }
                ctx.setLineDash([]);
                ctx.lineWidth = lw;
            }
        }
    } else if (d.type === 'fib_channel') {
        // Fib Channel: two trend lines (A→B and parallel through C) with fib levels between
        var fcA = _tvToPixel(chartId, d.t1, d.p1);
        var fcB = _tvToPixel(chartId, d.t2, d.p2);
        var fcC = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
        if (fcA && fcB) {
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.setLineDash([]);
            ctx.beginPath(); ctx.moveTo(fcA.x, fcA.y); ctx.lineTo(fcB.x, fcB.y); ctx.stroke();
            if (fcC) {
                // Perpendicular offset from A→B line to C
                var abDx = fcB.x - fcA.x, abDy = fcB.y - fcA.y;
                var abLen = Math.sqrt(abDx * abDx + abDy * abDy);
                if (abLen > 0) {
                    // Perpendicular offset = distance from C to line AB
                    var cOff = ((fcC.x - fcA.x) * (-abDy / abLen) + (fcC.y - fcA.y) * (abDx / abLen));
                    var px = -abDy / abLen, py = abDx / abLen;
                    var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
                    var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
                    var fibEnabled = d.fibEnabled || [];
                    var showLbls = d.showLabels !== false;
                    for (var fi = 0; fi < fibLevels.length; fi++) {
                        if (fibEnabled[fi] === false) continue;
                        var lvl = fibLevels[fi];
                        var off = cOff * lvl;
                        var fc = fibColors[fi] || col;
                        ctx.strokeStyle = fc;
                        ctx.lineWidth = lvl === 0 || lvl === 1 ? lw : Math.max(1, lw - 1);
                        ctx.setLineDash(lvl === 0 || lvl === 1 ? [] : [4, 3]);
                        ctx.beginPath();
                        ctx.moveTo(fcA.x + px * off, fcA.y + py * off);
                        ctx.lineTo(fcB.x + px * off, fcB.y + py * off);
                        ctx.stroke();
                        if (showLbls) {
                            ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                            ctx.fillStyle = fc;
                            ctx.fillText(lvl.toFixed(3), fcA.x + px * off + 4, fcA.y + py * off - 4);
                        }
                    }
                    // Fill between 0 and 1 levels
                    if (d.fillEnabled !== false) {
                        ctx.fillStyle = d.fillColor || col;
                        ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.04;
                        ctx.beginPath();
                        ctx.moveTo(fcA.x, fcA.y);
                        ctx.lineTo(fcB.x, fcB.y);
                        ctx.lineTo(fcB.x + px * cOff, fcB.y + py * cOff);
                        ctx.lineTo(fcA.x + px * cOff, fcA.y + py * cOff);
                        ctx.closePath();
                        ctx.fill();
                        ctx.globalAlpha = 1.0;
                    }
                    ctx.setLineDash([]);
                    ctx.lineWidth = lw;
                }
            }
        }
    } else if (d.type === 'fib_timezone') {
        // Fib Time Zone: vertical lines at fibonacci time intervals from anchor
        var ftzA = _tvToPixel(chartId, d.t1, d.p1);
        var ftzB = _tvToPixel(chartId, d.t2, d.p2);
        if (ftzA && ftzB) {
            var tDiff = d.t2 - d.t1;
            var fibNums = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144];
            var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
            var fibTzEnabled = d.fibEnabled || [];
            var showLbls = d.showLabels !== false;
            for (var fi = 0; fi < fibNums.length; fi++) {
                if (fibTzEnabled[fi] === false) continue;
                var tLine = d.t1 + tDiff * fibNums[fi];
                var xPx = _tvToPixel(chartId, tLine, d.p1);
                if (!xPx) continue;
                if (xPx.x < 0 || xPx.x > w) continue;
                var fc = fibColors[fi % fibColors.length] || col;
                ctx.strokeStyle = fc;
                ctx.lineWidth = fi < 3 ? lw : Math.max(1, lw - 1);
                ctx.setLineDash(fi < 3 ? [] : [4, 3]);
                ctx.beginPath(); ctx.moveTo(xPx.x, 0); ctx.lineTo(xPx.x, h); ctx.stroke();
                if (showLbls) {
                    ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                    ctx.fillStyle = fc;
                    ctx.fillText(String(fibNums[fi]), xPx.x + 3, 14);
                }
            }
            ctx.setLineDash([]);
            ctx.lineWidth = lw;
            // Trend line connecting anchors
            if (d.showTrendLine !== false) {
                ctx.strokeStyle = col;
                ctx.setLineDash([6, 4]);
                ctx.globalAlpha = 0.5;
                ctx.beginPath(); ctx.moveTo(ftzA.x, ftzA.y); ctx.lineTo(ftzB.x, ftzB.y); ctx.stroke();
                ctx.globalAlpha = 1.0;
                ctx.setLineDash([]);
            }
        }
    } else if (d.type === 'fib_fan') {
        // Fib Speed Resistance Fan: fan lines from anchor A through fib-interpolated points on B
        var ffA = _tvToPixel(chartId, d.t1, d.p1);
        var ffB = _tvToPixel(chartId, d.t2, d.p2);
        if (ffA && ffB) {
            var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
            var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
            var fibEnabled = d.fibEnabled || [];
            var showLbls = d.showLabels !== false;
            var fdx = ffB.x - ffA.x, fdy = ffB.y - ffA.y;
            for (var fi = 0; fi < fibLevels.length; fi++) {
                if (fibEnabled[fi] === false) continue;
                var lvl = fibLevels[fi];
                if (lvl === 0) continue; // 0 level = horizontal through A
                var fc = fibColors[fi] || col;
                // Fan line from A to point at (B.x, lerp(A.y, B.y, lvl))
                var fanY = ffA.y + fdy * lvl;
                ctx.strokeStyle = fc;
                ctx.lineWidth = lvl === 1 ? lw : Math.max(1, lw - 1);
                ctx.setLineDash(lvl === 1 ? [] : [4, 3]);
                // Extend the line beyond B
                var extLen = 4000;
                var fDx = ffB.x - ffA.x, fDy = fanY - ffA.y;
                var fLen = Math.sqrt(fDx * fDx + fDy * fDy);
                if (fLen > 0) {
                    var eX = ffA.x + (fDx / fLen) * extLen;
                    var eY = ffA.y + (fDy / fLen) * extLen;
                    ctx.beginPath(); ctx.moveTo(ffA.x, ffA.y); ctx.lineTo(eX, eY); ctx.stroke();
                }
                if (showLbls) {
                    ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                    ctx.fillStyle = fc;
                    ctx.fillText(lvl.toFixed(3), ffB.x + 4, fanY - 4);
                }
            }
            // Fill between adjacent fan lines
            if (d.fillEnabled !== false) {
                ctx.fillStyle = col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.03;
                for (var fi = 0; fi < fibLevels.length - 1; fi++) {
                    if (fibEnabled[fi] === false || fibEnabled[fi + 1] === false) continue;
                    var y1 = ffA.y + fdy * fibLevels[fi];
                    var y2 = ffA.y + fdy * fibLevels[fi + 1];
                    ctx.beginPath();
                    ctx.moveTo(ffA.x, ffA.y);
                    ctx.lineTo(ffB.x, y1);
                    ctx.lineTo(ffB.x, y2);
                    ctx.closePath();
                    ctx.fill();
                }
                ctx.globalAlpha = 1.0;
            }
            ctx.setLineDash([]);
            ctx.lineWidth = lw;
        }
    } else if (d.type === 'fib_arc') {
        // Fib Speed Resistance Arcs: semi-circle arcs centered at A, opening away from B
        var faA = _tvToPixel(chartId, d.t1, d.p1);
        var faB = _tvToPixel(chartId, d.t2, d.p2);
        if (faA && faB) {
            var abDist = Math.sqrt(Math.pow(faB.x - faA.x, 2) + Math.pow(faB.y - faA.y, 2));
            var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
            var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
            var fibEnabled = d.fibEnabled || [];
            var showLbls = d.showLabels !== false;
            // Angle from A to B — arcs open in the opposite direction (away from B)
            var abAngle = Math.atan2(faB.y - faA.y, faB.x - faA.x);
            var arcStart = abAngle + Math.PI / 2;
            var arcEnd = abAngle - Math.PI / 2;
            // Trend line
            if (d.showTrendLine !== false) {
                ctx.strokeStyle = col;
                ctx.setLineDash([6, 4]);
                ctx.globalAlpha = 0.5;
                ctx.beginPath(); ctx.moveTo(faA.x, faA.y); ctx.lineTo(faB.x, faB.y); ctx.stroke();
                ctx.globalAlpha = 1.0;
                ctx.setLineDash([]);
            }
            for (var fi = 0; fi < fibLevels.length; fi++) {
                if (fibEnabled[fi] === false) continue;
                var lvl = fibLevels[fi];
                if (lvl === 0) continue;
                var fc = fibColors[fi] || col;
                var arcR = abDist * lvl;
                ctx.strokeStyle = fc;
                ctx.lineWidth = lvl === 1 ? lw : Math.max(1, lw - 1);
                ctx.setLineDash(lvl === 1 ? [] : [4, 3]);
                ctx.beginPath();
                ctx.arc(faA.x, faA.y, arcR, arcStart, arcEnd);
                ctx.stroke();
                if (showLbls) {
                    ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                    ctx.fillStyle = fc;
                    // Label at the end of the arc (perpendicular to AB)
                    var lblX = faA.x + arcR * Math.cos(arcEnd) + 3;
                    var lblY = faA.y + arcR * Math.sin(arcEnd) - 4;
                    ctx.fillText(lvl.toFixed(3), lblX, lblY);
                }
            }
            ctx.setLineDash([]);
            ctx.lineWidth = lw;
        }
    } else if (d.type === 'fib_circle') {
        // Fib Circles: concentric circles centered at midpoint of AB with fib-scaled radii
        var fcirA = _tvToPixel(chartId, d.t1, d.p1);
        var fcirB = _tvToPixel(chartId, d.t2, d.p2);
        if (fcirA && fcirB) {
            var cMidX = (fcirA.x + fcirB.x) / 2, cMidY = (fcirA.y + fcirB.y) / 2;
            var baseR = Math.sqrt(Math.pow(fcirB.x - fcirA.x, 2) + Math.pow(fcirB.y - fcirA.y, 2)) / 2;
            var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
            var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
            var fibEnabled = d.fibEnabled || [];
            var showLbls = d.showLabels !== false;
            for (var fi = 0; fi < fibLevels.length; fi++) {
                if (fibEnabled[fi] === false) continue;
                var lvl = fibLevels[fi];
                if (lvl === 0) continue;
                var fc = fibColors[fi] || col;
                var cR = baseR * lvl;
                ctx.strokeStyle = fc;
                ctx.lineWidth = lvl === 1 ? lw : Math.max(1, lw - 1);
                ctx.setLineDash(lvl === 1 ? [] : [4, 3]);
                ctx.beginPath();
                ctx.arc(cMidX, cMidY, cR, 0, Math.PI * 2);
                ctx.stroke();
                if (showLbls) {
                    ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                    ctx.fillStyle = fc;
                    ctx.fillText(lvl.toFixed(3), cMidX + cR + 3, cMidY - 4);
                }
            }
            // Trend line
            if (d.showTrendLine !== false) {
                ctx.strokeStyle = col;
                ctx.setLineDash([6, 4]);
                ctx.globalAlpha = 0.5;
                ctx.beginPath(); ctx.moveTo(fcirA.x, fcirA.y); ctx.lineTo(fcirB.x, fcirB.y); ctx.stroke();
                ctx.globalAlpha = 1.0;
                ctx.setLineDash([]);
            }
            ctx.lineWidth = lw;
        }
    } else if (d.type === 'fib_wedge') {
        // Fib Wedge: two trend lines from A→B and A→C with fib levels between them
        var fwA = _tvToPixel(chartId, d.t1, d.p1);
        var fwB = _tvToPixel(chartId, d.t2, d.p2);
        var fwC = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
        if (fwA && fwB) {
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.setLineDash([]);
            // Draw A→B
            ctx.beginPath(); ctx.moveTo(fwA.x, fwA.y); ctx.lineTo(fwB.x, fwB.y); ctx.stroke();
            if (fwC) {
                // Draw A→C
                ctx.beginPath(); ctx.moveTo(fwA.x, fwA.y); ctx.lineTo(fwC.x, fwC.y); ctx.stroke();
                // Fib lines between A→B and A→C
                var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : _FIB_LEVELS.slice();
                var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
                var fibEnabled = d.fibEnabled || [];
                var showLbls = d.showLabels !== false;
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    if (fibEnabled[fi] === false) continue;
                    var lvl = fibLevels[fi];
                    if (lvl === 0 || lvl === 1) continue;
                    var fc = fibColors[fi] || col;
                    // Interpolated endpoint between B and C
                    var wEndX = fwB.x + (fwC.x - fwB.x) * lvl;
                    var wEndY = fwB.y + (fwC.y - fwB.y) * lvl;
                    ctx.strokeStyle = fc;
                    ctx.lineWidth = Math.max(1, lw - 1);
                    ctx.setLineDash([4, 3]);
                    ctx.beginPath(); ctx.moveTo(fwA.x, fwA.y); ctx.lineTo(wEndX, wEndY); ctx.stroke();
                    if (showLbls) {
                        ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                        ctx.fillStyle = fc;
                        ctx.fillText(lvl.toFixed(3), wEndX + 4, wEndY - 4);
                    }
                }
                // Fill
                if (d.fillEnabled !== false) {
                    ctx.fillStyle = d.fillColor || col;
                    ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.04;
                    ctx.beginPath();
                    ctx.moveTo(fwA.x, fwA.y);
                    ctx.lineTo(fwB.x, fwB.y);
                    ctx.lineTo(fwC.x, fwC.y);
                    ctx.closePath();
                    ctx.fill();
                    ctx.globalAlpha = 1.0;
                }
                ctx.setLineDash([]);
                ctx.lineWidth = lw;
            }
        }
    } else if (d.type === 'pitchfan') {
        // Pitchfan: median line from A to midpoint(B,C), with fan lines from A through fib divisions
        var pfA = _tvToPixel(chartId, d.t1, d.p1);
        var pfB = _tvToPixel(chartId, d.t2, d.p2);
        var pfC = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
        if (pfA && pfB) {
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.setLineDash([]);
            ctx.beginPath(); ctx.moveTo(pfA.x, pfA.y); ctx.lineTo(pfB.x, pfB.y); ctx.stroke();
            if (pfC) {
                ctx.beginPath(); ctx.moveTo(pfA.x, pfA.y); ctx.lineTo(pfC.x, pfC.y); ctx.stroke();
                // Median line to midpoint of B and C
                var pfMidX = (pfB.x + pfC.x) / 2, pfMidY = (pfB.y + pfC.y) / 2;
                if (d.showMedian !== false) {
                    ctx.strokeStyle = d.medianColor || col;
                    ctx.setLineDash([6, 4]);
                    ctx.beginPath(); ctx.moveTo(pfA.x, pfA.y); ctx.lineTo(pfMidX, pfMidY); ctx.stroke();
                    ctx.setLineDash([]);
                    ctx.strokeStyle = col;
                }
                // Fan lines from A through fib divisions between B and C
                var pfDefLevels = [0.236, 0.382, 0.5, 0.618, 0.786];
                var fibLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : pfDefLevels;
                var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
                var fibEnabled = d.fibEnabled || [];
                var showLbls = d.showLabels !== false;
                for (var fi = 0; fi < fibLevels.length; fi++) {
                    if (fibEnabled[fi] === false) continue;
                    var lvl = fibLevels[fi];
                    var fc = fibColors[fi] || col;
                    var pfTgtX = pfB.x + (pfC.x - pfB.x) * lvl;
                    var pfTgtY = pfB.y + (pfC.y - pfB.y) * lvl;
                    // Extend from A through target point
                    var pfDx = pfTgtX - pfA.x, pfDy = pfTgtY - pfA.y;
                    var pfLen = Math.sqrt(pfDx * pfDx + pfDy * pfDy);
                    if (pfLen > 0) {
                        var pfExt = 4000;
                        ctx.strokeStyle = fc;
                        ctx.lineWidth = Math.max(1, lw - 1);
                        ctx.setLineDash([4, 3]);
                        ctx.beginPath();
                        ctx.moveTo(pfA.x, pfA.y);
                        ctx.lineTo(pfA.x + (pfDx / pfLen) * pfExt, pfA.y + (pfDy / pfLen) * pfExt);
                        ctx.stroke();
                    }
                    if (showLbls) {
                        ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                        ctx.fillStyle = fc;
                        ctx.fillText(lvl.toFixed(3), pfTgtX + 4, pfTgtY - 4);
                    }
                }
                ctx.setLineDash([]);
                ctx.lineWidth = lw;
            }
        }
    } else if (d.type === 'fib_time') {
        // Trend-Based Fib Time: 3-point, A→B time range projected from C as vertical lines
        var ftA = _tvToPixel(chartId, d.t1, d.p1);
        var ftB = _tvToPixel(chartId, d.t2, d.p2);
        var ftC = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
        if (ftA && ftB) {
            var tDiff = d.t2 - d.t1;
            // Trend line A→B
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.setLineDash([6, 4]);
            ctx.globalAlpha = 0.5;
            ctx.beginPath(); ctx.moveTo(ftA.x, ftA.y); ctx.lineTo(ftB.x, ftB.y); ctx.stroke();
            if (ftC) {
                ctx.beginPath(); ctx.moveTo(ftB.x, ftB.y); ctx.lineTo(ftC.x, ftC.y); ctx.stroke();
            }
            ctx.globalAlpha = 1.0;
            ctx.setLineDash([]);
            // Vertical lines at fib ratios of AB time, projected from C
            var projT = ftC ? d.t3 : d.t1;
            var ftLevels = (d.fibLevelValues && d.fibLevelValues.length) ? d.fibLevelValues : [0, 0.382, 0.5, 0.618, 1, 1.382, 1.618, 2, 2.618, 4.236];
            var fibColors = (d.fibColors && d.fibColors.length) ? d.fibColors : _getFibColors();
            var fibEnabled = d.fibEnabled || [];
            var showLbls = d.showLabels !== false;
            for (var fi = 0; fi < ftLevels.length; fi++) {
                if (fibEnabled[fi] === false) continue;
                var tLine = projT + tDiff * ftLevels[fi];
                var xPx = _tvToPixel(chartId, tLine, d.p1);
                if (!xPx) continue;
                if (xPx.x < 0 || xPx.x > w) continue;
                var fc = fibColors[fi % fibColors.length] || col;
                ctx.strokeStyle = fc;
                ctx.lineWidth = (ftLevels[fi] === 0 || ftLevels[fi] === 1) ? lw : Math.max(1, lw - 1);
                ctx.setLineDash((ftLevels[fi] === 0 || ftLevels[fi] === 1) ? [] : [4, 3]);
                ctx.beginPath(); ctx.moveTo(xPx.x, 0); ctx.lineTo(xPx.x, h); ctx.stroke();
                if (showLbls) {
                    ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                    ctx.fillStyle = fc;
                    ctx.fillText(ftLevels[fi].toFixed(3), xPx.x + 3, 14);
                }
            }
            ctx.setLineDash([]);
            ctx.lineWidth = lw;
        }
    } else if (d.type === 'fib_spiral') {
        // Fib Spiral: golden logarithmic spiral from center A through B
        var fsA = _tvToPixel(chartId, d.t1, d.p1);
        var fsB = _tvToPixel(chartId, d.t2, d.p2);
        if (fsA && fsB) {
            var fsDx = fsB.x - fsA.x, fsDy = fsB.y - fsA.y;
            var fsR = Math.sqrt(fsDx * fsDx + fsDy * fsDy);
            var fsStartAngle = Math.atan2(fsDy, fsDx);
            var fsPhi = 1.6180339887;
            var fsGrowth = Math.log(fsPhi) / (Math.PI / 2);
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.beginPath();
            var fsNPts = 400;
            var fsMinTheta = -4 * Math.PI;
            var fsMaxTheta = 4 * Math.PI;
            var fsFirst = true;
            for (var fi = 0; fi <= fsNPts; fi++) {
                var theta = fsMinTheta + (fi / fsNPts) * (fsMaxTheta - fsMinTheta);
                var r = fsR * Math.exp(fsGrowth * theta);
                if (r < 1 || r > 5000) { fsFirst = true; continue; }
                var sx = fsA.x + r * Math.cos(fsStartAngle + theta);
                var sy = fsA.y + r * Math.sin(fsStartAngle + theta);
                if (fsFirst) { ctx.moveTo(sx, sy); fsFirst = false; }
                else ctx.lineTo(sx, sy);
            }
            ctx.stroke();
            // AB reference line
            ctx.setLineDash([6, 4]);
            ctx.globalAlpha = 0.5;
            ctx.beginPath(); ctx.moveTo(fsA.x, fsA.y); ctx.lineTo(fsB.x, fsB.y); ctx.stroke();
            ctx.globalAlpha = 1.0;
            ctx.setLineDash([]);
        }
    } else if (d.type === 'gann_box') {
        // Gann Box: rectangular grid with diagonal, price/time subdivisions
        var gbA = _tvToPixel(chartId, d.t1, d.p1);
        var gbB = _tvToPixel(chartId, d.t2, d.p2);
        if (gbA && gbB) {
            var gblx = Math.min(gbA.x, gbB.x), gbrx = Math.max(gbA.x, gbB.x);
            var gbty = Math.min(gbA.y, gbB.y), gbby = Math.max(gbA.y, gbB.y);
            var gbW = gbrx - gblx, gbH = gbby - gbty;
            // Box outline
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.strokeRect(gblx, gbty, gbW, gbH);
            // Horizontal grid lines
            var gbLevels = d.gannLevels || [0.25, 0.5, 0.75];
            var gbColors = (d.fibColors && d.fibColors.length) ? d.fibColors : [];
            var gbEnabled = d.fibEnabled || [];
            for (var gi = 0; gi < gbLevels.length; gi++) {
                if (gbEnabled[gi] === false) continue;
                var gy = gbty + gbH * gbLevels[gi];
                ctx.strokeStyle = gbColors[gi] || col;
                ctx.lineWidth = Math.max(1, lw - 1);
                ctx.setLineDash([4, 3]);
                ctx.beginPath(); ctx.moveTo(gblx, gy); ctx.lineTo(gbrx, gy); ctx.stroke();
            }
            // Vertical grid lines
            for (var gi = 0; gi < gbLevels.length; gi++) {
                if (gbEnabled[gi] === false) continue;
                var gx = gblx + gbW * gbLevels[gi];
                ctx.strokeStyle = gbColors[gi] || col;
                ctx.lineWidth = Math.max(1, lw - 1);
                ctx.setLineDash([4, 3]);
                ctx.beginPath(); ctx.moveTo(gx, gbty); ctx.lineTo(gx, gbby); ctx.stroke();
            }
            ctx.setLineDash([]);
            // Main diagonal
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.beginPath(); ctx.moveTo(gblx, gbby); ctx.lineTo(gbrx, gbty); ctx.stroke();
            // Counter-diagonal
            ctx.setLineDash([4, 3]);
            ctx.beginPath(); ctx.moveTo(gblx, gbty); ctx.lineTo(gbrx, gbby); ctx.stroke();
            ctx.setLineDash([]);
            // Background fill
            if (d.fillEnabled !== false) {
                ctx.fillStyle = d.fillColor || col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.03;
                ctx.fillRect(gblx, gbty, gbW, gbH);
                ctx.globalAlpha = 1.0;
            }
        }
    } else if (d.type === 'gann_square_fixed') {
        // Gann Square Fixed: fixed-ratio square grid
        var gsfA = _tvToPixel(chartId, d.t1, d.p1);
        var gsfB = _tvToPixel(chartId, d.t2, d.p2);
        if (gsfA && gsfB) {
            var gsfDx = Math.abs(gsfB.x - gsfA.x), gsfDy = Math.abs(gsfB.y - gsfA.y);
            var gsfSize = Math.max(gsfDx, gsfDy);
            var gsfX = Math.min(gsfA.x, gsfB.x), gsfY = Math.min(gsfA.y, gsfB.y);
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.strokeRect(gsfX, gsfY, gsfSize, gsfSize);
            var gsfLevels = d.gannLevels || [0.25, 0.5, 0.75];
            var gsfColors = (d.fibColors && d.fibColors.length) ? d.fibColors : [];
            var gsfEnabled = d.fibEnabled || [];
            for (var gi = 0; gi < gsfLevels.length; gi++) {
                if (gsfEnabled[gi] === false) continue;
                var gy = gsfY + gsfSize * gsfLevels[gi];
                var gx = gsfX + gsfSize * gsfLevels[gi];
                ctx.strokeStyle = gsfColors[gi] || col;
                ctx.lineWidth = Math.max(1, lw - 1);
                ctx.setLineDash([4, 3]);
                ctx.beginPath(); ctx.moveTo(gsfX, gy); ctx.lineTo(gsfX + gsfSize, gy); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(gx, gsfY); ctx.lineTo(gx, gsfY + gsfSize); ctx.stroke();
            }
            ctx.setLineDash([]);
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.beginPath(); ctx.moveTo(gsfX, gsfY + gsfSize); ctx.lineTo(gsfX + gsfSize, gsfY); ctx.stroke();
            ctx.setLineDash([4, 3]);
            ctx.beginPath(); ctx.moveTo(gsfX, gsfY); ctx.lineTo(gsfX + gsfSize, gsfY + gsfSize); ctx.stroke();
            ctx.setLineDash([]);
            if (d.fillEnabled !== false) {
                ctx.fillStyle = d.fillColor || col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.03;
                ctx.fillRect(gsfX, gsfY, gsfSize, gsfSize);
                ctx.globalAlpha = 1.0;
            }
        }
    } else if (d.type === 'gann_square') {
        // Gann Square: rectangular grid with diagonals and mid-cross
        var gsA = _tvToPixel(chartId, d.t1, d.p1);
        var gsB = _tvToPixel(chartId, d.t2, d.p2);
        if (gsA && gsB) {
            var gslx = Math.min(gsA.x, gsB.x), gsrx = Math.max(gsA.x, gsB.x);
            var gsty = Math.min(gsA.y, gsB.y), gsby = Math.max(gsA.y, gsB.y);
            var gsW = gsrx - gslx, gsH = gsby - gsty;
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.strokeRect(gslx, gsty, gsW, gsH);
            var gsLevels = d.gannLevels || [0.25, 0.5, 0.75];
            var gsColors = (d.fibColors && d.fibColors.length) ? d.fibColors : [];
            var gsEnabled = d.fibEnabled || [];
            for (var gi = 0; gi < gsLevels.length; gi++) {
                if (gsEnabled[gi] === false) continue;
                var gy = gsty + gsH * gsLevels[gi];
                var gx = gslx + gsW * gsLevels[gi];
                ctx.strokeStyle = gsColors[gi] || col;
                ctx.lineWidth = Math.max(1, lw - 1);
                ctx.setLineDash([4, 3]);
                ctx.beginPath(); ctx.moveTo(gslx, gy); ctx.lineTo(gsrx, gy); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(gx, gsty); ctx.lineTo(gx, gsby); ctx.stroke();
            }
            ctx.setLineDash([]);
            ctx.strokeStyle = col;
            ctx.lineWidth = lw;
            ctx.beginPath(); ctx.moveTo(gslx, gsby); ctx.lineTo(gsrx, gsty); ctx.stroke();
            ctx.setLineDash([4, 3]);
            ctx.beginPath(); ctx.moveTo(gslx, gsty); ctx.lineTo(gsrx, gsby); ctx.stroke();
            ctx.setLineDash([]);
            // Mid-cross
            var gsMidX = (gslx + gsrx) / 2, gsMidY = (gsty + gsby) / 2;
            ctx.setLineDash([2, 2]);
            ctx.globalAlpha = 0.4;
            ctx.beginPath(); ctx.moveTo(gsMidX, gsty); ctx.lineTo(gsMidX, gsby); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(gslx, gsMidY); ctx.lineTo(gsrx, gsMidY); ctx.stroke();
            ctx.globalAlpha = 1.0;
            ctx.setLineDash([]);
            if (d.fillEnabled !== false) {
                ctx.fillStyle = d.fillColor || col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.03;
                ctx.fillRect(gslx, gsty, gsW, gsH);
                ctx.globalAlpha = 1.0;
            }
        }
    } else if (d.type === 'gann_fan') {
        // Gann Fan: fan lines from A at standard Gann angles, B defines the 1x1 line
        var gfA = _tvToPixel(chartId, d.t1, d.p1);
        var gfB = _tvToPixel(chartId, d.t2, d.p2);
        if (gfA && gfB) {
            var gfDx = gfB.x - gfA.x, gfDy = gfB.y - gfA.y;
            var gannAngles = [
                { name: '1\u00d78', ratio: 0.125 },
                { name: '1\u00d74', ratio: 0.25 },
                { name: '1\u00d73', ratio: 0.333 },
                { name: '1\u00d72', ratio: 0.5 },
                { name: '1\u00d71', ratio: 1 },
                { name: '2\u00d71', ratio: 2 },
                { name: '3\u00d71', ratio: 3 },
                { name: '4\u00d71', ratio: 4 },
                { name: '8\u00d71', ratio: 8 }
            ];
            var gfColors = (d.fibColors && d.fibColors.length) ? d.fibColors : [];
            var gfEnabled = d.fibEnabled || [];
            var showLbls = d.showLabels !== false;
            for (var gi = 0; gi < gannAngles.length; gi++) {
                if (gfEnabled[gi] === false) continue;
                var gRatio = gannAngles[gi].ratio;
                var fanEndX = gfA.x + gfDx;
                var fanEndY = gfA.y + gfDy * gRatio;
                var fDx = fanEndX - gfA.x, fDy = fanEndY - gfA.y;
                var fLen = Math.sqrt(fDx * fDx + fDy * fDy);
                if (fLen > 0) {
                    var extLen = 4000;
                    var eX = gfA.x + (fDx / fLen) * extLen;
                    var eY = gfA.y + (fDy / fLen) * extLen;
                    ctx.strokeStyle = gfColors[gi] || col;
                    ctx.lineWidth = gRatio === 1 ? lw : Math.max(1, lw - 1);
                    ctx.setLineDash(gRatio === 1 ? [] : [4, 3]);
                    ctx.beginPath(); ctx.moveTo(gfA.x, gfA.y); ctx.lineTo(eX, eY); ctx.stroke();
                    if (showLbls) {
                        ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                        ctx.fillStyle = gfColors[gi] || col;
                        ctx.fillText(gannAngles[gi].name, fanEndX + 4, fanEndY - 4);
                    }
                }
            }
            ctx.setLineDash([]);
            ctx.lineWidth = lw;
        }
    } else if (d.type === 'measure') {
        var m1 = _tvToPixel(chartId, d.t1, d.p1);
        var m2 = _tvToPixel(chartId, d.t2, d.p2);
        if (m1 && m2) {
            var priceDiff = d.p2 - d.p1;
            var pctChange = d.p1 !== 0 ? ((priceDiff / d.p1) * 100) : 0;
            var isUp = priceDiff >= 0;
            var measureUpCol = d.colorUp || _cssVar('--pywry-draw-measure-up');
            var measureDnCol = d.colorDown || _cssVar('--pywry-draw-measure-down');
            var measureCol = isUp ? measureUpCol : measureDnCol;
            ctx.strokeStyle = measureCol;
            ctx.fillStyle = measureCol;

            // Shaded rectangle between the two points (like TV)
            var mrx = Math.min(m1.x, m2.x), mry = Math.min(m1.y, m2.y);
            var mrw = Math.abs(m2.x - m1.x), mrh = Math.abs(m2.y - m1.y);
            ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.08;
            ctx.fillRect(mrx, mry, mrw, mrh);
            ctx.globalAlpha = 1.0;

            // Vertical dashed lines at each x
            ctx.setLineDash([3, 3]);
            ctx.beginPath();
            ctx.moveTo(m1.x, Math.min(m1.y, m2.y) - 20);
            ctx.lineTo(m1.x, Math.max(m1.y, m2.y) + 20);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(m2.x, Math.min(m1.y, m2.y) - 20);
            ctx.lineTo(m2.x, Math.max(m1.y, m2.y) + 20);
            ctx.stroke();
            ctx.setLineDash([]);

            // Horizontal lines at each price
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(mrx, m1.y);
            ctx.lineTo(mrx + mrw, m1.y);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(mrx, m2.y);
            ctx.lineTo(mrx + mrw, m2.y);
            ctx.stroke();
            ctx.lineWidth = lw;

            // Info label (like TV: "−15.76 (−5.64%) −1,576")
            var label = (isUp ? '+' : '') + priceDiff.toFixed(2) +
                        ' (' + (isUp ? '+' : '') + pctChange.toFixed(2) + '%)';
            var mFontSize = d.fontSize || 12;
            ctx.font = 'bold ' + mFontSize + 'px -apple-system,BlinkMacSystemFont,sans-serif';
            var met = ctx.measureText(label);
            var boxPad = 6;
            var bx = (m1.x + m2.x) / 2 - met.width / 2 - boxPad;
            var by = Math.min(m1.y, m2.y) - 28;
            // Background pill
            ctx.fillStyle = measureCol;
            ctx.globalAlpha = 0.9;
            _roundRect(ctx, bx, by, met.width + boxPad * 2, 22, 4);
            ctx.fill();
            ctx.globalAlpha = 1.0;
            ctx.fillStyle = _cssVar('--pywry-draw-label-text');
            ctx.textBaseline = 'middle';
            ctx.fillText(label, bx + boxPad, by + 11);
            ctx.textBaseline = 'alphabetic';
        }
    } else if (d.type === 'ray') {
        // Ray: from point A through point B, extending to infinity in B direction
        var ra = _tvToPixel(chartId, d.t1, d.p1);
        var rb = _tvToPixel(chartId, d.t2, d.p2);
        if (ra && rb) {
            var rdx = rb.x - ra.x, rdy = rb.y - ra.y;
            var rlen = Math.sqrt(rdx * rdx + rdy * rdy);
            if (rlen > 0) {
                var ext = 4000;
                var rux = rdx / rlen, ruy = rdy / rlen;
                ctx.beginPath();
                ctx.moveTo(ra.x, ra.y);
                ctx.lineTo(ra.x + rux * ext, ra.y + ruy * ext);
                ctx.stroke();
            }
            // Text annotation
            if (d.text) {
                var rMidX = (ra.x + rb.x) / 2, rMidY = (ra.y + rb.y) / 2;
                var rFs = d.textFontSize || 12;
                var rTStyle = (d.textItalic ? 'italic ' : '') + (d.textBold ? 'bold ' : '');
                ctx.font = rTStyle + rFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
                ctx.fillStyle = d.textColor || col;
                ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
                ctx.fillText(d.text, rMidX, rMidY - 6);
                ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
            }
        }
    } else if (d.type === 'extended_line') {
        // Extended line: infinite in both directions through A and B
        var ea = _tvToPixel(chartId, d.t1, d.p1);
        var eb = _tvToPixel(chartId, d.t2, d.p2);
        if (ea && eb) {
            var edx = eb.x - ea.x, edy = eb.y - ea.y;
            var elen = Math.sqrt(edx * edx + edy * edy);
            if (elen > 0) {
                var eext = 4000;
                var eux = edx / elen, euy = edy / elen;
                ctx.beginPath();
                ctx.moveTo(ea.x - eux * eext, ea.y - euy * eext);
                ctx.lineTo(eb.x + eux * eext, eb.y + euy * eext);
                ctx.stroke();
            }
            // Text annotation
            if (d.text) {
                var eMidX = (ea.x + eb.x) / 2, eMidY = (ea.y + eb.y) / 2;
                var eFs = d.textFontSize || 12;
                var eTStyle = (d.textItalic ? 'italic ' : '') + (d.textBold ? 'bold ' : '');
                ctx.font = eTStyle + eFs + 'px -apple-system,BlinkMacSystemFont,sans-serif';
                ctx.fillStyle = d.textColor || col;
                ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
                ctx.fillText(d.text, eMidX, eMidY - 6);
                ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
            }
        }
    } else if (d.type === 'hray') {
        // Horizontal ray: from anchor point extending right
        var hry = series.priceToCoordinate(d.p1);
        var hra = _tvToPixel(chartId, d.t1, d.p1);
        if (hry !== null && hra) {
            ctx.beginPath();
            ctx.moveTo(hra.x, hry);
            ctx.lineTo(w, hry);
            ctx.stroke();
        }
    } else if (d.type === 'vline') {
        // Vertical line: at a specific time, top to bottom
        var va = _tvToPixel(chartId, d.t1, d.p1 || 0);
        if (va) {
            ctx.beginPath();
            ctx.moveTo(va.x, 0);
            ctx.lineTo(va.x, h);
            ctx.stroke();
        }
    } else if (d.type === 'crossline') {
        // Cross line: vertical + horizontal at a specific point
        var cla = _tvToPixel(chartId, d.t1, d.p1);
        var cly = series.priceToCoordinate(d.p1);
        if (cla && cly !== null) {
            ctx.beginPath();
            ctx.moveTo(cla.x, 0);
            ctx.lineTo(cla.x, h);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0, cly);
            ctx.lineTo(w, cly);
            ctx.stroke();
        }
    } else if (d.type === 'flat_channel') {
        // Flat top/bottom: two horizontal parallel lines at p1 and p2
        var fy1 = series.priceToCoordinate(d.p1);
        var fy2 = series.priceToCoordinate(d.p2);
        if (fy1 !== null && fy2 !== null) {
            if (d.fillEnabled !== false) {
                ctx.fillStyle = d.fillColor || col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.08;
                ctx.fillRect(0, Math.min(fy1, fy2), w, Math.abs(fy2 - fy1));
                ctx.globalAlpha = 1.0;
            }
            ctx.beginPath();
            ctx.moveTo(0, fy1);
            ctx.lineTo(w, fy1);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0, fy2);
            ctx.lineTo(w, fy2);
            ctx.stroke();
        }
    } else if (d.type === 'regression_channel') {
        // Regression channel: linear regression with separate base/up/down lines
        var ra1 = _tvToPixel(chartId, d.t1, d.p1);
        var ra2 = _tvToPixel(chartId, d.t2, d.p2);
        if (ra1 && ra2) {
            var rcUpOff = d.upperDeviation !== undefined ? d.upperDeviation : (d.offset || 30);
            var rcDnOff = d.lowerDeviation !== undefined ? d.lowerDeviation : (d.offset || 30);
            var useUpper = d.useUpperDeviation !== false;
            var useLower = d.useLowerDeviation !== false;
            var ext = 4000;
            // Extend lines support
            var doExtend = !!d.extendLines;
            var dx = ra2.x - ra1.x, dy = ra2.y - ra1.y;
            var len = Math.sqrt(dx * dx + dy * dy);
            var ux = len > 0 ? dx / len : 1, uy = len > 0 ? dy / len : 0;
            var sx1 = ra1.x, sy1 = ra1.y, sx2 = ra2.x, sy2 = ra2.y;
            if (doExtend && len > 0) {
                sx1 = ra1.x - ux * ext; sy1 = ra1.y - uy * ext;
                sx2 = ra2.x + ux * ext; sy2 = ra2.y + uy * ext;
            }
            // Perpendicular unit vector (pointing upward in screen coords)
            var px = len > 0 ? -dy / len : 0, py = len > 0 ? dx / len : -1;
            // Helper: apply per-line style
            function _rcSetLineStyle(lineStyle) {
                ctx.setLineDash(lineStyle === 1 ? [6,4] : lineStyle === 2 ? [2,3] : []);
            }
            // Base line
            if (d.showBaseLine !== false) {
                ctx.strokeStyle = d.baseColor || col;
                ctx.lineWidth = d.baseWidth || defW;
                _rcSetLineStyle(d.baseLineStyle !== undefined ? d.baseLineStyle : (d.lineStyle || 0));
                ctx.beginPath();
                ctx.moveTo(sx1, sy1);
                ctx.lineTo(sx2, sy2);
                ctx.stroke();
            }
            // Upper bound
            if (useUpper && d.showUpLine !== false) {
                ctx.strokeStyle = d.upColor || col;
                ctx.lineWidth = d.upWidth || defW;
                _rcSetLineStyle(d.upLineStyle !== undefined ? d.upLineStyle : 1);
                ctx.globalAlpha = 0.8;
                ctx.beginPath();
                ctx.moveTo(sx1 + px * rcUpOff, sy1 + py * rcUpOff);
                ctx.lineTo(sx2 + px * rcUpOff, sy2 + py * rcUpOff);
                ctx.stroke();
                ctx.globalAlpha = 1.0;
            }
            // Lower bound
            if (useLower && d.showDownLine !== false) {
                ctx.strokeStyle = d.downColor || col;
                ctx.lineWidth = d.downWidth || defW;
                _rcSetLineStyle(d.downLineStyle !== undefined ? d.downLineStyle : 1);
                ctx.globalAlpha = 0.8;
                ctx.beginPath();
                ctx.moveTo(sx1 - px * rcDnOff, sy1 - py * rcDnOff);
                ctx.lineTo(sx2 - px * rcDnOff, sy2 - py * rcDnOff);
                ctx.stroke();
                ctx.globalAlpha = 1.0;
            }
            // Reset stroke for selection handles
            ctx.strokeStyle = col;
            ctx.lineWidth = defW;
            _rcSetLineStyle(d.lineStyle || 0);
            // Fill between upper and lower bounds
            if (d.fillEnabled !== false && (useUpper || useLower)) {
                ctx.fillStyle = d.fillColor || col;
                ctx.globalAlpha = d.fillOpacity !== undefined ? d.fillOpacity : 0.05;
                var uOff = useUpper ? rcUpOff : 0;
                var dOff = useLower ? rcDnOff : 0;
                ctx.beginPath();
                ctx.moveTo(sx1 + px * uOff, sy1 + py * uOff);
                ctx.lineTo(sx2 + px * uOff, sy2 + py * uOff);
                ctx.lineTo(sx2 - px * dOff, sy2 - py * dOff);
                ctx.lineTo(sx1 - px * dOff, sy1 - py * dOff);
                ctx.closePath();
                ctx.fill();
                ctx.globalAlpha = 1.0;
            }
            // Pearson's R label
            if (d.showPearsonsR) {
                var midX = (ra1.x + ra2.x) / 2, midY = (ra1.y + ra2.y) / 2;
                var vals = _tvGetSeriesDataBetween(chartId, d.t1, d.t2);
                var rVal = vals ? _tvPearsonsR(vals) : null;
                if (rVal !== null) {
                    ctx.font = '11px -apple-system,BlinkMacSystemFont,sans-serif';
                    ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
                    ctx.fillStyle = col;
                    ctx.globalAlpha = 0.9;
                    ctx.fillText('R = ' + rVal.toFixed(4), midX, midY - 8);
                    ctx.globalAlpha = 1.0;
                }
            }
        }
    } else if (d.type === 'brush' || d.type === 'highlighter') {
        // Brush/Highlighter: freeform path through collected points
        var pts = d.points;
        if (pts && pts.length > 1) {
            if (d.opacity !== undefined && d.opacity < 1) ctx.globalAlpha = d.opacity;
            if (d.type === 'highlighter') {
                ctx.lineCap = 'round';
                ctx.lineJoin = 'round';
            }
            ctx.beginPath();
            var bp0 = _tvToPixel(chartId, pts[0].t, pts[0].p);
            if (bp0) {
                ctx.moveTo(bp0.x, bp0.y);
                for (var bi = 1; bi < pts.length; bi++) {
                    var bpi = _tvToPixel(chartId, pts[bi].t, pts[bi].p);
                    if (bpi) ctx.lineTo(bpi.x, bpi.y);
                }
                ctx.stroke();
            }
            ctx.globalAlpha = 1.0;
        }
    } else if (d.type === 'arrow_marker') {
        // Arrow Marker: fat filled arrow shape from p1 (tail) to p2 (tip)
        if (p1 && p2) {
            var amFillCol = d.fillColor || d.color || defColor;
            var amBorderCol = d.borderColor || d.color || defColor;
            var amTextCol = d.textColor || d.color || defColor;
            var amdx = p2.x - p1.x, amdy = p2.y - p1.y;
            var amLen = Math.sqrt(amdx * amdx + amdy * amdy);
            if (amLen > 1) {
                var amux = amdx / amLen, amuy = amdy / amLen;
                var amnx = -amuy, amny = amux;
                var amHeadLen = Math.min(amLen * 0.38, 80);
                var amHeadW = Math.max(amLen * 0.22, 16);
                var amShaftW = amHeadW * 0.38;
                var ambx = p2.x - amux * amHeadLen, amby = p2.y - amuy * amHeadLen;
                ctx.beginPath();
                ctx.moveTo(p2.x, p2.y);
                ctx.lineTo(ambx + amnx * amHeadW, amby + amny * amHeadW);
                ctx.lineTo(ambx + amnx * amShaftW, amby + amny * amShaftW);
                ctx.lineTo(p1.x + amnx * amShaftW, p1.y + amny * amShaftW);
                ctx.lineTo(p1.x - amnx * amShaftW, p1.y - amny * amShaftW);
                ctx.lineTo(ambx - amnx * amShaftW, amby - amny * amShaftW);
                ctx.lineTo(ambx - amnx * amHeadW, amby - amny * amHeadW);
                ctx.closePath();
                ctx.fillStyle = amFillCol;
                ctx.fill();
                ctx.strokeStyle = amBorderCol;
                ctx.lineWidth = 1;
                ctx.stroke();
            }
            if (d.text) {
                var _amfs = d.fontSize || 16;
                var _amfw = (d.bold ? 'bold ' : '') + (d.italic ? 'italic ' : '');
                ctx.font = _amfw + _amfs + 'px Arial, sans-serif';
                ctx.fillStyle = amTextCol;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillText(d.text, p1.x, p1.y + 8);
            }
        }
    } else if (d.type === 'arrow') {
        // Arrow: thin line with arrowhead at p2
        if (p1 && p2) {
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
            var adx = p2.x - p1.x, ady = p2.y - p1.y;
            var aAngle = Math.atan2(ady, adx);
            var aLen = 12;
            ctx.beginPath();
            ctx.moveTo(p2.x, p2.y);
            ctx.lineTo(p2.x - aLen * Math.cos(aAngle - 0.4), p2.y - aLen * Math.sin(aAngle - 0.4));
            ctx.moveTo(p2.x, p2.y);
            ctx.lineTo(p2.x - aLen * Math.cos(aAngle + 0.4), p2.y - aLen * Math.sin(aAngle + 0.4));
            ctx.stroke();
            if (d.text) {
                var _afs = d.fontSize || 16;
                var _afw = (d.bold ? 'bold ' : '') + (d.italic ? 'italic ' : '');
                ctx.font = _afw + _afs + 'px Arial, sans-serif';
                ctx.fillStyle = col;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillText(d.text, p2.x, p2.y + 6);
            }
        }
    } else if (d.type === 'arrow_mark_up') {
        if (p1) {
            var amu_fc = d.fillColor || d.color || defColor;
            var amu_bc = d.borderColor || d.color || defColor;
            var amu_tc = d.textColor || d.color || defColor;
            var amSz = (d.size || 30) / 2;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y - amSz);
            ctx.lineTo(p1.x - amSz * 0.7, p1.y + amSz * 0.5);
            ctx.lineTo(p1.x + amSz * 0.7, p1.y + amSz * 0.5);
            ctx.closePath();
            ctx.fillStyle = amu_fc;
            ctx.fill();
            ctx.strokeStyle = amu_bc;
            ctx.lineWidth = 1;
            ctx.stroke();
            if (d.text && mouseOver) {
                var _afs = d.fontSize || 16;
                var _afw = (d.bold ? 'bold ' : '') + (d.italic ? 'italic ' : '');
                ctx.font = _afw + _afs + 'px Arial, sans-serif';
                ctx.fillStyle = amu_tc;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillText(d.text, p1.x, p1.y + amSz * 0.5 + 4);
            }
        }
    } else if (d.type === 'arrow_mark_down') {
        if (p1) {
            var amd_fc = d.fillColor || d.color || defColor;
            var amd_bc = d.borderColor || d.color || defColor;
            var amd_tc = d.textColor || d.color || defColor;
            var amSz = (d.size || 30) / 2;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y + amSz);
            ctx.lineTo(p1.x - amSz * 0.7, p1.y - amSz * 0.5);
            ctx.lineTo(p1.x + amSz * 0.7, p1.y - amSz * 0.5);
            ctx.closePath();
            ctx.fillStyle = amd_fc;
            ctx.fill();
            ctx.strokeStyle = amd_bc;
            ctx.lineWidth = 1;
            ctx.stroke();
            if (d.text && mouseOver) {
                var _afs = d.fontSize || 16;
                var _afw = (d.bold ? 'bold ' : '') + (d.italic ? 'italic ' : '');
                ctx.font = _afw + _afs + 'px Arial, sans-serif';
                ctx.fillStyle = amd_tc;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'bottom';
                ctx.fillText(d.text, p1.x, p1.y - amSz * 0.5 - 4);
            }
        }
    } else if (d.type === 'arrow_mark_left') {
        if (p1) {
            var aml_fc = d.fillColor || d.color || defColor;
            var aml_bc = d.borderColor || d.color || defColor;
            var aml_tc = d.textColor || d.color || defColor;
            var amSz = (d.size || 30) / 2;
            ctx.beginPath();
            ctx.moveTo(p1.x - amSz, p1.y);
            ctx.lineTo(p1.x + amSz * 0.5, p1.y - amSz * 0.7);
            ctx.lineTo(p1.x + amSz * 0.5, p1.y + amSz * 0.7);
            ctx.closePath();
            ctx.fillStyle = aml_fc;
            ctx.fill();
            ctx.strokeStyle = aml_bc;
            ctx.lineWidth = 1;
            ctx.stroke();
            if (d.text && mouseOver) {
                var _afs = d.fontSize || 16;
                var _afw = (d.bold ? 'bold ' : '') + (d.italic ? 'italic ' : '');
                ctx.font = _afw + _afs + 'px Arial, sans-serif';
                ctx.fillStyle = aml_tc;
                ctx.textAlign = 'left';
                ctx.textBaseline = 'middle';
                ctx.fillText(d.text, p1.x + amSz * 0.5 + 4, p1.y);
            }
        }
    } else if (d.type === 'arrow_mark_right') {
        if (p1) {
            var amr_fc = d.fillColor || d.color || defColor;
            var amr_bc = d.borderColor || d.color || defColor;
            var amr_tc = d.textColor || d.color || defColor;
            var amSz = (d.size || 30) / 2;
            ctx.beginPath();
            ctx.moveTo(p1.x + amSz, p1.y);
            ctx.lineTo(p1.x - amSz * 0.5, p1.y - amSz * 0.7);
            ctx.lineTo(p1.x - amSz * 0.5, p1.y + amSz * 0.7);
            ctx.closePath();
            ctx.fillStyle = amr_fc;
            ctx.fill();
            ctx.strokeStyle = amr_bc;
            ctx.lineWidth = 1;
            ctx.stroke();
            if (d.text && mouseOver) {
                var _afs = d.fontSize || 16;
                var _afw = (d.bold ? 'bold ' : '') + (d.italic ? 'italic ' : '');
                ctx.font = _afw + _afs + 'px Arial, sans-serif';
                ctx.fillStyle = amr_tc;
                ctx.textAlign = 'right';
                ctx.textBaseline = 'middle';
                ctx.fillText(d.text, p1.x - amSz * 0.5 - 4, p1.y);
            }
        }
    } else if (d.type === 'circle') {
        // Circle: center at midpoint, radius = distance/2
        if (p1 && p2) {
            var cx = (p1.x + p2.x) / 2, cy = (p1.y + p2.y) / 2;
            var cr = Math.sqrt(Math.pow(p2.x - p1.x, 2) + Math.pow(p2.y - p1.y, 2)) / 2;
            ctx.beginPath();
            ctx.arc(cx, cy, cr, 0, Math.PI * 2);
            if (d.fillColor) { ctx.fillStyle = d.fillColor; ctx.fill(); }
            ctx.stroke();
        }
    } else if (d.type === 'ellipse') {
        // Ellipse: bounding box from p1 to p2
        if (p1 && p2) {
            var ecx = (p1.x + p2.x) / 2, ecy = (p1.y + p2.y) / 2;
            var erx = Math.abs(p2.x - p1.x) / 2, ery = Math.abs(p2.y - p1.y) / 2;
            ctx.beginPath();
            ctx.ellipse(ecx, ecy, Math.max(erx, 1), Math.max(ery, 1), 0, 0, Math.PI * 2);
            if (d.fillColor) { ctx.fillStyle = d.fillColor; ctx.fill(); }
            ctx.stroke();
        }
    } else if (d.type === 'triangle') {
        // Triangle: 3-point
        if (p1 && p2) {
            var tp3 = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            if (tp3) { ctx.lineTo(tp3.x, tp3.y); }
            ctx.closePath();
            if (d.fillColor) { ctx.fillStyle = d.fillColor; ctx.fill(); }
            ctx.stroke();
        }
    } else if (d.type === 'rotated_rect') {
        // Rotated Rectangle: A→B defines one edge, C defines perpendicular width
        if (p1 && p2) {
            var rp3 = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
            if (rp3) {
                // Direction A→B
                var rdx = p2.x - p1.x, rdy = p2.y - p1.y;
                var rlen = Math.sqrt(rdx * rdx + rdy * rdy);
                if (rlen > 0) {
                    var rnx = -rdy / rlen, rny = rdx / rlen;
                    // Project C onto perpendicular to get width
                    var rprojW = (rp3.x - p1.x) * rnx + (rp3.y - p1.y) * rny;
                    ctx.beginPath();
                    ctx.moveTo(p1.x, p1.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.lineTo(p2.x + rnx * rprojW, p2.y + rny * rprojW);
                    ctx.lineTo(p1.x + rnx * rprojW, p1.y + rny * rprojW);
                    ctx.closePath();
                    if (d.fillColor) { ctx.fillStyle = d.fillColor; ctx.fill(); }
                    ctx.stroke();
                }
            } else {
                // Preview: just the A→B edge
                ctx.beginPath();
                ctx.moveTo(p1.x, p1.y);
                ctx.lineTo(p2.x, p2.y);
                ctx.stroke();
            }
        }
    } else if (d.type === 'path' || d.type === 'polyline') {
        // Path (closed) or Polyline (open) — multi-point
        var mpts = d.points;
        if (mpts && mpts.length > 1) {
            ctx.beginPath();
            var mp0 = _tvToPixel(chartId, mpts[0].t, mpts[0].p);
            if (mp0) {
                ctx.moveTo(mp0.x, mp0.y);
                for (var mi = 1; mi < mpts.length; mi++) {
                    var mpi = _tvToPixel(chartId, mpts[mi].t, mpts[mi].p);
                    if (mpi) ctx.lineTo(mpi.x, mpi.y);
                }
                if (d.type === 'path') ctx.closePath();
                if (d.fillColor && d.type === 'path') { ctx.fillStyle = d.fillColor; ctx.fill(); }
                ctx.stroke();
            }
        }
    } else if (d.type === 'shape_arc') {
        // Arc: 3-point (start, end, control for curvature)
        if (p1 && p2) {
            var sap3 = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            if (sap3) {
                ctx.quadraticCurveTo(sap3.x, sap3.y, p2.x, p2.y);
            } else {
                ctx.lineTo(p2.x, p2.y);
            }
            ctx.stroke();
        }
    } else if (d.type === 'curve') {
        // Curve: 2-point with auto control point (arc above midpoint)
        if (p1 && p2) {
            var ccx = (p1.x + p2.x) / 2, ccy = Math.min(p1.y, p2.y) - Math.abs(p2.x - p1.x) * 0.3;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.quadraticCurveTo(ccx, ccy, p2.x, p2.y);
            ctx.stroke();
        }
    } else if (d.type === 'double_curve') {
        // Double Curve: 3-point S-curve (A→mid via C, mid→B via opposite)
        if (p1 && p2) {
            var dcp3 = d.t3 !== undefined ? _tvToPixel(chartId, d.t3, d.p3) : null;
            var dcMidX = (p1.x + p2.x) / 2, dcMidY = (p1.y + p2.y) / 2;
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            if (dcp3) {
                ctx.quadraticCurveTo(dcp3.x, dcp3.y, dcMidX, dcMidY);
                // Mirror control point for second half
                var dMirX = 2 * dcMidX - dcp3.x, dMirY = 2 * dcMidY - dcp3.y;
                ctx.quadraticCurveTo(dMirX, dMirY, p2.x, p2.y);
            } else {
                ctx.lineTo(p2.x, p2.y);
            }
            ctx.stroke();
        }
    } else if (d.type === 'long_position' || d.type === 'short_position') {
        // Long/Short Position: entry line, target (profit) and stop-loss zones
        if (p1 && p2) {
            var isLong = d.type === 'long_position';
            var entryY = p1.y, targetY = p2.y;
            var leftX = Math.min(p1.x, p2.x), rightX = Math.max(p1.x, p2.x);
            if (rightX - leftX < 20) rightX = leftX + 150;
            // Determine stop: mirror of target across entry
            var stopY = entryY + (entryY - targetY);
            // Profit zone (green)
            var profTop = Math.min(entryY, targetY), profBot = Math.max(entryY, targetY);
            ctx.fillStyle = isLong ? 'rgba(38,166,91,0.25)' : 'rgba(239,83,80,0.25)';
            ctx.fillRect(leftX, profTop, rightX - leftX, profBot - profTop);
            // Stop zone (red)
            var stopTop = Math.min(entryY, stopY), stopBot = Math.max(entryY, stopY);
            ctx.fillStyle = isLong ? 'rgba(239,83,80,0.25)' : 'rgba(38,166,91,0.25)';
            ctx.fillRect(leftX, stopTop, rightX - leftX, stopBot - stopTop);
            // Entry line
            ctx.setLineDash([]);
            ctx.beginPath();
            ctx.moveTo(leftX, entryY); ctx.lineTo(rightX, entryY);
            ctx.stroke();
            // Target and stop lines (dashed)
            ctx.setLineDash([4, 3]);
            ctx.beginPath();
            ctx.moveTo(leftX, targetY); ctx.lineTo(rightX, targetY);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(leftX, stopY); ctx.lineTo(rightX, stopY);
            ctx.stroke();
            ctx.setLineDash([]);
            // Labels
            ctx.fillStyle = col;
            ctx.font = '11px sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(isLong ? 'Target' : 'Stop', leftX + 4, targetY - 4);
            ctx.fillText('Entry', leftX + 4, entryY - 4);
            ctx.fillText(isLong ? 'Stop' : 'Target', leftX + 4, stopY - 4);
        }
    } else if (d.type === 'forecast') {
        // Forecast: solid line for history, dashed fan lines for projection
        if (p1 && p2) {
            // Solid history segment
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
            // Dashed projection lines — fan of 3 paths
            var fdx = p2.x - p1.x, fdy = p2.y - p1.y;
            ctx.setLineDash([6, 4]);
            var fAngles = [-0.3, 0, 0.3];
            for (var fi = 0; fi < fAngles.length; fi++) {
                var fAngle = Math.atan2(fdy, fdx) + fAngles[fi];
                var fLen = Math.sqrt(fdx * fdx + fdy * fdy);
                ctx.beginPath();
                ctx.moveTo(p2.x, p2.y);
                ctx.lineTo(p2.x + fLen * Math.cos(fAngle), p2.y + fLen * Math.sin(fAngle));
                ctx.stroke();
            }
            ctx.setLineDash([]);
        }
    } else if (d.type === 'bars_pattern') {
        // Bars Pattern: source region box with dashed projected copy
        if (p1 && p2) {
            var bpW = Math.abs(p2.x - p1.x), bpH = Math.abs(p2.y - p1.y);
            var bpL = Math.min(p1.x, p2.x), bpT = Math.min(p1.y, p2.y);
            ctx.strokeRect(bpL, bpT, bpW, bpH);
            ctx.setLineDash([4, 3]);
            ctx.strokeRect(bpL + bpW, bpT, bpW, bpH);
            ctx.setLineDash([]);
        }
    } else if (d.type === 'ghost_feed') {
        // Ghost Feed: solid source segment, dashed continuation
        if (p1 && p2) {
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
            var gfdx = p2.x - p1.x, gfdy = p2.y - p1.y;
            ctx.setLineDash([5, 4]);
            ctx.globalAlpha = 0.5;
            ctx.beginPath();
            ctx.moveTo(p2.x, p2.y); ctx.lineTo(p2.x + gfdx, p2.y + gfdy);
            ctx.stroke();
            ctx.globalAlpha = 1.0;
            ctx.setLineDash([]);
        }
    } else if (d.type === 'projection') {
        // Projection: source box with dashed projected box
        if (p1 && p2) {
            var prjW = Math.abs(p2.x - p1.x), prjH = Math.abs(p2.y - p1.y);
            var prjL = Math.min(p1.x, p2.x), prjT = Math.min(p1.y, p2.y);
            ctx.setLineDash([]);
            ctx.strokeRect(prjL, prjT, prjW, prjH);
            ctx.setLineDash([4, 3]);
            ctx.strokeRect(prjL + prjW + 4, prjT, prjW, prjH);
            ctx.setLineDash([]);
            // Connecting arrow
            ctx.beginPath();
            ctx.moveTo(prjL + prjW, prjT + prjH / 2);
            ctx.lineTo(prjL + prjW + 4, prjT + prjH / 2);
            ctx.stroke();
        }
    } else if (d.type === 'anchored_vwap') {
        // Anchored VWAP: vertical anchor line + horizontal price label
        if (p1) {
            var avH = ctx.canvas.height;
            ctx.setLineDash([4, 3]);
            ctx.beginPath();
            ctx.moveTo(p1.x, 0); ctx.lineTo(p1.x, avH);
            ctx.stroke();
            ctx.setLineDash([]);
            // Label
            ctx.fillStyle = col;
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('VWAP', p1.x, 14);
        }
    } else if (d.type === 'fixed_range_vol') {
        // Fixed Range Volume Profile: vertical range with histogram placeholder
        if (p1 && p2) {
            var frL = Math.min(p1.x, p2.x), frR = Math.max(p1.x, p2.x);
            var frT = Math.min(p1.y, p2.y), frB = Math.max(p1.y, p2.y);
            ctx.setLineDash([4, 3]);
            ctx.beginPath();
            ctx.moveTo(frL, frT); ctx.lineTo(frL, frB);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(frR, frT); ctx.lineTo(frR, frB);
            ctx.stroke();
            ctx.setLineDash([]);
            // Horizontal bars placeholder
            ctx.fillStyle = 'rgba(41,98,255,0.2)';
            var frRows = 6, frRH = (frB - frT) / frRows;
            for (var fri = 0; fri < frRows; fri++) {
                var frW = (frR - frL) * (0.3 + Math.random() * 0.6);
                ctx.fillRect(frL, frT + fri * frRH + 1, frW, frRH - 2);
            }
        }
    } else if (d.type === 'price_range') {
        // Price Range: two horizontal lines with vertical connector and price diff label
        if (p1 && p2) {
            var prW = ctx.canvas.width;
            ctx.setLineDash([4, 3]);
            ctx.beginPath();
            ctx.moveTo(0, p1.y); ctx.lineTo(prW, p1.y);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(0, p2.y); ctx.lineTo(prW, p2.y);
            ctx.stroke();
            ctx.setLineDash([]);
            // Vertical connector
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y); ctx.lineTo(p1.x, p2.y);
            ctx.stroke();
            // Price diff label
            var prDiff = d.p2 !== undefined ? Math.abs(d.p2 - d.p1).toFixed(2) : '';
            ctx.fillStyle = col;
            ctx.font = '11px sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(prDiff, p1.x + 6, (p1.y + p2.y) / 2 + 4);
        }
    } else if (d.type === 'date_range') {
        // Date Range: two vertical lines with horizontal connector
        if (p1 && p2) {
            var drH = ctx.canvas.height;
            ctx.setLineDash([4, 3]);
            ctx.beginPath();
            ctx.moveTo(p1.x, 0); ctx.lineTo(p1.x, drH);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(p2.x, 0); ctx.lineTo(p2.x, drH);
            ctx.stroke();
            ctx.setLineDash([]);
            // Horizontal connector at midY
            var drMidY = drH / 2;
            ctx.beginPath();
            ctx.moveTo(p1.x, drMidY); ctx.lineTo(p2.x, drMidY);
            ctx.stroke();
            // Arrow heads
            var drDir = p2.x > p1.x ? 1 : -1;
            ctx.beginPath();
            ctx.moveTo(p2.x, drMidY);
            ctx.lineTo(p2.x - drDir * 8, drMidY - 4);
            ctx.moveTo(p2.x, drMidY);
            ctx.lineTo(p2.x - drDir * 8, drMidY + 4);
            ctx.stroke();
        }
    } else if (d.type === 'date_price_range') {
        // Date and Price Range: rectangle region with dimension labels
        if (p1 && p2) {
            var dpLeft = Math.min(p1.x, p2.x), dpRight = Math.max(p1.x, p2.x);
            var dpTop = Math.min(p1.y, p2.y), dpBot = Math.max(p1.y, p2.y);
            ctx.fillStyle = 'rgba(41,98,255,0.1)';
            ctx.fillRect(dpLeft, dpTop, dpRight - dpLeft, dpBot - dpTop);
            ctx.strokeRect(dpLeft, dpTop, dpRight - dpLeft, dpBot - dpTop);
            // Price diff label
            var dpDiff = d.p2 !== undefined ? Math.abs(d.p2 - d.p1).toFixed(2) : '';
            ctx.fillStyle = col;
            ctx.font = '11px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(dpDiff, (dpLeft + dpRight) / 2, dpTop - 6);
        }
    }

    // Draw selection handles
    if (selected) {
        var anchors = _tvDrawAnchors(chartId, d);
        for (var ai = 0; ai < anchors.length; ai++) {
            var anc = anchors[ai];
            ctx.fillStyle = _cssVar('--pywry-draw-handle-fill');
            ctx.strokeStyle = col;
            ctx.lineWidth = 2;
            ctx.setLineDash([]);
            ctx.beginPath();
            ctx.arc(anc.x, anc.y, 5, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
        }
    }

    ctx.restore();
}

// Rounded rect helper
function _roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
}

// ---- Floating edit toolbar ----
var _floatingToolbar = null;   // current DOM element
var _floatingChartId = null;
var _colorPickerEl = null;
var _widthPickerEl = null;

function _tvShowFloatingToolbar(chartId, drawIdx) {
    _tvHideFloatingToolbar();
    _tvHideContextMenu();
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds || drawIdx < 0 || drawIdx >= ds.drawings.length) return;
    var d = ds.drawings[drawIdx];

    var bar = document.createElement('div');
    bar.className = 'pywry-draw-toolbar';
    _floatingToolbar = bar;
    _floatingChartId = chartId;

    // Determine which controls are relevant for this drawing type
    var _arrowMarkers = ['arrow_marker', 'arrow_mark_up', 'arrow_mark_down', 'arrow_mark_left', 'arrow_mark_right'];
    var _hoverTextMarkers = ['pin', 'flag_mark', 'signpost'];
    var _filledMarkers = ['arrow_marker', 'arrow_mark_up', 'arrow_mark_down', 'arrow_mark_left', 'arrow_mark_right', 'anchored_text', 'note', 'price_note', 'pin', 'callout', 'comment', 'price_label', 'signpost', 'flag_mark'];
    var isArrowMarker = _arrowMarkers.indexOf(d.type) !== -1;
    var isHoverTextMarker = _hoverTextMarkers.indexOf(d.type) !== -1;
    var isFilledMarker = _filledMarkers.indexOf(d.type) !== -1;
    var hasLineStyle = d.type !== 'text' && d.type !== 'brush' && d.type !== 'measure' && !isFilledMarker;
    var hasLineWidth = d.type !== 'text' && !isFilledMarker;
    var hasColorSwatch = d.type !== 'measure' && !isArrowMarker && !isHoverTextMarker;

    // Arrow markers: fill / border / text icon buttons with color indicators
    if (isArrowMarker) {
        var fillBtn = _dtColorBtn(_DT_ICONS.bucket, 'Fill color',
            d.fillColor || d.color || _drawDefaults.color, function(e) {
            _tvToggleColorPicker(chartId, drawIdx, fillBtn._indicator, 'fillColor');
        });
        bar.appendChild(fillBtn);

        var borderBtn = _dtColorBtn(_DT_ICONS.border, 'Border color',
            d.borderColor || d.color || _drawDefaults.color, function(e) {
            _tvToggleColorPicker(chartId, drawIdx, borderBtn._indicator, 'borderColor');
        });
        bar.appendChild(borderBtn);

        var textBtn = _dtColorBtn(_DT_ICONS.text, 'Text color',
            d.textColor || d.color || _drawDefaults.color, function(e) {
            _tvToggleColorPicker(chartId, drawIdx, textBtn._indicator, 'textColor');
        });
        bar.appendChild(textBtn);
        bar.appendChild(_dtSep());
    }

    // Pin / Flag / Signpost: pencil + color indicator, T, font size, settings, lock, trash, more
    if (isHoverTextMarker) {
        var htColorBtn = _dtColorBtn(_DT_ICONS.pencil, 'Color',
            d.markerColor || d.color || _drawDefaults.color, function(e) {
            _tvToggleColorPicker(chartId, drawIdx, htColorBtn._indicator, 'markerColor');
        });
        bar.appendChild(htColorBtn);

        var htTextBtn = _dtColorBtn(_DT_ICONS.text, 'Text',
            d.color || _drawDefaults.color, function(e) {
            _tvToggleColorPicker(chartId, drawIdx, htTextBtn._indicator, 'color');
        });
        bar.appendChild(htTextBtn);

        var htFsLabel = document.createElement('span');
        htFsLabel.className = 'dt-label';
        htFsLabel.textContent = d.fontSize || 14;
        htFsLabel.title = 'Font size';
        htFsLabel.addEventListener('click', function(e) {
            e.stopPropagation();
            _tvShowDrawingSettings(chartId, drawIdx);
        });
        bar.appendChild(htFsLabel);
        bar.appendChild(_dtSep());
    }

    // Color swatch (non-arrow-marker tools)
    if (hasColorSwatch) {
        var swatch = document.createElement('div');
        swatch.className = 'dt-swatch';
        swatch.style.background = d.color || _drawDefaults.color;
        swatch.title = 'Color';
        swatch.addEventListener('click', function(e) {
            e.stopPropagation();
            _tvToggleColorPicker(chartId, drawIdx, swatch);
        });
        bar.appendChild(swatch);
        bar.appendChild(_dtSep());
    }

    // Line width button
    if (hasLineWidth) {
        var lwBtn = _dtBtn(_DT_ICONS.lineW, 'Line width', function(e) {
            e.stopPropagation();
            _tvToggleWidthPicker(chartId, drawIdx, lwBtn);
        });
        var lwLabel = document.createElement('span');
        lwLabel.className = 'dt-label';
        lwLabel.textContent = (d.lineWidth || 2) + 'px';
        lwLabel.title = 'Line width';
        lwLabel.addEventListener('click', function(e) {
            e.stopPropagation();
            _tvToggleWidthPicker(chartId, drawIdx, lwBtn);
        });
        bar.appendChild(lwBtn);
        bar.appendChild(lwLabel);
        bar.appendChild(_dtSep());
    }

    // Line style cycle (solid → dashed → dotted)
    if (hasLineStyle) {
        var styleBtn = _dtBtn(_DT_ICONS.pencil, 'Line style', function() {
            d.lineStyle = ((d.lineStyle || 0) + 1) % 3;
            _tvRenderDrawings(chartId);
        });
        bar.appendChild(styleBtn);
        bar.appendChild(_dtSep());
    }

    // Lock toggle
    var lockBtn = _dtBtn(d.locked ? _DT_ICONS.lock : _DT_ICONS.unlock,
        d.locked ? 'Unlock' : 'Lock', function() {
        d.locked = !d.locked;
        lockBtn.innerHTML = d.locked ? _DT_ICONS.lock : _DT_ICONS.unlock;
        lockBtn.title = d.locked ? 'Unlock' : 'Lock';
        if (d.locked) lockBtn.classList.add('active');
        else lockBtn.classList.remove('active');
    });
    if (d.locked) lockBtn.classList.add('active');
    bar.appendChild(lockBtn);

    bar.appendChild(_dtSep());

    // Settings button — opens drawing settings panel for any type
    var settingsBtn = _dtBtn(_DT_ICONS.settings, 'Settings', function() {
        _tvShowDrawingSettings(chartId, drawIdx);
    });
    bar.appendChild(settingsBtn);
    bar.appendChild(_dtSep());

    // Delete
    var delBtn = _dtBtn(_DT_ICONS.trash, 'Delete', function() {
        _tvDeleteDrawing(chartId, drawIdx);
    });
    delBtn.style.color = _cssVar('--pywry-draw-danger', '#f44336');
    bar.appendChild(delBtn);

    bar.appendChild(_dtSep());

    // More (...)
    var moreBtn = _dtBtn(_DT_ICONS.more, 'More', function(e) {
        e.stopPropagation();
        // Show context menu near toolbar
        var rect = bar.getBoundingClientRect();
        var cRect = ds.canvas.getBoundingClientRect();
        _tvShowContextMenu(chartId, drawIdx,
            rect.right - cRect.left, rect.bottom - cRect.top + 4);
    });
    bar.appendChild(moreBtn);

    ds.uiLayer.appendChild(bar);
    _tvRepositionToolbar(chartId);
}

function _tvRepositionToolbar(chartId) {
    if (!_floatingToolbar || _floatingChartId !== chartId) return;
    if (_drawSelectedIdx < 0) { _tvHideFloatingToolbar(); return; }
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds || _drawSelectedIdx >= ds.drawings.length) { _tvHideFloatingToolbar(); return; }
    var d = ds.drawings[_drawSelectedIdx];
    var anchors = _tvDrawAnchors(chartId, d);
    if (anchors.length === 0) { _tvHideFloatingToolbar(); return; }

    // Position above the topmost anchor
    var minY = Infinity, midX = 0;
    for (var i = 0; i < anchors.length; i++) {
        if (anchors[i].y < minY) minY = anchors[i].y;
        midX += anchors[i].x;
    }
    midX /= anchors.length;

    var tbW = _floatingToolbar.offsetWidth || 300;
    var left = midX - tbW / 2;
    var top  = minY - 44;
    // Clamp to container
    var cw = ds.canvas.clientWidth;
    if (left < 4) left = 4;
    if (left + tbW > cw - 4) left = cw - tbW - 4;
    if (top < 4) top = 4;

    _floatingToolbar.style.left = left + 'px';
    _floatingToolbar.style.top  = top  + 'px';
}

function _tvHideFloatingToolbar() {
    if (_floatingToolbar && _floatingToolbar.parentNode) {
        _floatingToolbar.parentNode.removeChild(_floatingToolbar);
    }
    _floatingToolbar = null;
    _floatingChartId = null;
    _tvHideColorPicker();
    _tvHideWidthPicker();
}

function _dtBtn(svgHtml, title, onclick) {
    var btn = document.createElement('button');
    btn.innerHTML = svgHtml;
    btn.title = title;
    btn.addEventListener('click', function(e) { e.stopPropagation(); onclick(e); });
    return btn;
}

/**
 * Create a toolbar button with an icon and a color indicator bar beneath it.
 * Used for fill / border / text color controls on filled marker drawings.
 */
function _dtColorBtn(svgHtml, title, color, onclick) {
    var btn = document.createElement('button');
    btn.className = 'dt-color-btn';
    btn.title = title;
    btn.innerHTML = svgHtml;
    var indicator = document.createElement('span');
    indicator.className = 'dt-color-indicator';
    indicator.style.background = color;
    btn.appendChild(indicator);
    btn.addEventListener('click', function(e) { e.stopPropagation(); onclick(e); });
    btn._indicator = indicator;
    return btn;
}

function _dtSep() {
    var s = document.createElement('div');
    s.className = 'dt-sep';
    return s;
}

// ---- HSV / RGB conversion helpers ----
function _hsvToRgb(h, s, v) {
    var i = Math.floor(h * 6), f = h * 6 - i, p = v * (1 - s);
    var q = v * (1 - f * s), t = v * (1 - (1 - f) * s);
    var r, g, b;
    switch (i % 6) {
        case 0: r = v; g = t; b = p; break;
        case 1: r = q; g = v; b = p; break;
        case 2: r = p; g = v; b = t; break;
        case 3: r = p; g = q; b = v; break;
        case 4: r = t; g = p; b = v; break;
        case 5: r = v; g = p; b = q; break;
    }
    return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)];
}

function _rgbToHsv(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    var max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
    var h = 0, s = max === 0 ? 0 : d / max, v = max;
    if (d !== 0) {
        switch (max) {
            case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
            case g: h = ((b - r) / d + 2) / 6; break;
            case b: h = ((r - g) / d + 4) / 6; break;
        }
    }
    return [h, s, v];
}

function _hexToRgb(hex) {
    hex = hex.replace(/^#/, '');
    if (hex.length === 3) hex = hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2];
    var n = parseInt(hex, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function _rgbToHex(r, g, b) {
    return '#' + ((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1);
}

// ---- Canvas paint helpers for color picker ----
function _cpPaintSV(canvas, hue) {
    var w = canvas.width, h = canvas.height;
    var ctx = canvas.getContext('2d');
    var hRgb = _hsvToRgb(hue, 1, 1);
    var hHex = _rgbToHex(hRgb[0], hRgb[1], hRgb[2]);
    ctx.fillStyle = _cssVar('--pywry-cp-sv-white', '#ffffff');
    ctx.fillRect(0, 0, w, h);
    var gH = ctx.createLinearGradient(0, 0, w, 0);
    gH.addColorStop(0, _cssVar('--pywry-cp-sv-white', '#ffffff'));
    gH.addColorStop(1, hHex);
    ctx.fillStyle = gH;
    ctx.fillRect(0, 0, w, h);
    var gV = ctx.createLinearGradient(0, 0, 0, h);
    var svBlack = _cssVar('--pywry-cp-sv-black', '#000000');
    var svRgb = _hexToRgb(svBlack);
    gV.addColorStop(0, 'rgba(' + svRgb[0] + ',' + svRgb[1] + ',' + svRgb[2] + ',0)');
    gV.addColorStop(1, svBlack);
    ctx.fillStyle = gV;
    ctx.fillRect(0, 0, w, h);
}

function _cpPaintHue(canvas) {
    var w = canvas.width, h = canvas.height;
    var ctx = canvas.getContext('2d');
    var g = ctx.createLinearGradient(0, 0, w, 0);
    g.addColorStop(0,     _cssVar('--pywry-cp-hue-0', '#ff0000'));
    g.addColorStop(0.167, _cssVar('--pywry-cp-hue-1', '#ffff00'));
    g.addColorStop(0.333, _cssVar('--pywry-cp-hue-2', '#00ff00'));
    g.addColorStop(0.5,   _cssVar('--pywry-cp-hue-3', '#00ffff'));
    g.addColorStop(0.667, _cssVar('--pywry-cp-hue-4', '#0000ff'));
    g.addColorStop(0.833, _cssVar('--pywry-cp-hue-5', '#ff00ff'));
    g.addColorStop(1,     _cssVar('--pywry-cp-hue-6', '#ff0000'));
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
}

// ---- Full color picker popup (canvas-based, all inline styles) ----
function _tvToggleColorPicker(chartId, drawIdx, anchor, propName) {
    _tvHideWidthPicker();
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds) return;
    var d = ds.drawings[drawIdx];
    var _cpProp = propName || 'color';
    var curHex = _tvColorToHex(d[_cpProp] || d.color || _drawDefaults.color, _drawDefaults.color);
    var curOpacity = _tvToNumber(d[_cpProp + 'Opacity'], _tvColorOpacityPercent(d[_cpProp], 100));

    _tvShowColorOpacityPopup(anchor, curHex, curOpacity, null, function(newColor, newOpacity) {
        d[_cpProp] = _tvColorWithOpacity(newColor, newOpacity, newColor);
        d[_cpProp + 'Opacity'] = newOpacity;
        anchor.style.background = _tvColorWithOpacity(newColor, newOpacity, newColor);
        if (d.type === 'hline') _tvSyncPriceLineColor(chartId, drawIdx, _tvColorWithOpacity(newColor, newOpacity, newColor));
        _tvRenderDrawings(chartId);
    });
}

function _tvHideColorPicker() {
    if (_colorPickerEl && _colorPickerEl.parentNode) {
        _colorPickerEl.parentNode.removeChild(_colorPickerEl);
    }
    _colorPickerEl = null;
}

// ---- Width picker popup ----
function _tvToggleWidthPicker(chartId, drawIdx, anchor) {
    if (_widthPickerEl) { _tvHideWidthPicker(); return; }
    _tvHideColorPicker();
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds) return;
    var d = ds.drawings[drawIdx];
    var picker = document.createElement('div');
    picker.className = 'pywry-draw-width-picker';
    _widthPickerEl = picker;

    for (var i = 0; i < _DRAW_WIDTHS.length; i++) {
        (function(pw) {
            var row = document.createElement('div');
            row.className = 'wp-row' + ((d.lineWidth || 2) === pw ? ' sel' : '');
            var line = document.createElement('div');
            line.className = 'wp-line';
            line.style.borderTopWidth = pw + 'px';
            row.appendChild(line);
            var label = document.createElement('span');
            label.textContent = pw + 'px';
            row.appendChild(label);
            row.addEventListener('click', function(e) {
                e.stopPropagation();
                d.lineWidth = pw;
                _tvRenderDrawings(chartId);
                _tvHideWidthPicker();
                // Update label in toolbar
                var lbls = _floatingToolbar ? _floatingToolbar.querySelectorAll('.dt-label') : [];
                if (lbls.length > 0) lbls[0].textContent = pw + 'px';
            });
            picker.appendChild(row);
        })(_DRAW_WIDTHS[i]);
    }

    var _oc = _tvAppendOverlay(chartId, picker);

    // Position the picker relative to the anchor
    requestAnimationFrame(function() {
        var _cs = _tvContainerSize(_oc);
        var aRect = _tvContainerRect(_oc, anchor.getBoundingClientRect());
        var pH = picker.offsetHeight;
        var pW = picker.offsetWidth;
        var top = aRect.top - pH - 6;
        var left = aRect.left;
        if (top < 0) {
            top = aRect.bottom + 6;
        }
        if (left + pW > _cs.width - 4) {
            left = _cs.width - pW - 4;
        }
        if (left < 4) left = 4;
        picker.style.top = top + 'px';
        picker.style.left = left + 'px';
    });
}

function _tvHideWidthPicker() {
    if (_widthPickerEl && _widthPickerEl.parentNode) {
        _widthPickerEl.parentNode.removeChild(_widthPickerEl);
    }
    _widthPickerEl = null;
}

// ---- Context menu (right-click on drawing) ----
var _ctxMenuEl = null;

function _tvShowContextMenu(chartId, drawIdx, posX, posY) {
    _tvHideContextMenu();
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds || drawIdx < 0 || drawIdx >= ds.drawings.length) return;
    var d = ds.drawings[drawIdx];

    var menu = document.createElement('div');
    menu.className = 'pywry-draw-ctx-menu';
    _ctxMenuEl = menu;

    // Settings
    _cmItem(menu, _DT_ICONS.settings, 'Settings...', '', function() {
        _tvHideContextMenu();
        _tvShowDrawingSettings(chartId, drawIdx);
    });

    _cmSep(menu);

    // Clone
    _cmItem(menu, _DT_ICONS.clone, 'Clone', 'Ctrl+Drag', function() {
        var copy = Object.assign({}, d);
        copy._id = ++_drawIdCounter;
        ds.drawings.push(copy);
        _emitDrawingAdded(chartId, copy);
        _tvRenderDrawings(chartId);
        _tvHideContextMenu();
    });

    // Copy (as JSON to clipboard)
    _cmItem(menu, '', 'Copy', 'Ctrl+C', function() {
        try {
            navigator.clipboard.writeText(JSON.stringify(d));
        } catch(e) {}
        _tvHideContextMenu();
    });

    _cmSep(menu);

    // Hide / Show
    var isHidden = d.hidden;
    _cmItem(menu, isHidden ? _DT_ICONS.eye : _DT_ICONS.eyeOff,
        isHidden ? 'Show' : 'Hide', '', function() {
        d.hidden = !d.hidden;
        if (d.hidden) {
            _drawSelectedIdx = -1;
            _tvHideFloatingToolbar();
        }
        _tvRenderDrawings(chartId);
        _tvHideContextMenu();
    });

    _cmSep(menu);

    // Bring to front
    _cmItem(menu, '', 'Bring to Front', '', function() {
        var _undoChartId = chartId;
        var _undoFromIdx = drawIdx;
        _tvPushUndo({
            label: 'Bring to front',
            undo: function() {
                var ds2 = window.__PYWRY_DRAWINGS__[_undoChartId];
                if (!ds2 || ds2.drawings.length === 0) return;
                // Move last back to original index
                var item = ds2.drawings.pop();
                ds2.drawings.splice(_undoFromIdx, 0, item);
                _tvDeselectAll(_undoChartId);
            },
            redo: function() {
                var ds2 = window.__PYWRY_DRAWINGS__[_undoChartId];
                if (!ds2 || _undoFromIdx >= ds2.drawings.length) return;
                ds2.drawings.push(ds2.drawings.splice(_undoFromIdx, 1)[0]);
                _tvDeselectAll(_undoChartId);
            },
        });
        ds.drawings.push(ds.drawings.splice(drawIdx, 1)[0]);
        _drawSelectedIdx = ds.drawings.length - 1;
        _tvRenderDrawings(chartId);
        _tvHideContextMenu();
    });

    // Send to back
    _cmItem(menu, '', 'Send to Back', '', function() {
        ds.drawings.unshift(ds.drawings.splice(drawIdx, 1)[0]);
        _drawSelectedIdx = 0;
        _tvRenderDrawings(chartId);
        _tvHideContextMenu();
    });

    _cmSep(menu);

    // Delete
    _cmItem(menu, _DT_ICONS.trash, 'Delete', 'Del', function() {
        _tvDeleteDrawing(chartId, drawIdx);
        _tvHideContextMenu();
    }, true);

    menu.style.left = posX + 'px';
    menu.style.top  = posY + 'px';
    ds.uiLayer.appendChild(menu);

    // Clamp context menu within container
    requestAnimationFrame(function() {
        var mRect = menu.getBoundingClientRect();
        var uiRect = ds.uiLayer.getBoundingClientRect();
        if (mRect.right > uiRect.right) {
            menu.style.left = Math.max(0, posX - (mRect.right - uiRect.right)) + 'px';
        }
        if (mRect.bottom > uiRect.bottom) {
            menu.style.top = Math.max(0, posY - (mRect.bottom - uiRect.bottom)) + 'px';
        }
    });

    // Close on click outside
    setTimeout(function() {
        document.addEventListener('click', _ctxMenuOutsideClick, { once: true });
    }, 0);
}

function _ctxMenuOutsideClick() { _tvHideContextMenu(); }

function _tvHideContextMenu() {
    if (_ctxMenuEl && _ctxMenuEl.parentNode) {
        _ctxMenuEl.parentNode.removeChild(_ctxMenuEl);
    }
    _ctxMenuEl = null;
}

function _cmItem(menu, icon, label, shortcut, onclick, danger) {
    var row = document.createElement('div');
    row.className = 'cm-item' + (danger ? ' cm-danger' : '');
    
    // Icon container (always present for consistent spacing)
    var iconWrap = document.createElement('span');
    iconWrap.className = 'cm-icon';
    if (icon) iconWrap.innerHTML = icon;
    row.appendChild(iconWrap);
    
    // Label
    var lbl = document.createElement('span');
    lbl.className = 'cm-label';
    lbl.textContent = label;
    row.appendChild(lbl);
    
    // Shortcut
    if (shortcut) {
        var sc = document.createElement('span');
        sc.className = 'cm-shortcut';
        sc.textContent = shortcut;
        row.appendChild(sc);
    }
    
    row.addEventListener('click', function(e) { e.stopPropagation(); onclick(); });
    menu.appendChild(row);
}

function _cmSep(menu) {
    var s = document.createElement('div');
    s.className = 'cm-sep';
    menu.appendChild(s);
}

// ---- Delete drawing helper ----
function _tvDeleteDrawing(chartId, drawIdx) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds) return;
    var d = ds.drawings[drawIdx];
    if (!d) return;

    // Push undo entry before deleting
    var _undoChartId = chartId;
    var _undoDrawing = Object.assign({}, d);
    var _undoIdx = drawIdx;
    _tvPushUndo({
        label: 'Delete ' + (d.type || 'drawing'),
        undo: function() {
            var ds2 = window.__PYWRY_DRAWINGS__[_undoChartId];
            if (!ds2) return;
            var idx = Math.min(_undoIdx, ds2.drawings.length);
            ds2.drawings.splice(idx, 0, Object.assign({}, _undoDrawing));
            // Re-create native price line if hline
            if (_undoDrawing.type === 'hline') {
                var entry = window.__PYWRY_TVCHARTS__[_undoChartId];
                if (entry) {
                    var mainKey = Object.keys(entry.seriesMap)[0];
                    if (mainKey && entry.seriesMap[mainKey]) {
                        var pl = entry.seriesMap[mainKey].createPriceLine({
                            price: _undoDrawing.price, color: _undoDrawing.color,
                            lineWidth: _undoDrawing.lineWidth, lineStyle: _undoDrawing.lineStyle,
                            axisLabelVisible: true, title: '',
                        });
                        ds2.priceLines.splice(idx, 0, { seriesId: mainKey, priceLine: pl });
                    }
                }
            }
            _tvDeselectAll(_undoChartId);
        },
        redo: function() {
            var ds2 = window.__PYWRY_DRAWINGS__[_undoChartId];
            if (!ds2) return;
            for (var i = ds2.drawings.length - 1; i >= 0; i--) {
                if (ds2.drawings[i]._id === _undoDrawing._id) {
                    if (ds2.drawings[i].type === 'hline' && ds2.priceLines[i]) {
                        var entry = window.__PYWRY_TVCHARTS__[_undoChartId];
                        if (entry) {
                            var pl2 = ds2.priceLines[i];
                            var ser = entry.seriesMap[pl2.seriesId];
                            if (ser) try { ser.removePriceLine(pl2.priceLine); } catch(e) {}
                        }
                        ds2.priceLines.splice(i, 1);
                    }
                    ds2.drawings.splice(i, 1);
                    break;
                }
            }
            _tvDeselectAll(_undoChartId);
        },
    });

    // Remove native price line if hline
    if (d.type === 'hline' && ds.priceLines[drawIdx]) {
        var entry = window.__PYWRY_TVCHARTS__[chartId];
        if (entry) {
            var pl = ds.priceLines[drawIdx];
            var ser = entry.seriesMap[pl.seriesId];
            if (ser) try { ser.removePriceLine(pl.priceLine); } catch(e) {}
        }
        ds.priceLines.splice(drawIdx, 1);
    }
    ds.drawings.splice(drawIdx, 1);
    _drawSelectedIdx = -1;
    _drawSelectedChart = null;
    _tvHideFloatingToolbar();
    _tvRenderDrawings(chartId);
    if (window.pywry && window.pywry.emit) {
        window.pywry.emit('tvchart:drawing-deleted', { chartId: chartId, index: drawIdx });
    }
}

// ---- Sync native price line color for hlines ----
function _tvSyncPriceLineColor(chartId, drawIdx, color) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds || !ds.priceLines[drawIdx]) return;
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;
    var pl = ds.priceLines[drawIdx];
    var ser = entry.seriesMap[pl.seriesId];
    if (ser) {
        try { ser.removePriceLine(pl.priceLine); } catch(e) {}
        var drw = ds.drawings[drawIdx];
        var newPl = ser.createPriceLine({
            price: drw.price,
            color: color,
            lineWidth: drw.lineWidth || 2,
            lineStyle: drw.lineStyle || 0,
            axisLabelVisible: drw.showPriceLabel !== false,
            title: drw.title || '',
        });
        ds.priceLines[drawIdx] = { seriesId: pl.seriesId, priceLine: newPl };
    }
}

// ---- Mouse interaction engine ----
function _tvEnableDrawing(chartId) {
    var ds = _tvEnsureDrawingLayer(chartId);
    if (!ds || ds._eventsAttached) return;
    ds._eventsAttached = true;

    var canvas = ds.canvas;
    var entry  = window.__PYWRY_TVCHARTS__[chartId];
    if (!entry) return;
    var container = entry.container;

    // =========================================================================
    // Container-level listeners: work in CURSOR mode (canvas has ptr-events:none)
    // Events bubble up from the chart's own internal canvas through the container.
    // =========================================================================

    // --- Mouse move: hover highlight + drag (cursor mode) ---
    // Use CAPTURE phase so drag moves are intercepted before the chart.
    // NOTE: During drag, document-level handlers do the actual drag work.
    // This handler only blocks propagation during drag so the chart doesn't pan.
    container.addEventListener('mousemove', function(e) {
        // When a modal is open (interaction locked), never process hover/drag
        if (entry._interactionLocked) return;
        // During drag, the document-level handler processes movement.
        // Just block chart interaction here.
        if (_drawDragging && _drawSelectedChart === chartId) {
            e.preventDefault();
            e.stopPropagation();
            return;
        }

        // Hover detection (cursor mode only)
        if (ds._activeTool === 'cursor') {
            var rect = canvas.getBoundingClientRect();
            var mx = e.clientX - rect.left;
            var my = e.clientY - rect.top;
            var hitIdx = _tvHitTest(chartId, mx, my);
            if (hitIdx !== _drawHoverIdx) {
                _drawHoverIdx = hitIdx;
                _tvRenderDrawings(chartId);
            }
            // Cursor style feedback
            if (_drawSelectedIdx >= 0 && _drawSelectedChart === chartId) {
                var selD = ds.drawings[_drawSelectedIdx];
                if (selD) {
                    var ancs = _tvDrawAnchors(chartId, selD);
                    for (var ai = 0; ai < ancs.length; ai++) {
                        var dx = mx - ancs[ai].x, dy = my - ancs[ai].y;
                        if (dx * dx + dy * dy < 64) {
                            container.style.cursor = 'grab';
                            return;
                        }
                    }
                }
            }
            container.style.cursor = hitIdx >= 0 ? 'pointer' : '';
        }
    }, true);  // capture phase

    // --- Document-level drag handler (bound during startDrag, unbound in endDrag) ---
    // Using document-level ensures drag continues even when mouse leaves the container.
    var _boundDocDragMove = null;
    var _boundDocDragEnd  = null;

    function docDragMove(e) {
        if (!_drawDragging || _drawSelectedChart !== chartId) return;
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;
        e.preventDefault();

        var dd = ds.drawings[_drawSelectedIdx];
        if (!dd || dd.locked) { _tvRenderDrawings(chartId); return; }

        var series = _tvMainSeries(chartId);
        var ak = _drawDragging.anchor;

        if (ak === 'body') {
            // Pixel-based translation from drag start.
            // Use total pixel offset applied to the ORIGINAL anchor positions
            // to avoid accumulated time-rounding drift.
            var totalDx = mx - _drawDragging.startX;
            var totalDy = my - _drawDragging.startY;

            if (dd.type === 'hline') {
                if (_drawDragging._origPriceY !== null && series) {
                    var newP = series.coordinateToPrice(_drawDragging._origPriceY + totalDy);
                    if (newP !== null) dd.price = newP;
                }
            } else if (dd.type === 'vline') {
                if (_drawDragging._origPx1) {
                    var vNewC = _tvFromPixel(chartId, _drawDragging._origPx1.x + totalDx, 0);
                    if (vNewC && vNewC.time !== null) dd.t1 = vNewC.time;
                }
            } else if (dd.type === 'flat_channel') {
                if (_drawDragging._origPriceY !== null && _drawDragging._origPrice2Y !== null && series) {
                    var fcP1 = series.coordinateToPrice(_drawDragging._origPriceY + totalDy);
                    var fcP2 = series.coordinateToPrice(_drawDragging._origPrice2Y + totalDy);
                    if (fcP1 !== null && fcP2 !== null) { dd.p1 = fcP1; dd.p2 = fcP2; }
                }
            } else if ((dd.type === 'brush' || dd.type === 'highlighter' || dd.type === 'path' || dd.type === 'polyline') && dd.points && _drawDragging._origBrushPx) {
                var obp = _drawDragging._origBrushPx;
                var allOk = true;
                var newPts = [];
                for (var bdi = 0; bdi < obp.length; bdi++) {
                    if (!obp[bdi]) { allOk = false; break; }
                    var bNewC = _tvFromPixel(chartId, obp[bdi].x + totalDx, obp[bdi].y + totalDy);
                    if (!bNewC || bNewC.time === null || bNewC.price === null) { allOk = false; break; }
                    newPts.push({ t: bNewC.time, p: bNewC.price });
                }
                if (allOk) dd.points = newPts;
            } else {
                // Two-point (or three-point) tools: translate all anchors in pixel space
                if (_drawDragging._origPx1 && _drawDragging._origPx2) {
                    var newC1 = _tvFromPixel(chartId, _drawDragging._origPx1.x + totalDx, _drawDragging._origPx1.y + totalDy);
                    var newC2 = _tvFromPixel(chartId, _drawDragging._origPx2.x + totalDx, _drawDragging._origPx2.y + totalDy);
                    if (newC1 && newC1.time !== null && newC1.price !== null &&
                        newC2 && newC2.time !== null && newC2.price !== null) {
                        dd.t1 = newC1.time; dd.p1 = newC1.price;
                        dd.t2 = newC2.time; dd.p2 = newC2.price;
                    }
                    // Also translate third anchor if present
                    if (_drawDragging._origPx3) {
                        var newC3 = _tvFromPixel(chartId, _drawDragging._origPx3.x + totalDx, _drawDragging._origPx3.y + totalDy);
                        if (newC3 && newC3.time !== null && newC3.price !== null) {
                            dd.t3 = newC3.time; dd.p3 = newC3.price;
                        }
                    }
                }
            }
        } else {
            // Anchor drag: set the anchor directly from mouse position
            var coord = _tvFromPixel(chartId, mx, my);
            if (!coord || coord.time === null || coord.price === null) {
                _tvRenderDrawings(chartId);
                return;
            }
            if (ak === 'p1') { dd.t1 = coord.time; dd.p1 = coord.price; }
            else if (ak === 'p2') { dd.t2 = coord.time; dd.p2 = coord.price; }
            else if (ak === 'p3') { dd.t3 = coord.time; dd.p3 = coord.price; }
            else if (ak === 'price') { dd.price = coord.price; }
            else if (ak.indexOf('pt') === 0 && dd.points) {
                // Path/polyline vertex drag
                var ptIdx = parseInt(ak.substring(2));
                if (!isNaN(ptIdx) && ptIdx >= 0 && ptIdx < dd.points.length) {
                    dd.points[ptIdx] = { t: coord.time, p: coord.price };
                }
            }
        }

        _tvRenderDrawings(chartId);
        _tvRepositionToolbar(chartId);
    }

    // --- Mouse down: begin drag (select + drag in one motion, cursor mode) ---
    // Use CAPTURE phase so we fire before the chart and can block its panning.
    container.addEventListener('mousedown', function(e) {
        if (e.button !== 0) return;
        // When a modal is open (interaction locked), never start drawing drag
        if (entry._interactionLocked) return;
        if (ds._activeTool !== 'cursor') return;
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;

        // Helper: start dragging and block chart panning
        function startDrag(anchor, mx2, my2) {
            var dd = ds.drawings[_drawSelectedIdx];
            var series = _tvMainSeries(chartId);
            _drawDragging = {
                anchor: anchor, startX: mx2, startY: my2,
                // Store original anchor pixel positions at drag start
                _origPx1: null, _origPx2: null, _origPx3: null,
                _origPriceY: null, _origPrice2Y: null,
                _origBrushPx: null,
            };
            // Snapshot pixel positions for body drag
            if (anchor === 'body' && dd) {
                if (dd.type === 'hline' && series) {
                    _drawDragging._origPriceY = series.priceToCoordinate(dd.price);
                } else if (dd.type === 'vline') {
                    _drawDragging._origPx1 = _tvToPixel(chartId, dd.t1, 0);
                } else if (dd.type === 'flat_channel' && series) {
                    _drawDragging._origPriceY = series.priceToCoordinate(dd.p1);
                    _drawDragging._origPrice2Y = series.priceToCoordinate(dd.p2);
                } else if ((dd.type === 'brush' || dd.type === 'highlighter' || dd.type === 'path' || dd.type === 'polyline') && dd.points) {
                    _drawDragging._origBrushPx = [];
                    for (var bi = 0; bi < dd.points.length; bi++) {
                        _drawDragging._origBrushPx.push(
                            _tvToPixel(chartId, dd.points[bi].t, dd.points[bi].p)
                        );
                    }
                } else {
                    _drawDragging._origPx1 = dd.t1 !== undefined ? _tvToPixel(chartId, dd.t1, dd.p1) : null;
                    _drawDragging._origPx2 = dd.t2 !== undefined ? _tvToPixel(chartId, dd.t2, dd.p2) : null;
                    _drawDragging._origPx3 = dd.t3 !== undefined ? _tvToPixel(chartId, dd.t3, dd.p3) : null;
                }
            }
            // Block chart panning by making the overlay intercept events
            canvas.style.pointerEvents = 'auto';
            // Freeze chart interaction so crosshair/legend/axes don't move
            entry.chart.applyOptions({ handleScroll: false, handleScale: false });
            entry.chart.clearCrosshairPosition();
            container.style.cursor = anchor === 'body' ? 'move' : 'grabbing';
            // Bind document-level handlers so drag works even outside the container
            _boundDocDragMove = docDragMove;
            _boundDocDragEnd  = docDragEnd;
            document.addEventListener('mousemove', _boundDocDragMove, true);
            document.addEventListener('mouseup', _boundDocDragEnd, true);
            e.preventDefault();
            e.stopPropagation();
        }

        // If a drawing is already selected, try its anchors first
        if (_drawSelectedIdx >= 0 && _drawSelectedChart === chartId) {
            var selD = ds.drawings[_drawSelectedIdx];
            if (selD && !selD.locked) {
                var ancs = _tvDrawAnchors(chartId, selD);
                for (var ai = 0; ai < ancs.length; ai++) {
                    var adx = mx - ancs[ai].x, ady = my - ancs[ai].y;
                    if (adx * adx + ady * ady < 64) {
                        startDrag(ancs[ai].key, mx, my);
                        return;
                    }
                }
                if (_tvDrawHit(chartId, selD, mx, my, 8)) {
                    startDrag('body', mx, my);
                    return;
                }
            }
        }

        // Not on the selected drawing — hit-test all drawings to select + drag
        var hitIdx = _tvHitTest(chartId, mx, my);
        if (hitIdx >= 0) {
            var hitD = ds.drawings[hitIdx];
            if (hitD && !hitD.locked) {
                _drawSelectedIdx = hitIdx;
                _drawSelectedChart = chartId;
                _tvRenderDrawings(chartId);
                _tvShowFloatingToolbar(chartId, hitIdx);
                // Check anchors of new selection
                var hitAncs = _tvDrawAnchors(chartId, hitD);
                for (var hai = 0; hai < hitAncs.length; hai++) {
                    var hdx = mx - hitAncs[hai].x, hdy = my - hitAncs[hai].y;
                    if (hdx * hdx + hdy * hdy < 64) {
                        startDrag(hitAncs[hai].key, mx, my);
                        return;
                    }
                }
                startDrag('body', mx, my);
            }
        }
    }, true);  // capture phase

    // --- Mouse up: end drag ---
    function docDragEnd() {
        if (_drawDragging) {
            _drawDidDrag = true;
            _drawDragging = null;
            // Remove document-level handlers
            if (_boundDocDragMove) document.removeEventListener('mousemove', _boundDocDragMove, true);
            if (_boundDocDragEnd) document.removeEventListener('mouseup', _boundDocDragEnd, true);
            _boundDocDragMove = null;
            _boundDocDragEnd  = null;
            // Restore pointer-events so chart can pan/zoom again
            _tvApplyDrawingInteractionMode(ds);
            // Restore chart interaction
            entry.chart.applyOptions({ handleScroll: true, handleScale: true });
            container.style.cursor = '';
            _tvRenderDrawings(chartId);
            _tvRepositionToolbar(chartId);
            // Sync native price line if hline was dragged
            if (_drawSelectedIdx >= 0 && ds.drawings[_drawSelectedIdx] &&
                ds.drawings[_drawSelectedIdx].type === 'hline') {
                _tvSyncPriceLineColor(chartId, _drawSelectedIdx,
                    ds.drawings[_drawSelectedIdx].color || _drawDefaults.color);
            }
        }
    }
    // Brush/Highlighter commit still uses container mouseup
    function brushCommit() {
        if (_drawPending && (_drawPending.type === 'brush' || _drawPending.type === 'highlighter') && _drawPending.chartId === chartId) {
            if (_drawPending.points && _drawPending.points.length > 1) {
                ds.drawings.push(Object.assign({}, _drawPending));
                _drawSelectedIdx = ds.drawings.length - 1;
                _drawSelectedChart = chartId;
                _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
                _emitDrawingAdded(chartId, _drawPending);
            }
            _drawPending = null;
            _tvRenderDrawings(chartId);
        }
    }
    container.addEventListener('mouseup', brushCommit, true);   // capture phase

    // --- Double-click: open drawing settings (cursor mode) ---
    container.addEventListener('dblclick', function(e) {
        if (entry._interactionLocked) return;
        if (ds._activeTool !== 'cursor') return;
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;
        var hitIdx = _tvHitTest(chartId, mx, my);
        if (hitIdx >= 0) {
            e.preventDefault();
            e.stopPropagation();
            _drawSelectedIdx = hitIdx;
            _drawSelectedChart = chartId;
            _tvRenderDrawings(chartId);
            _tvShowDrawingSettings(chartId, hitIdx);
        }
    });

    // --- Click: select/deselect drawing (cursor mode) ---
    container.addEventListener('click', function(e) {
        if (entry._interactionLocked) return;
        if (ds._activeTool !== 'cursor') return;
        // Skip click if a drag just completed
        if (_drawDidDrag) {
            _drawDidDrag = false;
            return;
        }
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;
        var hitIdx = _tvHitTest(chartId, mx, my);
        if (hitIdx >= 0) {
            _drawSelectedIdx = hitIdx;
            _drawSelectedChart = chartId;
            _tvRenderDrawings(chartId);
            _tvShowFloatingToolbar(chartId, hitIdx);
        } else {
            _tvDeselectAll(chartId);
        }
    });

    // --- Right-click: context menu (cursor mode) ---
    container.addEventListener('contextmenu', function(e) {
        if (entry._interactionLocked) return;
        if (ds._activeTool !== 'cursor') return;
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;
        var hitIdx = _tvHitTest(chartId, mx, my);
        if (hitIdx >= 0) {
            e.preventDefault();
            _drawSelectedIdx = hitIdx;
            _drawSelectedChart = chartId;
            _tvRenderDrawings(chartId);
            _tvShowFloatingToolbar(chartId, hitIdx);
            _tvShowContextMenu(chartId, hitIdx, mx, my);
        }
    });

    // =========================================================================
    // Canvas-level listeners: work in DRAWING TOOL mode (canvas has ptr-events:auto)
    // These handle live preview, click-to-place, brush, and drawing-tool context menu.
    // =========================================================================

    // --- Mouse move on canvas: live preview for in-progress drawing ---
    canvas.addEventListener('mousemove', function(e) {
        if (!_drawPending || _drawPending.chartId !== chartId) return;
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;
        var pc = _tvFromPixel(chartId, mx, my);
        if (pc) {
            if ((_drawPending.type === 'brush' || _drawPending.type === 'highlighter') && _drawPending.points && !_drawPending._multiPoint) {
                _drawPending.points.push({ t: pc.time, p: pc.price });
            } else if (_drawPending._phase === 2) {
                // 3-point tool: phase 2 previews the third anchor
                _drawPending.t3 = pc.time;
                _drawPending.p3 = pc.price;
            } else {
                _drawPending.t2 = pc.time;
                _drawPending.p2 = pc.price;
            }
            _tvRenderDrawings(chartId);
        }
    });

    // --- Click on canvas: place drawing (drawing tool mode) ---
    canvas.addEventListener('click', function(e) {
        var _tool = ds._activeTool;
        // Drawing tools only — cursor mode is handled on container
        if (_tool === 'cursor' || _tool === 'crosshair') return;

        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;
        var coord = _tvFromPixel(chartId, mx, my);
        if (!coord || coord.time === null || coord.price === null) return;

        if (_tool === 'hline') {
            var hlD = {
                _id: ++_drawIdCounter, type: 'hline', price: coord.price,
                chartId: chartId, color: _drawDefaults.color,
                lineWidth: _drawDefaults.lineWidth, lineStyle: _drawDefaults.lineStyle,
                showPriceLabel: true, title: '', extend: "Don't extend",
            };
            ds.drawings.push(hlD);
            // Native price line
            var mainKey = Object.keys(entry.seriesMap)[0];
            if (mainKey && entry.seriesMap[mainKey]) {
                var pl = entry.seriesMap[mainKey].createPriceLine({
                    price: coord.price, color: hlD.color,
                    lineWidth: hlD.lineWidth, lineStyle: hlD.lineStyle,
                    axisLabelVisible: true, title: '',
                });
                ds.priceLines.push({ seriesId: mainKey, priceLine: pl });
            }
            _tvRenderDrawings(chartId);
            // Auto-select new drawing
            _drawSelectedIdx = ds.drawings.length - 1;
            _drawSelectedChart = chartId;
            _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
            _emitDrawingAdded(chartId, hlD);
            return;
        }

        if (_tool === 'text') {
            var txtD = {
                _id: ++_drawIdCounter, type: 'text', t1: coord.time, p1: coord.price,
                text: 'Text', chartId: chartId, color: _drawDefaults.color,
                fontSize: 14, lineWidth: _drawDefaults.lineWidth,
            };
            ds.drawings.push(txtD);
            _tvRenderDrawings(chartId);
            _drawSelectedIdx = ds.drawings.length - 1;
            _drawSelectedChart = chartId;
            _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
            _emitDrawingAdded(chartId, txtD);
            // Open settings panel with Text tab
            _tvShowDrawingSettings(chartId, _drawSelectedIdx);
            return;
        }

        // Single-click text/notes tools
        var _singleClickTextTools = ['anchored_text', 'note', 'price_note', 'pin', 'comment', 'price_label', 'signpost', 'flag_mark'];
        if (_singleClickTextTools.indexOf(_tool) !== -1) {
            var _sctDefText = { anchored_text: 'Text', note: 'Note', price_note: 'Price Note', pin: '', comment: 'Comment', price_label: 'Label', signpost: 'Signpost', flag_mark: '' };
            var sctD = {
                _id: ++_drawIdCounter, type: _tool, t1: coord.time, p1: coord.price,
                text: _sctDefText[_tool] || '', chartId: chartId,
                color: _drawDefaults.color, fontSize: 14,
                bold: false, italic: false,
                bgEnabled: true, bgColor: '#2a2e39',
                borderEnabled: false, borderColor: _drawDefaults.color,
                lineWidth: _drawDefaults.lineWidth,
            };
            ds.drawings.push(sctD);
            _tvRenderDrawings(chartId);
            _drawSelectedIdx = ds.drawings.length - 1;
            _drawSelectedChart = chartId;
            _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
            _emitDrawingAdded(chartId, sctD);
            _tvShowDrawingSettings(chartId, _drawSelectedIdx);
            return;
        }

        // Vertical Line — single-click, anchored by time only
        if (_tool === 'vline') {
            var vlD = {
                _id: ++_drawIdCounter, type: 'vline', t1: coord.time,
                chartId: chartId, color: _drawDefaults.color,
                lineWidth: _drawDefaults.lineWidth, lineStyle: _drawDefaults.lineStyle,
            };
            ds.drawings.push(vlD);
            _tvRenderDrawings(chartId);
            _drawSelectedIdx = ds.drawings.length - 1;
            _drawSelectedChart = chartId;
            _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
            _emitDrawingAdded(chartId, vlD);
            return;
        }

        // Cross Line — single-click, crosshair-style
        if (_tool === 'crossline') {
            var clD = {
                _id: ++_drawIdCounter, type: 'crossline', t1: coord.time, p1: coord.price,
                chartId: chartId, color: _drawDefaults.color,
                lineWidth: _drawDefaults.lineWidth, lineStyle: _drawDefaults.lineStyle,
            };
            ds.drawings.push(clD);
            _tvRenderDrawings(chartId);
            _drawSelectedIdx = ds.drawings.length - 1;
            _drawSelectedChart = chartId;
            _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
            _emitDrawingAdded(chartId, clD);
            return;
        }

        // Arrow mark single-click tools
        var arrowMarks = ['arrow_mark_up', 'arrow_mark_down', 'arrow_mark_left', 'arrow_mark_right'];
        if (arrowMarks.indexOf(_tool) !== -1) {
            var amD = {
                _id: ++_drawIdCounter, type: _tool, t1: coord.time, p1: coord.price,
                chartId: chartId, color: _drawDefaults.color,
                fillColor: _drawDefaults.color, borderColor: _drawDefaults.color, textColor: _drawDefaults.color,
                lineWidth: _drawDefaults.lineWidth, size: 30,
                text: '', fontSize: 16, bold: false, italic: false,
            };
            ds.drawings.push(amD);
            _tvRenderDrawings(chartId);
            _drawSelectedIdx = ds.drawings.length - 1;
            _drawSelectedChart = chartId;
            _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
            _emitDrawingAdded(chartId, amD);
            return;
        }

        // Anchored VWAP — single-click anchor point
        if (_tool === 'anchored_vwap') {
            var avD = {
                _id: ++_drawIdCounter, type: 'anchored_vwap', t1: coord.time, p1: coord.price,
                chartId: chartId, color: _drawDefaults.color || '#2962FF',
                lineWidth: _drawDefaults.lineWidth,
            };
            ds.drawings.push(avD);
            _tvRenderDrawings(chartId);
            _drawSelectedIdx = ds.drawings.length - 1;
            _drawSelectedChart = chartId;
            _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
            _emitDrawingAdded(chartId, avD);
            return;
        }

        // Two-point tools (including ray, extended_line, hray, flat_channel, regression_channel)
        var twoPointTools = ['trendline', 'ray', 'extended_line', 'hray',
                             'rect', 'channel', 'flat_channel', 'regression_channel',
                             'fibonacci', 'measure',
                             'fib_timezone', 'fib_fan', 'fib_arc', 'fib_circle',
                             'fib_spiral', 'gann_box', 'gann_square_fixed', 'gann_square', 'gann_fan',
                             'arrow_marker', 'arrow', 'circle', 'ellipse', 'curve',
                             'long_position', 'short_position', 'forecast',
                             'bars_pattern', 'ghost_feed', 'projection', 'fixed_range_vol',
                             'price_range', 'date_range', 'date_price_range',
                             'callout'];
        // Three-point tools (A→B, then C on second click)
        var threePointTools = ['fib_extension', 'fib_channel', 'fib_wedge', 'pitchfan', 'fib_time',
                               'rotated_rect', 'triangle', 'shape_arc', 'double_curve'];
        if (threePointTools.indexOf(_tool) !== -1) {
            if (!_drawPending || _drawPending.chartId !== chartId) {
                // First click: set A
                _drawPending = {
                    _id: ++_drawIdCounter, type: _tool,
                    t1: coord.time, p1: coord.price,
                    t2: coord.time, p2: coord.price,
                    chartId: chartId, color: _drawDefaults.color,
                    lineWidth: _drawDefaults.lineWidth, lineStyle: _drawDefaults.lineStyle,
                    _phase: 1,
                };
            } else if (_drawPending._phase === 1) {
                // Second click: set B, start previewing C
                _drawPending.t2 = coord.time;
                _drawPending.p2 = coord.price;
                _drawPending.t3 = coord.time;
                _drawPending.p3 = coord.price;
                _drawPending._phase = 2;
            } else {
                // Third click: set C, commit
                _drawPending.t3 = coord.time;
                _drawPending.p3 = coord.price;
                delete _drawPending._phase;
                ds.drawings.push(Object.assign({}, _drawPending));
                var committed = _drawPending;
                _drawPending = null;
                _tvRenderDrawings(chartId);
                _drawSelectedIdx = ds.drawings.length - 1;
                _drawSelectedChart = chartId;
                _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
                _emitDrawingAdded(chartId, committed);
            }
            return;
        }
        if (twoPointTools.indexOf(_tool) !== -1) {
            if (!_drawPending || _drawPending.chartId !== chartId) {
                _drawPending = {
                    _id: ++_drawIdCounter, type: _tool,
                    t1: coord.time, p1: coord.price,
                    t2: coord.time, p2: coord.price,
                    chartId: chartId, color: _drawDefaults.color,
                    lineWidth: _drawDefaults.lineWidth, lineStyle: _drawDefaults.lineStyle,
                    offset: 30,
                    extend: "Don't extend",
                    ray: false,
                    showMiddlePoint: false,
                    showPriceLabels: false,
                    stats: 'hidden',
                    statsPosition: 'right',
                    alwaysShowStats: false,
                };
                if (_tool === 'arrow_marker' || _tool === 'arrow') {
                    _drawPending.text = '';
                    _drawPending.fontSize = 16;
                    _drawPending.bold = false;
                    _drawPending.italic = false;
                    _drawPending.fillColor = _drawDefaults.color;
                    _drawPending.borderColor = _drawDefaults.color;
                    _drawPending.textColor = _drawDefaults.color;
                }
                if (_tool === 'callout') {
                    _drawPending.text = 'Callout';
                    _drawPending.fontSize = 14;
                    _drawPending.bold = false;
                    _drawPending.italic = false;
                    _drawPending.bgEnabled = true;
                    _drawPending.bgColor = '#2a2e39';
                    _drawPending.borderEnabled = false;
                    _drawPending.borderColor = _drawDefaults.color;
                }
            } else {
                _drawPending.t2 = coord.time;
                _drawPending.p2 = coord.price;
                ds.drawings.push(Object.assign({}, _drawPending));
                var committed = _drawPending;
                _drawPending = null;
                _tvRenderDrawings(chartId);
                // Auto-select
                _drawSelectedIdx = ds.drawings.length - 1;
                _drawSelectedChart = chartId;
                _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
                _emitDrawingAdded(chartId, committed);
            }
            return;
        }

        // Brush / Highlighter — free-form drawing, collect points on drag
        if (_tool === 'brush' || _tool === 'highlighter') {
            _drawPending = {
                _id: ++_drawIdCounter, type: _tool,
                points: [{ t: coord.time, p: coord.price }],
                chartId: chartId, color: _drawDefaults.color,
                lineWidth: _tool === 'highlighter' ? 10 : _drawDefaults.lineWidth,
                opacity: _tool === 'highlighter' ? 0.4 : 1,
            };
            _tvRenderDrawings(chartId);
            return;
        }

        // Path / Polyline — click-per-point, double-click or right-click to finish
        if (_tool === 'path' || _tool === 'polyline') {
            if (!_drawPending || _drawPending.chartId !== chartId) {
                _drawPending = {
                    _id: ++_drawIdCounter, type: _tool,
                    points: [{ t: coord.time, p: coord.price }],
                    chartId: chartId, color: _drawDefaults.color,
                    lineWidth: _drawDefaults.lineWidth, lineStyle: _drawDefaults.lineStyle,
                    _multiPoint: true,
                };
            } else {
                _drawPending.points.push({ t: coord.time, p: coord.price });
            }
            _tvRenderDrawings(chartId);
            return;
        }
    });

    // Double-click to commit path/polyline
    canvas.addEventListener('dblclick', function(e) {
        if (!_drawPending || !_drawPending._multiPoint) return;
        var d = _drawPending;
        // Remove last duplicated point from dblclick
        if (d.points.length > 2) d.points.pop();
        delete d._multiPoint;
        ds.drawings.push(Object.assign({}, d));
        var committed = d;
        _drawPending = null;
        _tvRenderDrawings(chartId);
        _drawSelectedIdx = ds.drawings.length - 1;
        _drawSelectedChart = chartId;
        _tvShowFloatingToolbar(chartId, _drawSelectedIdx);
        _emitDrawingAdded(chartId, committed);
    });

    // --- Right-click on canvas: cancel pending drawing and revert to cursor ---
    canvas.addEventListener('contextmenu', function(e) {
        if (_drawPending) {
            e.preventDefault();
            _drawPending = null;
            _tvRenderDrawings(chartId);
            _tvRevertToCursor(chartId);
        } else if (ds._activeTool !== 'cursor' && ds._activeTool !== 'crosshair') {
            e.preventDefault();
            _tvRevertToCursor(chartId);
        }
    });

    // --- Keyboard shortcuts ---
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            // Cancel pending drawing
            if (_drawPending) {
                _drawPending = null;
                _tvRenderDrawings(chartId);
            }
            // If a drawing tool is active, revert to cursor
            if (ds._activeTool !== 'cursor' && ds._activeTool !== 'crosshair') {
                _tvRevertToCursor(chartId);
                return;
            }
            // Otherwise deselect any selected drawing
            if (_drawSelectedIdx >= 0 && _drawSelectedChart === chartId) {
                _tvDeselectAll(chartId);
            }
            return;
        }
        if (_drawSelectedIdx < 0 || _drawSelectedChart !== chartId) return;
        if (e.key === 'Delete' || e.key === 'Backspace') {
            e.preventDefault();
            _tvDeleteDrawing(chartId, _drawSelectedIdx);
        }
    });
}

function _tvDeselectAll(chartId) {
    _drawSelectedIdx   = -1;
    _drawSelectedChart = null;
    _drawHoverIdx      = -1;
    _tvHideFloatingToolbar();
    _tvHideContextMenu();
    _tvRenderDrawings(chartId);
}

// Revert to cursor mode and update the left toolbar UI
function _tvRevertToCursor(chartId) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds || ds._activeTool === 'cursor') return;
    _tvSetDrawTool(chartId, 'cursor');
    // Update left toolbar scoped to this chart
    var allIcons = _tvScopedQueryAll(chartId, '.pywry-toolbar-left .pywry-icon-btn');
    if (allIcons) allIcons.forEach(function(el) { el.classList.remove('active'); });
    var cursorBtn = _tvScopedById(chartId, 'tvchart-tool-cursor');
    if (cursorBtn) cursorBtn.classList.add('active');
}

function _emitDrawingAdded(chartId, d) {
    // Push undo entry for the newly added drawing (always the last in the array)
    var _undoChartId = chartId;
    var _undoDrawing = Object.assign({}, d);
    _tvPushUndo({
        label: 'Add ' + (d.type || 'drawing'),
        undo: function() {
            var ds = window.__PYWRY_DRAWINGS__[_undoChartId];
            if (!ds) return;
            // Find and remove the drawing by _id
            for (var i = ds.drawings.length - 1; i >= 0; i--) {
                if (ds.drawings[i]._id === _undoDrawing._id) {
                    // Remove native price line if hline
                    if (ds.drawings[i].type === 'hline' && ds.priceLines[i]) {
                        var entry = window.__PYWRY_TVCHARTS__[_undoChartId];
                        if (entry) {
                            var pl = ds.priceLines[i];
                            var ser = entry.seriesMap[pl.seriesId];
                            if (ser) try { ser.removePriceLine(pl.priceLine); } catch(e) {}
                        }
                        ds.priceLines.splice(i, 1);
                    }
                    ds.drawings.splice(i, 1);
                    break;
                }
            }
            _tvDeselectAll(_undoChartId);
        },
        redo: function() {
            var ds = window.__PYWRY_DRAWINGS__[_undoChartId];
            if (!ds) return;
            ds.drawings.push(Object.assign({}, _undoDrawing));
            // Re-create native price line if hline
            if (_undoDrawing.type === 'hline') {
                var entry = window.__PYWRY_TVCHARTS__[_undoChartId];
                if (entry) {
                    var mainKey = Object.keys(entry.seriesMap)[0];
                    if (mainKey && entry.seriesMap[mainKey]) {
                        var pl = entry.seriesMap[mainKey].createPriceLine({
                            price: _undoDrawing.price, color: _undoDrawing.color,
                            lineWidth: _undoDrawing.lineWidth, lineStyle: _undoDrawing.lineStyle,
                            axisLabelVisible: true, title: '',
                        });
                        ds.priceLines.push({ seriesId: mainKey, priceLine: pl });
                    }
                }
            }
            _tvDeselectAll(_undoChartId);
        },
    });
    if (window.pywry && window.pywry.emit) {
        window.pywry.emit('tvchart:drawing-added', { chartId: chartId, drawing: d });
    }
    // Auto-revert to cursor after every drawing finishes so the
    // toolbar button doesn't stay highlighted forever.
    _tvRevertToCursor(chartId);
}

// ---- Tool switching ----
function _tvSetDrawTool(chartId, tool) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds) {
        _tvEnsureDrawingLayer(chartId);
        ds = window.__PYWRY_DRAWINGS__[chartId];
    }
    if (!ds) return;

    ds._activeTool = tool;
    if (_drawPending && _drawPending.chartId === chartId) {
        _drawPending = null;
    }

    _tvApplyDrawingInteractionMode(ds);

    // Toggle chart crosshair lines based on tool selection
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (entry && entry._chartPrefs) {
        entry._chartPrefs.crosshairEnabled = (tool === 'crosshair');
        _tvApplyHoverReadoutMode(entry);
    }

    // Deselect when switching tools
    _tvDeselectAll(chartId);
}

// ---- Clear all drawings ----
function _tvClearDrawings(chartId) {
    var ds = window.__PYWRY_DRAWINGS__[chartId];
    if (!ds) return;
    var entry = window.__PYWRY_TVCHARTS__[chartId];
    if (entry) {
        for (var i = 0; i < ds.priceLines.length; i++) {
            var pl = ds.priceLines[i];
            var ser = entry.seriesMap[pl.seriesId];
            if (ser) try { ser.removePriceLine(pl.priceLine); } catch(e) {}
        }
    }
    ds.priceLines = [];
    ds.drawings   = [];
    if (_drawPending && _drawPending.chartId === chartId) _drawPending = null;
    _drawSelectedIdx   = -1;
    _drawSelectedChart = null;
    _tvHideFloatingToolbar();
    _tvHideContextMenu();
    _tvRenderDrawings(chartId);
}

