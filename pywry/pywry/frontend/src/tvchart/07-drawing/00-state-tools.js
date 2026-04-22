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

