// PyWry Chat Handlers
// Manages chat UI: messages, streaming, threads, slash commands, settings.
// Follows the same pattern as toolbar-handlers.js:
//   initChatHandlers(container, pywry) — called with container + pywry object.
//   Uses pywry.emit() for outbound events, pywry.on() for inbound.
//   All DOM queries scoped to container.
//
// Layout follows VS Code Copilot Chat:
//   Header bar (conv picker dropdown + settings dropdown + actions) | Messages | Input bar
//
// Settings is a dropdown menu anchored to the gear icon.  Developers
// register items via chat:register-settings-item event.
//
// Conversations show editable titles and selectable/copyable IDs.

/* eslint-disable no-var */

// =========================================================================
// Constants (mirrors chat.py safety constants)
// =========================================================================
var __PYWRY_CHAT_MAX_RENDERED = 200;
var __PYWRY_CHAT_MAX_MSG_SIZE = 500000;
var __PYWRY_CHAT_MAX_CODE_LINES = 500;
var __PYWRY_CHAT_SEND_COOLDOWN = 1000;
var __PYWRY_CHAT_SCROLL_THRESHOLD = 100;

function initChatHandlers(container, pywry) {
  if (!container || !pywry) return;

  var eventRoot = typeof container.addEventListener === 'function' ? container : document;
  var queryRoot = container;
  if (container && container.nodeType === 9) {
    queryRoot = container.querySelector('.pywry-chat') || container;
  } else if (
    container &&
    container.nodeType === 1 &&
    container.classList &&
    !container.classList.contains('pywry-chat') &&
    typeof container.querySelector === 'function'
  ) {
    queryRoot = container.querySelector('.pywry-chat') || container;
  }
  if (!queryRoot || typeof queryRoot.querySelector !== 'function') return;

  // =========================================================================
  // Scoped DOM helpers
  // =========================================================================
  function $(sel) { return queryRoot.querySelector(sel); }

  var chatArea    = $('#pywry-chat-messages');
  var inputEl     = $('#pywry-chat-input');
  var sendBtnEl   = $('#pywry-chat-send');
  var sidebarEl   = $('#pywry-chat-sidebar');
  var cmdPalette  = $('#pywry-chat-cmd-palette');
  var settingsEl  = $('#pywry-chat-settings');       // dropdown container
  var typingEl    = $('#pywry-chat-typing');
  var badgeEl     = $('#pywry-chat-new-msg-badge');
  var todoEl      = $('#pywry-chat-todo');

  // Header conversation picker
  var convPickerEl = $('.pywry-chat-conv-picker');
  var convBtnEl    = $('#pywry-chat-conv-btn');
  var convTitleEl  = $('#pywry-chat-conv-title');

  // Settings dropdown wrapper
  var settingsMenuEl = queryRoot.querySelector('.pywry-chat-settings-menu');

  // Context / attachments elements (may be null when context is disabled)
  var attachBtnEl    = $('#pywry-chat-attach-btn');
  var attachBarEl    = $('#pywry-chat-attachments-bar');
  var dropOverlayEl  = $('#pywry-chat-drop-overlay');
  var mentionPopupEl = $('#pywry-chat-mention-popup');

  // Bail if no chat DOM present
  if (!chatArea || !inputEl) return;

  // Guard against double-init on the same container
  if (chatArea.__pywryChatInit) return;
  chatArea.__pywryChatInit = true;

  // =========================================================================
  // State
  // =========================================================================
  var state = {
    messages: [],
    activeThreadId: null,
    threads: [],
    slashCommands: [],
    isStreaming: false,
    isGenerating: false,  // true from send until response completes
    streamingMsgId: null,
    lastSendTime: 0,
    settingsItems: [],
    inputRequiredRequestId: null,
    userScrolledUp: false,
    attachments: [],       // {type, name, content, mimeType, path, widgetId}
    contextSources: [],    // available @mention targets from backend
  };

  // Show stop button + disable input (called on send and streaming start)
  function showStopButton() {
    state.isGenerating = true;
    if (sendBtnEl) {
      sendBtnEl.classList.add('pywry-chat-stop');
      sendBtnEl.innerHTML = '<svg width="14" height="14" viewBox="0 0 14 14"><rect x="2" y="2" width="10" height="10" rx="1" fill="currentColor"/></svg>';
      sendBtnEl.setAttribute('data-tooltip', 'Stop generation');
    }
    if (inputEl) inputEl.disabled = true;
  }

  // Restore send button + enable input
  function showSendButton() {
    state.isGenerating = false;
    if (sendBtnEl) {
      sendBtnEl.classList.remove('pywry-chat-stop');
      sendBtnEl.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16"><path d="M1 8l6-6v4h7v4H7v4L1 8z" fill="currentColor"/></svg>';
      sendBtnEl.setAttribute('data-tooltip', 'Send message');
    }
    if (inputEl) {
      inputEl.disabled = false;
      inputEl.focus();
    }
  }

  // =========================================================================
  // Escape HTML (XSS prevention)
  // =========================================================================
  function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // =========================================================================
  // Markdown — lightweight inline parser (no external deps)
  // =========================================================================

  // =========================================================================
  // Syntax Highlighting — lightweight regex tokenizer (VS Code Dark+ inspired)
  // =========================================================================
  var _hlLangs = {};

  // Token types: kw (keyword), str (string), cmt (comment), num (number),
  //   fn (function/method), dec (decorator/attr), type (builtin type),
  //   op (operator), punc (punctuation), prop (property/key)

  // --- Python ---
  _hlLangs.python = _hlLangs.py = [
    [/^(#.*)$/gm, 'cmt'],
    [/("""[\s\S]*?"""|'''[\s\S]*?''')/g, 'str'],
    [/("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, 'str'],
    [/(f"(?:[^"\\]|\\.)*"|f'(?:[^'\\]|\\.)*')/g, 'str'],
    [/\b(def|class|return|import|from|as|if|elif|else|for|while|try|except|finally|with|yield|raise|pass|break|continue|and|or|not|in|is|lambda|async|await|global|nonlocal|assert|del)\b/g, 'kw'],
    [/\b(True|False|None|self|cls)\b/g, 'type'],
    [/\b(int|str|float|bool|list|dict|set|tuple|bytes|type|object|range|print|len|isinstance|hasattr|getattr|setattr|super|property|staticmethod|classmethod|enumerate|zip|map|filter|sorted|reversed|any|all|open|input)\b/g, 'fn'],
    [/(@\w+)/g, 'dec'],
    [/\b(\d+\.?\d*(?:e[+-]?\d+)?|0[xX][\da-fA-F]+|0[bB][01]+|0[oO][0-7]+)\b/g, 'num'],
  ];

  // --- JavaScript / TypeScript ---
  _hlLangs.javascript = _hlLangs.js = _hlLangs.typescript = _hlLangs.ts = _hlLangs.jsx = _hlLangs.tsx = [
    [/(\/\/.*$)/gm, 'cmt'],
    [/(\/\*[\s\S]*?\*\/)/g, 'cmt'],
    [/(`(?:[^`\\]|\\.)*`)/g, 'str'],
    [/("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, 'str'],
    [/\b(var|let|const|function|return|if|else|for|while|do|switch|case|break|continue|try|catch|finally|throw|new|delete|typeof|instanceof|in|of|class|extends|super|import|export|default|from|as|async|await|yield|this|void|with)\b/g, 'kw'],
    [/\b(true|false|null|undefined|NaN|Infinity)\b/g, 'type'],
    [/\b(console|document|window|Array|Object|String|Number|Boolean|Map|Set|Promise|RegExp|Date|Math|JSON|Error|parseInt|parseFloat|setTimeout|setInterval|fetch|require)\b/g, 'fn'],
    [/\b(\d+\.?\d*(?:e[+-]?\d+)?|0[xX][\da-fA-F]+|0[bB][01]+|0[oO][0-7]+)\b/g, 'num'],
    [/(=>)/g, 'kw'],
  ];

  // --- JSON ---
  _hlLangs.json = _hlLangs.jsonc = [
    [/(\/\/.*$)/gm, 'cmt'],
    [/("(?:[^"\\]|\\.)*")\s*:/g, 'prop'],
    [/("(?:[^"\\]|\\.)*")/g, 'str'],
    [/\b(true|false|null)\b/g, 'type'],
    [/\b(-?\d+\.?\d*(?:e[+-]?\d+)?)\b/g, 'num'],
  ];

  // --- HTML / XML ---
  _hlLangs.html = _hlLangs.xml = _hlLangs.svg = [
    [/(<!--[\s\S]*?-->)/g, 'cmt'],
    [/("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, 'str'],
    [/(&lt;\/?)([\w-]+)/g, function (_m, bracket, tag) {
      return '<span class="pywry-hl-punc">' + bracket + '</span><span class="pywry-hl-kw">' + tag + '</span>';
    }],
    [/\b([\w-]+)(=)/g, function (_m, attr, eq) {
      return '<span class="pywry-hl-prop">' + attr + '</span>' + eq;
    }],
  ];

  // --- CSS / SCSS ---
  _hlLangs.css = _hlLangs.scss = _hlLangs.less = [
    [/(\/\*[\s\S]*?\*\/)/g, 'cmt'],
    [/("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, 'str'],
    [/(#[\da-fA-F]{3,8})\b/g, 'num'],
    [/\b(\d+\.?\d*(?:px|em|rem|%|vh|vw|s|ms|deg|fr)?)\b/g, 'num'],
    [/(--[\w-]+)/g, 'prop'],
    [/(@[\w-]+)/g, 'kw'],
    [/([\w-]+)\s*(?=\{)/g, 'kw'],
  ];

  // --- SQL ---
  _hlLangs.sql = [
    [/(--.*$)/gm, 'cmt'],
    [/(\/\*[\s\S]*?\*\/)/g, 'cmt'],
    [/('(?:[^'\\]|\\.)*')/g, 'str'],
    [/\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TABLE|INTO|VALUES|SET|JOIN|INNER|OUTER|LEFT|RIGHT|ON|AND|OR|NOT|IN|IS|NULL|AS|ORDER|BY|GROUP|HAVING|LIMIT|OFFSET|UNION|ALL|DISTINCT|EXISTS|BETWEEN|LIKE|INDEX|PRIMARY|KEY|FOREIGN|REFERENCES|DEFAULT|CHECK|CONSTRAINT|CASCADE|BEGIN|COMMIT|ROLLBACK|GRANT|REVOKE|VIEW|TRIGGER|PROCEDURE|FUNCTION|IF|ELSE|THEN|END|CASE|WHEN|COUNT|SUM|AVG|MIN|MAX|COALESCE|CAST|UPPER|LOWER|TRIM|VARCHAR|INT|INTEGER|TEXT|BOOLEAN|DATE|TIMESTAMP|FLOAT|DECIMAL|SERIAL|BIGINT|SMALLINT|CHAR|BLOB|NUMERIC)\b/gi, 'kw'],
    [/\b(\d+\.?\d*)\b/g, 'num'],
  ];

  // --- Shell / Bash ---
  _hlLangs.bash = _hlLangs.sh = _hlLangs.shell = _hlLangs.zsh = _hlLangs.powershell = _hlLangs.ps1 = [
    [/(#.*$)/gm, 'cmt'],
    [/("(?:[^"\\]|\\.)*"|'[^']*')/g, 'str'],
    [/\b(if|then|else|elif|fi|for|while|do|done|case|esac|in|function|return|exit|export|source|alias|unalias|set|unset|local|declare|readonly|shift|trap|eval|exec|cd|echo|printf|read|test)\b/g, 'kw'],
    [/(\$\{?\w+\}?)/g, 'type'],
    [/\b(\d+)\b/g, 'num'],
  ];

  // --- YAML ---
  _hlLangs.yaml = _hlLangs.yml = [
    [/(#.*$)/gm, 'cmt'],
    [/("(?:[^"\\]|\\.)*"|'[^']*')/g, 'str'],
    [/^([\w][\w\s.-]*)(?=:\s)/gm, 'prop'],
    [/\b(true|false|null|yes|no|on|off)\b/gi, 'type'],
    [/\b(\d+\.?\d*)\b/g, 'num'],
  ];

  // --- Rust ---
  _hlLangs.rust = _hlLangs.rs = [
    [/(\/\/.*$)/gm, 'cmt'],
    [/(\/\*[\s\S]*?\*\/)/g, 'cmt'],
    [/("(?:[^"\\]|\\.)*")/g, 'str'],
    [/\b(fn|let|mut|const|struct|enum|impl|trait|pub|mod|use|crate|super|self|Self|match|if|else|for|while|loop|break|continue|return|async|await|move|where|type|as|in|ref|unsafe|extern|dyn|static|macro_rules)\b/g, 'kw'],
    [/\b(i8|i16|i32|i64|i128|isize|u8|u16|u32|u64|u128|usize|f32|f64|bool|char|str|String|Vec|Option|Result|Box|Rc|Arc|Some|None|Ok|Err|true|false)\b/g, 'type'],
    [/(#\[[\w:]+)/g, 'dec'],
    [/\b(\d+\.?\d*(?:e[+-]?\d+)?(?:_\d+)*(?:f32|f64|i32|u32|usize)?)\b/g, 'num'],
  ];

  // --- Go ---
  _hlLangs.go = _hlLangs.golang = [
    [/(\/\/.*$)/gm, 'cmt'],
    [/(\/\*[\s\S]*?\*\/)/g, 'cmt'],
    [/("(?:[^"\\]|\\.)*"|`[^`]*`)/g, 'str'],
    [/\b(func|var|const|type|struct|interface|map|chan|package|import|return|if|else|for|range|switch|case|default|break|continue|go|select|defer|fallthrough)\b/g, 'kw'],
    [/\b(int|int8|int16|int32|int64|uint|uint8|uint16|uint32|uint64|float32|float64|complex64|complex128|byte|rune|string|bool|error|nil|true|false|iota|append|len|cap|make|new|copy|delete|close|panic|recover|print|println)\b/g, 'type'],
    [/\b(\d+\.?\d*(?:e[+-]?\d+)?|0[xX][\da-fA-F]+)\b/g, 'num'],
  ];

  // --- C / C++ ---
  _hlLangs.c = _hlLangs.cpp = _hlLangs.h = _hlLangs.hpp = _hlLangs.cc = _hlLangs.cxx = [
    [/(\/\/.*$)/gm, 'cmt'],
    [/(\/\*[\s\S]*?\*\/)/g, 'cmt'],
    [/("(?:[^"\\]|\\.)*")/g, 'str'],
    [/(#\s*\w+)/g, 'dec'],
    [/\b(if|else|for|while|do|switch|case|break|continue|return|typedef|struct|union|enum|class|public|private|protected|virtual|override|const|static|extern|inline|volatile|register|sizeof|namespace|using|template|typename|new|delete|try|catch|throw|auto|void|nullptr|this)\b/g, 'kw'],
    [/\b(int|char|float|double|long|short|unsigned|signed|bool|size_t|string|vector|map|set|list|pair|shared_ptr|unique_ptr|true|false|NULL|nullptr)\b/g, 'type'],
    [/\b(\d+\.?\d*(?:e[+-]?\d+)?[fFlLuU]*|0[xX][\da-fA-F]+[lLuU]*)\b/g, 'num'],
  ];

  // --- Java / C# / Kotlin ---
  _hlLangs.java = _hlLangs.csharp = _hlLangs.cs = _hlLangs.kotlin = _hlLangs.kt = [
    [/(\/\/.*$)/gm, 'cmt'],
    [/(\/\*[\s\S]*?\*\/)/g, 'cmt'],
    [/("(?:[^"\\]|\\.)*")/g, 'str'],
    [/\b(abstract|assert|break|case|catch|class|const|continue|default|do|else|enum|extends|final|finally|for|goto|if|implements|import|instanceof|interface|native|new|package|private|protected|public|return|static|strictfp|super|switch|synchronized|this|throw|throws|transient|try|volatile|while|var|val|fun|object|when|sealed|data|override|companion|suspend|inline|reified|lateinit|async|await|yield|using|namespace|delegate|event|get|set|virtual|void)\b/g, 'kw'],
    [/\b(boolean|byte|char|double|float|int|long|short|string|String|Integer|Boolean|Double|Float|Long|List|Map|Set|Array|true|false|null|void|Any|Unit|Nothing|Int|Pair)\b/g, 'type'],
    [/@(\w+)/g, 'dec'],
    [/\b(\d+\.?\d*(?:e[+-]?\d+)?[fFdDlL]?|0[xX][\da-fA-F]+)\b/g, 'num'],
  ];

  // --- Ruby ---
  _hlLangs.ruby = _hlLangs.rb = [
    [/(#.*$)/gm, 'cmt'],
    [/("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, 'str'],
    [/\b(def|class|module|end|if|elsif|else|unless|case|when|while|until|for|do|begin|rescue|ensure|raise|return|yield|require|include|extend|attr_reader|attr_writer|attr_accessor|puts|print|self|super|nil|true|false|and|or|not|in|then|lambda|proc)\b/g, 'kw'],
    [/(:\w+)/g, 'type'],
    [/(@\w+)/g, 'dec'],
    [/\b(\d+\.?\d*(?:e[+-]?\d+)?)\b/g, 'num'],
  ];

  // --- Markdown (inside code blocks — meta) ---
  _hlLangs.markdown = _hlLangs.md = [
    [/^(#{1,6}\s+.*)$/gm, 'kw'],
    [/(\*\*[^*]+\*\*)/g, 'str'],
    [/(\*[^*]+\*)/g, 'str'],
    [/(`[^`]+`)/g, 'fn'],
    [/(\[.*?\]\(.*?\))/g, 'type'],
  ];

  // --- Diff ---
  _hlLangs.diff = _hlLangs.patch = [
    [/^(\+.*)$/gm, 'str'],
    [/^(-.*)$/gm, 'kw'],
    [/^(@@.*@@)/gm, 'type'],
  ];

  // --- TOML ---
  _hlLangs.toml = [
    [/(#.*$)/gm, 'cmt'],
    [/("(?:[^"\\]|\\.)*"|'[^']*')/g, 'str'],
    [/^\s*([\w.-]+)\s*(?==)/gm, 'prop'],
    [/(\[[\w.-]+\])/gm, 'kw'],
    [/\b(true|false)\b/g, 'type'],
    [/\b(\d+\.?\d*(?:e[+-]?\d+)?)\b/g, 'num'],
  ];

  /**
   * Apply syntax highlighting to code text.
   * Returns HTML with <span class="pywry-hl-{type}"> wrapping tokens.
   * Text is already HTML-escaped before highlighting.
   */
  function _highlight(code, lang) {
    var rules = lang ? _hlLangs[lang.toLowerCase()] : null;
    if (!rules) return escapeHtml(code);

    // Tokenize: walk through code, applying rules in priority order.
    // We use a placeholder approach to avoid re-matching already-highlighted spans.
    var tokens = [];
    var safe = escapeHtml(code);

    for (var r = 0; r < rules.length; r++) {
      var rule = rules[r];
      var regex = rule[0];
      var tokenType = rule[1];

      // Clone regex to reset lastIndex
      var re = new RegExp(regex.source, regex.flags);

      if (typeof tokenType === 'function') {
        // Custom replacement function — call it directly
        safe = safe.replace(re, tokenType);
      } else {
        safe = safe.replace(re, function (match) {
          // Don't highlight inside already-placed spans
          if (match.indexOf('pywry-hl-') !== -1) return match;
          var idx = tokens.length;
          tokens.push('<span class="pywry-hl-' + tokenType + '">' + match + '</span>');
          return '\x00HL' + idx + '\x00';
        });
      }
    }

    // Restore placeholders
    safe = safe.replace(/\x00HL(\d+)\x00/g, function (_m, idx) {
      return tokens[parseInt(idx)];
    });

    return safe;
  }

  // Render a code block object {lang, code} → <pre><code>…</code></pre>
  function _renderCodeBlock(lang, code) {
    var lines = code.split('\n');
    // Strip single trailing empty line (common from closing fence spacing)
    if (lines.length > 1 && lines[lines.length - 1] === '') lines.pop();

    // Dedent: strip common leading whitespace (like textwrap.dedent).
    // LLMs often indent code blocks inside list items, producing unusable
    // copy-paste output. Find the minimum indentation across non-empty lines
    // and strip that many leading spaces/tabs from every line.
    var minIndent = Infinity;
    for (var i = 0; i < lines.length; i++) {
      if (lines[i].trim() === '') continue; // skip blank lines
      var leading = lines[i].match(/^[ \t]*/)[0].length;
      if (leading < minIndent) minIndent = leading;
    }
    if (minIndent > 0 && minIndent < Infinity) {
      for (var j = 0; j < lines.length; j++) {
        lines[j] = lines[j].substring(minIndent);
      }
    }

    var collapsed = lines.length > __PYWRY_CHAT_MAX_CODE_LINES;
    var shown = collapsed ? lines.slice(0, __PYWRY_CHAT_MAX_CODE_LINES).join('\n') : lines.join('\n');
    var extra = collapsed
      ? '<button class="pywry-chat-expand" onclick="this.parentNode.querySelector(\'.pywry-chat-code-hidden\').style.display=\'block\';this.remove()">Show ' +
        (lines.length - __PYWRY_CHAT_MAX_CODE_LINES) + ' more lines</button>' +
        '<span class="pywry-chat-code-hidden" style="display:none">' + escapeHtml(lines.slice(__PYWRY_CHAT_MAX_CODE_LINES).join('\n')) + '</span>'
      : '';
    var cls = lang ? ' class="language-' + escapeHtml(lang) + '"' : '';
    var highlighted = _highlight(shown, lang);
    return '<pre><code' + cls + '>' + highlighted + extra + '</code></pre>';
  }

  function renderMarkdown(text) {
    if (!text) return '';
    var start = performance.now();

    // Normalize line endings
    text = text.replace(/\r\n/g, '\n');

    // --- Phase 1: Extract fenced code blocks into placeholders ---
    // Closing ``` must be on its OWN line (only trailing whitespace allowed).
    // This prevents nested ``` fences (e.g. ```json inside an example block)
    // from being mistaken for the closing fence.
    var codeBlocks = [];
    var html = text.replace(/```(\w*)\n([\s\S]*?)\n?```[ \t]*(?:\n|$)/g, function (_m, lang, code) {
      var idx = codeBlocks.length;
      codeBlocks.push({ lang: lang || '', code: code });
      return '\nPWCB' + idx + 'PWCB\n';
    });
    // Unclosed code block at end of text (during streaming — opening ``` arrived
    // but closing ``` hasn't yet).  Show it as a code block in progress.
    html = html.replace(/```(\w*)\n([\s\S]*)$/, function (_m, lang, code) {
      var idx = codeBlocks.length;
      codeBlocks.push({ lang: lang || '', code: code });
      return '\nPWCB' + idx + 'PWCB\n';
    });

    // --- Phase 2: Extract inline code ---
    var inlineCodes = [];
    html = html.replace(/`([^`]+)`/g, function (_m, code) {
      var idx = inlineCodes.length;
      inlineCodes.push(code);
      return 'PWIC' + idx + 'PWIC';
    });

    // --- Phase 3: Escape HTML in all remaining text (XSS prevention) ---
    html = escapeHtml(html);

    // --- Phase 4: Markdown transforms (text is now HTML-safe) ---

    // Markdown tables → lightweight HTML tables
    html = html.replace(
      /(?:^|\n)(\|[^\n]+\|)\n(\|[\s:|-]+\|)\n((?:\|[^\n]+\|(?:\n|$))+)/gm,
      function (_m, headerLine, _sepLine, bodyBlock) {
        var headers = headerLine.split('|').map(function (s) { return s.trim(); }).filter(Boolean);
        var rows = bodyBlock.trim().split('\n').map(function (row) {
          return row.split('|').map(function (s) { return s.trim(); }).filter(Boolean);
        });
        var t = '<table class="pywry-chat-md-table"><thead><tr>';
        headers.forEach(function (h) { t += '<th>' + h + '</th>'; });
        t += '</tr></thead><tbody>';
        rows.forEach(function (cells) {
          t += '<tr>';
          headers.forEach(function (_h, i) { t += '<td>' + (cells[i] || '') + '</td>'; });
          t += '</tr>';
        });
        t += '</tbody></table>';
        return t;
      }
    );

    // Bold (text already HTML-escaped — no double-escape)
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // Italic
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // Strikethrough
    html = html.replace(/~~(.+?)~~/g, '<del>$1</del>');
    // Links — block javascript: URIs (href is already HTML-escaped)
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (_m, label, href) {
      if (/^\s*javascript\s*:/i.test(href)) return label;
      return '<a href="' + href + '" target="_blank" rel="noopener">' + label + '</a>';
    });

    // Headings (must come after bold/italic so inline formats inside headings work)
    html = html.replace(/(?:^|\n)######\s+(.+)/g, '<h6>$1</h6>');
    html = html.replace(/(?:^|\n)#####\s+(.+)/g, '<h5>$1</h5>');
    html = html.replace(/(?:^|\n)####\s+(.+)/g, '<h4>$1</h4>');
    html = html.replace(/(?:^|\n)###\s+(.+)/g, '<h3>$1</h3>');
    html = html.replace(/(?:^|\n)##\s+(.+)/g, '<h2>$1</h2>');
    html = html.replace(/(?:^|\n)#\s+(.+)/g, '<h1>$1</h1>');

    // Horizontal rule
    html = html.replace(/(?:^|\n)---+(?:\n|$)/g, '<hr>');

    // Blockquotes (> is escaped to &gt; by phase 3)
    html = html.replace(/(?:^|\n)((?:&gt;[^\n]*(?:\n|$))+)/g, function (_m, block) {
      var inner = block.replace(/(?:^|\n)&gt;\s?/g, '\n').trim();
      return '<blockquote>' + inner + '</blockquote>';
    });

    // Unordered lists (- or * at line start)
    html = html.replace(/(?:^|\n)((?:[-*]\s+[^\n]+(?:\n|$))+)/g, function (_m, block) {
      var items = block.trim().split('\n').map(function (line) {
        return '<li>' + line.replace(/^[-*]\s+/, '') + '</li>';
      });
      return '<ul>' + items.join('') + '</ul>';
    });

    // Ordered lists (1. 2. etc at line start)
    html = html.replace(/(?:^|\n)((?:\d+\.\s+[^\n]+(?:\n|$))+)/g, function (_m, block) {
      var items = block.trim().split('\n').map(function (line) {
        return '<li>' + line.replace(/^\d+\.\s+/, '') + '</li>';
      });
      return '<ol>' + items.join('') + '</ol>';
    });

    // --- Phase 5: Re-insert inline code ---
    html = html.replace(/PWIC(\d+)PWIC/g, function (_m, idx) {
      return '<code>' + escapeHtml(inlineCodes[parseInt(idx)]) + '</code>';
    });

    // --- Phase 6: Re-insert code blocks ---
    html = html.replace(/PWCB(\d+)PWCB/g, function (_m, idx) {
      var block = codeBlocks[parseInt(idx)];
      return _renderCodeBlock(block.lang, block.code);
    });

    // --- Phase 7: Paragraphs and line breaks ---
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');
    html = '<p>' + html + '</p>';

    if (performance.now() - start > 50) {
      return '<p>' + escapeHtml(text) + '</p><small class="pywry-chat-fmt-warn">Formatting timeout</small>';
    }
    return html;
  }

  // =========================================================================
  // Message Rendering — VS Code style (full width, role label)
  // =========================================================================
  function roleIcon(role) {
    if (role === 'user') return 'U';
    if (role === 'assistant') return 'A';
    return '';
  }

  function createMessageEl(msg) {
    var el = document.createElement('div');
    el.className = 'pywry-chat-msg pywry-chat-msg-' + msg.role;
    el.setAttribute('data-msg-id', msg.id);

    var content = msg.html || renderMarkdown(msg.text || '');

    if (content.length > __PYWRY_CHAT_MAX_MSG_SIZE) {
      var truncated = content.substring(0, __PYWRY_CHAT_MAX_MSG_SIZE);
      content = truncated +
        '<button class="pywry-chat-expand" onclick="this.parentNode.innerHTML=this.getAttribute(\'data-full\');this.remove()" ' +
        'data-full="' + escapeHtml(content) + '">Show full message</button>';
    }

    if (msg.stopped) {
      content += '<span class="pywry-chat-stopped">(stopped)</span>';
    }

    // Role label with icon (VS Code style)
    var roleLabel = '';
    if (msg.role !== 'system') {
      roleLabel = '<div class="pywry-chat-msg-role">' +
        '<span class="pywry-chat-msg-role-icon">' + roleIcon(msg.role) + '</span>' +
        '<span>' + (msg.role === 'user' ? 'You' : 'Assistant') + '</span>' +
        '</div>';
    }

    // Attachment badges for user messages
    var attachBadges = '';
    if (msg.attachments && msg.attachments.length > 0) {
      attachBadges = '<div class="pywry-chat-msg-attachments">';
      for (var ai = 0; ai < msg.attachments.length; ai++) {
        var a = msg.attachments[ai];
        var icon = a.type === 'widget' ? '@' : '\u{1F4CE}';
        attachBadges += '<span class="pywry-chat-msg-attach-badge">' + icon + ' ' + escapeHtml(a.name) + '</span>';
      }
      attachBadges += '</div>';
    }

    // Action toolbar — edit/resend on user messages, resend on assistant
    var actions = '';
    // Edit / Resend on user messages only — the user rerun flow is
    // "edit or resend YOUR prompt"; assistant bubbles (including the
    // welcome message) carry no retry action because there is no
    // prior user turn to rerun from.
    if (msg.role === 'user') {
      actions =
        '<div class="pywry-chat-msg-actions">' +
          '<button class="pywry-chat-msg-action" data-action="edit" data-tooltip="Edit and resend">' +
            '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M11.3 2.3a1.4 1.4 0 012 2L5.7 11.9 2 13l1.1-3.7z"/></svg>' +
            ' Edit' +
          '</button>' +
          '<button class="pywry-chat-msg-action" data-action="resend" data-tooltip="Resend from this message">' +
            '<svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M3 8a5 5 0 019.5-2.2"/><polyline points="13 2 13 6 9 6"/>' +
            '<path d="M13 8a5 5 0 01-9.5 2.2"/><polyline points="3 14 3 10 7 10"/></svg>' +
            ' Resend' +
          '</button>' +
        '</div>';
    }

    el.innerHTML = roleLabel + attachBadges +
      '<div class="pywry-chat-msg-content">' + content + '</div>' + actions;
    return el;
  }

  function renderMessages() {
    if (!chatArea) return;
    chatArea.innerHTML = '';
    var start = Math.max(0, state.messages.length - __PYWRY_CHAT_MAX_RENDERED);
    for (var i = start; i < state.messages.length; i++) {
      chatArea.appendChild(createMessageEl(state.messages[i]));
    }
    maybeAutoScroll();
  }

  function appendMessageToDOM(msg) {
    if (!chatArea) return;
    var nodes = chatArea.querySelectorAll('.pywry-chat-msg');
    if (nodes.length >= __PYWRY_CHAT_MAX_RENDERED) {
      chatArea.removeChild(nodes[0]);
    }
    chatArea.appendChild(createMessageEl(msg));
    maybeAutoScroll();
  }

  function maybeAutoScroll() {
    if (!chatArea) return;
    if (!state.userScrolledUp) {
      chatArea.scrollTop = chatArea.scrollHeight;
      if (badgeEl) badgeEl.style.display = 'none';
    } else if (badgeEl) {
      badgeEl.style.display = 'block';
    }
  }

  // =========================================================================
  // Streaming
  // =========================================================================
  var streamBuffer = '';
  var streamRafId = null;

  function flushStreamBuffer() {
    streamRafId = null;
    if (!state.streamingMsgId || !chatArea) return;

    var msgEl = chatArea.querySelector('[data-msg-id="' + state.streamingMsgId + '"]');
    if (!msgEl) return;

    var contentEl = msgEl.querySelector('.pywry-chat-msg-content');
    if (!contentEl) return;

    var msg = state.messages.find(function (m) { return m.id === state.streamingMsgId; });
    if (msg) {
      msg.text = (msg.text || '') + streamBuffer;
    }
    streamBuffer = '';

    if (msg) {
      contentEl.innerHTML = renderMarkdown(msg.text);
    }
    maybeAutoScroll();
  }

  function appendStreamChunk(chunk) {
    streamBuffer += chunk;
    if (!streamRafId) {
      streamRafId = requestAnimationFrame(flushStreamBuffer);
    }
  }

  function startStreaming(messageId, threadId) {
    state.isStreaming = true;
    state.streamingMsgId = messageId;

    var msg = {
      id: messageId,
      role: 'assistant',
      text: '',
      threadId: threadId || state.activeThreadId,
      stopped: false
    };
    state.messages.push(msg);
    appendMessageToDOM(msg);

    // Ensure stop button is showing (may already be from handleSend)
    showStopButton();
  }

  function stopStreaming(stopped) {
    if (streamBuffer) flushStreamBuffer();
    if (streamRafId) cancelAnimationFrame(streamRafId);
    streamRafId = null;
    streamBuffer = '';

    if (stopped) {
      var msg = state.messages.find(function (m) { return m.id === state.streamingMsgId; });
      if (msg) {
        msg.stopped = true;
        var msgEl = chatArea && chatArea.querySelector('[data-msg-id="' + state.streamingMsgId + '"]');
        if (msgEl) {
          var content = msgEl.querySelector('.pywry-chat-msg-content');
          if (content && !content.querySelector('.pywry-chat-stopped')) {
            content.insertAdjacentHTML('beforeend', '<span class="pywry-chat-stopped">(stopped)</span>');
          }
        }
      }
    }

    state.isStreaming = false;
    state.streamingMsgId = null;

    showSendButton();
  }

  // =========================================================================
  // Send / Stop — uses pywry.emit() like toolbar
  // =========================================================================
  function handleSend() {
    if (state.isStreaming || state.isGenerating) {
      handleStop();
      return;
    }

    if (!inputEl) return;
    var text = inputEl.value.trim();
    if (!text) return;

    var now = Date.now();
    if (now - state.lastSendTime < __PYWRY_CHAT_SEND_COOLDOWN) return;
    state.lastSendTime = now;

    // Input response mode — resume blocked handler instead of new request
    if (state.inputRequiredRequestId) {
      var irMsgId = 'msg_' + Math.random().toString(36).substring(2, 10);
      var irMsg = {
        id: irMsgId,
        role: 'user',
        text: text,
        threadId: state.activeThreadId,
        stopped: false
      };
      state.messages.push(irMsg);
      appendMessageToDOM(irMsg);

      pywry.emit('chat:input-response', {
        requestId: state.inputRequiredRequestId,
        text: text,
        threadId: state.activeThreadId
      });

      state.inputRequiredRequestId = null;
      inputEl.value = '';
      inputEl.placeholder = 'Ask a question...';
      autoResizeInput(inputEl);
      var irBar = inputEl.closest('.pywry-chat-input-bar');
      if (irBar) irBar.classList.remove('pywry-chat-input-required');
      // Remove any inline controls (buttons/radio) if present
      var irControls = chatArea && chatArea.querySelector('.pywry-chat-ir-controls');
      if (irControls) irControls.remove();
      return;
    }

    // Slash command check
    if (text.startsWith('/')) {
      var parts = text.split(/\s+/);
      var cmdName = parts[0].toLowerCase();
      var cmd = state.slashCommands.find(function (c) { return c.name === cmdName; });
      if (cmd) {
        pywry.emit('chat:slash-command', {
          command: cmdName,
          args: parts.slice(1).join(' '),
          threadId: state.activeThreadId
        });
        inputEl.value = '';
        autoResizeInput(inputEl);
        hideCommandPalette();
        return;
      }
    }

    // Add user message to state + DOM
    var msgId = 'msg_' + Math.random().toString(36).substring(2, 10);
    var userMsg = {
      id: msgId,
      role: 'user',
      text: text,
      threadId: state.activeThreadId,
      stopped: false,
      attachments: state.attachments.length > 0
        ? state.attachments.map(function (a) { return { name: a.name, type: a.type }; })
        : undefined
    };
    state.messages.push(userMsg);
    appendMessageToDOM(userMsg);

    // Force scroll to bottom on new message
    state.userScrolledUp = false;
    if (chatArea) chatArea.scrollTop = chatArea.scrollHeight;

    inputEl.value = '';
    autoResizeInput(inputEl);

    // Show stop button immediately so user can cancel during API call
    showStopButton();

    // Emit to backend (include attachments if any)
    var payload = {
      messageId: msgId,
      text: text,
      threadId: state.activeThreadId,
      timestamp: Date.now()
    };
    if (state.attachments.length > 0) {
      // Resolve attachments for backend — files send path (Tauri) or content (browser), widgets extract live data
      var resolved = state.attachments.map(function (a) {
        if (a.type === 'file') {
          var obj = { type: 'file', name: a.name };
          if (a.path) { obj.path = a.path; }
          if (a.content) { obj.content = a.content; }
          return obj;
        }
        // Widget — extract live data from component
        var copy = { type: a.type, name: a.name, widgetId: a.widgetId };
        var comp = window.__PYWRY_COMPONENTS__ && window.__PYWRY_COMPONENTS__[a.componentId];
        if (comp && comp.getData) {
          try { copy.content = comp.getData(); } catch (e) { /* noop */ }
        }
        return copy;
      });
      payload.attachments = resolved;
    }
    pywry.emit('chat:user-message', payload);

    // Clear attachments after sending
    state.attachments = [];
    renderAttachmentPills();
  }

  function handleStop() {
    pywry.emit('chat:stop-generation', {
      threadId: state.activeThreadId,
      messageId: state.streamingMsgId
    });
    if (state.isStreaming) {
      stopStreaming(true);
    } else {
      // Stop pressed before streaming started (during API call / typing phase)
      showSendButton();
      if (typingEl) typingEl.style.display = 'none';
    }
  }

  // =========================================================================
  // Input auto-resize
  // =========================================================================
  function autoResizeInput(el) {
    if (!el) return;
    el.style.height = 'auto';
    var sh = el.scrollHeight;
    el.style.height = Math.min(sh, 200) + 'px';
    el.style.overflowY = sh > 200 ? 'auto' : 'hidden';
  }

  // =========================================================================
  // Conversation Picker — editable titles, visible IDs
  // =========================================================================
  function updateConvTitle() {
    if (!convTitleEl) return;
    var active = state.threads.find(function (t) { return t.thread_id === state.activeThreadId; });
    convTitleEl.textContent = active ? active.title : 'New Chat';
  }

  function dismissTooltip() {
    // Hide ALL tooltip elements (tooltip-manager.js AND toolbar-handlers.js)
    document.querySelectorAll('.pywry-tooltip.visible').forEach(function(t) {
      t.classList.remove('visible');
    });
    var tip = document.getElementById('pywry-tooltip');
    if (tip) tip.classList.remove('visible');
  }

  function toggleConvDropdown() {
    if (!convPickerEl) return;
    closeSettingsMenu();
    var wasOpen = convPickerEl.classList.contains('open');
    convPickerEl.classList.toggle('open');
    if (!wasOpen) {
      dismissTooltip();
      if (convBtnEl) convBtnEl.removeAttribute('data-tooltip');
      var dd = convPickerEl.querySelector('.pywry-chat-conv-dropdown');
      if (dd) {
        var rect = convBtnEl.getBoundingClientRect();
        dd.style.top = (rect.bottom + 4) + 'px';
        dd.style.left = rect.left + 'px';
      }
    } else {
      if (convBtnEl) convBtnEl.setAttribute('data-tooltip', 'Switch conversation');
    }
  }

  function closeConvDropdown() {
    if (convPickerEl) convPickerEl.classList.remove('open');
    if (convBtnEl) convBtnEl.setAttribute('data-tooltip', 'Switch conversation');
  }

  function renderThreadList() {
    if (!sidebarEl) return;
    sidebarEl.innerHTML = '';

    state.threads.forEach(function (t) {
      var li = document.createElement('div');
      li.className = 'pywry-chat-thread-item' + (t.thread_id === state.activeThreadId ? ' active' : '');
      li.setAttribute('data-thread-id', t.thread_id);

      // Info column: title + thread ID
      var info = document.createElement('div');
      info.className = 'pywry-chat-thread-info';

      var titleSpan = document.createElement('span');
      titleSpan.className = 'pywry-chat-thread-title';
      titleSpan.textContent = t.title;
      titleSpan.addEventListener('click', function () {
        closeConvDropdown();
        pywry.emit('chat:thread-switch', { threadId: t.thread_id });
      });

      var idSpan = document.createElement('span');
      idSpan.className = 'pywry-chat-thread-id';
      idSpan.textContent = t.thread_id;
      idSpan.setAttribute('data-tooltip', 'Click to copy ID');
      idSpan.addEventListener('click', function (e) {
        e.stopPropagation();
        if (navigator.clipboard) {
          navigator.clipboard.writeText(t.thread_id);
        }
        idSpan.textContent = 'Copied!';
        setTimeout(function () { idSpan.textContent = t.thread_id; }, 1000);
      });

      info.appendChild(titleSpan);
      info.appendChild(idSpan);

      // Action buttons: rename + delete
      var actions = document.createElement('div');
      actions.className = 'pywry-chat-thread-actions';

      var renameBtn = document.createElement('button');
      renameBtn.setAttribute('data-tooltip', 'Rename');
      renameBtn.textContent = '\u270F';  // ✏
      renameBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        startThreadRename(li, t);
      });

      var delBtn = document.createElement('button');
      delBtn.setAttribute('data-tooltip', 'Delete');
      delBtn.textContent = '\u2715'; // ✕
      delBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        pywry.emit('chat:thread-delete', { threadId: t.thread_id });
      });

      actions.appendChild(renameBtn);
      actions.appendChild(delBtn);

      li.appendChild(info);
      li.appendChild(actions);
      sidebarEl.appendChild(li);
    });

    updateConvTitle();
  }

  function startThreadRename(itemEl, thread) {
    var titleEl = itemEl.querySelector('.pywry-chat-thread-title');
    if (!titleEl) return;

    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'pywry-chat-thread-title-input';
    input.value = thread.title;

    titleEl.style.display = 'none';
    titleEl.parentNode.insertBefore(input, titleEl.nextSibling);
    input.focus();
    input.select();

    function commit() {
      var newTitle = input.value.trim();
      if (newTitle && newTitle !== thread.title) {
        thread.title = newTitle;
        pywry.emit('chat:thread-rename', { threadId: thread.thread_id, title: newTitle });
      }
      titleEl.textContent = thread.title;
      titleEl.style.display = '';
      if (input.parentNode) input.parentNode.removeChild(input);
      updateConvTitle();
    }

    input.addEventListener('blur', commit);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); commit(); }
      if (e.key === 'Escape') {
        titleEl.style.display = '';
        if (input.parentNode) input.parentNode.removeChild(input);
      }
    });
  }

  // =========================================================================
  // Slash Command Palette
  // =========================================================================
  var cmdPaletteIndex = -1;

  function showCommandPalette(filter) {
    if (!cmdPalette) return;

    var filtered = state.slashCommands.filter(function (c) {
      return c.name.indexOf(filter) === 0;
    });

    if (filtered.length === 0) {
      cmdPalette.style.display = 'none';
      cmdPaletteIndex = -1;
      return;
    }

    cmdPalette.innerHTML = '';
    cmdPaletteIndex = -1;
    filtered.forEach(function (c, i) {
      var item = document.createElement('div');
      item.className = 'pywry-chat-cmd-item';
      item.setAttribute('data-cmd-index', i);
      item.innerHTML =
        '<strong>' + escapeHtml(c.name) + '</strong> ' +
        '<span>' + escapeHtml(c.description || '') + '</span>';
      item.addEventListener('click', function () {
        selectPaletteItem(c.name);
      });
      item.addEventListener('mouseenter', function () {
        setCmdPaletteActive(i);
      });
      cmdPalette.appendChild(item);
    });
    cmdPalette.style.display = 'block';
  }

  function setCmdPaletteActive(index) {
    if (!cmdPalette) return;
    var items = cmdPalette.querySelectorAll('.pywry-chat-cmd-item');
    items.forEach(function (el) { el.classList.remove('active'); });
    if (index >= 0 && index < items.length) {
      items[index].classList.add('active');
      items[index].scrollIntoView({ block: 'nearest' });
    }
    cmdPaletteIndex = index;
  }

  function selectPaletteItem(cmdName) {
    if (inputEl) {
      inputEl.value = cmdName + ' ';
      inputEl.focus();
    }
    hideCommandPalette();
  }

  function hideCommandPalette() {
    if (cmdPalette) cmdPalette.style.display = 'none';
    cmdPaletteIndex = -1;
  }

  // =========================================================================
  // Settings Dropdown Menu — developer adds items dynamically
  // =========================================================================
  function toggleSettingsMenu() {
    if (!settingsMenuEl) return;
    closeConvDropdown();
    var wasOpen = settingsMenuEl.classList.contains('open');
    settingsMenuEl.classList.toggle('open');
    var btn = settingsMenuEl.querySelector('#pywry-chat-settings-toggle');
    if (!wasOpen) {
      dismissTooltip();
      if (btn) btn.removeAttribute('data-tooltip');
      var dd = settingsMenuEl.querySelector('.pywry-chat-settings-dropdown');
      if (dd && btn) {
        var rect = btn.getBoundingClientRect();
        dd.style.top = (rect.bottom + 4) + 'px';
        dd.style.right = (window.innerWidth - rect.right) + 'px';
        dd.style.left = 'auto';
      }
    } else {
      if (btn) btn.setAttribute('data-tooltip', 'Settings');
    }
  }

  function closeSettingsMenu() {
    if (settingsMenuEl) settingsMenuEl.classList.remove('open');
    var btn = settingsMenuEl && settingsMenuEl.querySelector('#pywry-chat-settings-toggle');
    if (btn) btn.setAttribute('data-tooltip', 'Settings');
  }

  function renderSettingsMenu() {
    if (!settingsEl) return;

    if (state.settingsItems.length === 0) {
      settingsEl.innerHTML = '<div class="pywry-chat-settings-empty">No settings configured</div>';
      return;
    }

    settingsEl.innerHTML = '';

    state.settingsItems.forEach(function (item) {
      if (item.type === 'separator') {
        var sep = document.createElement('div');
        sep.className = 'pywry-chat-settings-sep';
        settingsEl.appendChild(sep);
        return;
      }

      var el = document.createElement('div');
      el.className = 'pywry-chat-settings-item';
      el.setAttribute('data-settings-id', item.id);

      var label = '<span class="pywry-chat-settings-item-label">' + escapeHtml(item.label || '') + '</span>';

      if (item.type === 'action') {
        el.innerHTML = label;
        el.addEventListener('click', function () {
          pywry.emit('chat:settings-change', { key: item.id, value: null });
          closeSettingsMenu();
        });
      } else if (item.type === 'toggle') {
        el.innerHTML = label + '<input type="checkbox"' + (item.value ? ' checked' : '') + '>';
        var cb = el.querySelector('input');
        cb.addEventListener('change', function () {
          item.value = this.checked;
          pywry.emit('chat:settings-change', { key: item.id, value: this.checked });
        });
        el.addEventListener('click', function (e) {
          if (e.target !== cb) {
            cb.checked = !cb.checked;
            cb.dispatchEvent(new Event('change'));
          }
        });
      } else if (item.type === 'select') {
        var opts = (item.options || []).map(function (o) {
          var selected = String(o) === String(item.value) ? ' selected' : '';
          return '<option' + selected + '>' + escapeHtml(String(o)) + '</option>';
        }).join('');
        el.innerHTML = label + '<select>' + opts + '</select>';
        el.querySelector('select').addEventListener('change', function () {
          item.value = this.value;
          pywry.emit('chat:settings-change', { key: item.id, value: this.value });
        });
        // Prevent click on select from closing menu
        el.querySelector('select').addEventListener('click', function (e) { e.stopPropagation(); });
      } else if (item.type === 'range') {
        var min = item.min != null ? item.min : 0;
        var max = item.max != null ? item.max : 1;
        var step = item.step != null ? item.step : 0.1;
        var val = item.value != null ? item.value : min;
        el.innerHTML = label +
          '<input type="range" min="' + min + '" max="' + max + '" step="' + step + '" value="' + val + '">' +
          '<span class="pywry-chat-settings-range-val">' + val + '</span>';
        var rangeInput = el.querySelector('input[type="range"]');
        var rangeVal = el.querySelector('.pywry-chat-settings-range-val');
        rangeInput.addEventListener('input', function () {
          rangeVal.textContent = this.value;
        });
        rangeInput.addEventListener('change', function () {
          item.value = parseFloat(this.value);
          pywry.emit('chat:settings-change', { key: item.id, value: parseFloat(this.value) });
        });
        rangeInput.addEventListener('click', function (e) { e.stopPropagation(); });
      }

      settingsEl.appendChild(el);
    });
  }

  // =========================================================================
  // Event Listeners — incoming from Python via pywry.on()
  // =========================================================================

  // Edit / resend bookkeeping — drop messages the backend has discarded.
  pywry.on('chat:messages-deleted', function (data) {
    if (!chatArea) return;
    var ids = (data && data.messageIds) || [];
    if (!ids.length) return;
    var idSet = {};
    for (var i = 0; i < ids.length; i++) idSet[ids[i]] = true;
    // Drop from frontend state
    state.messages = state.messages.filter(function (m) { return !idSet[m.id]; });
    // Drop from DOM
    for (var j = 0; j < ids.length; j++) {
      var node = chatArea.querySelector('[data-msg-id="' + ids[j] + '"]');
      if (node && node.parentNode) node.parentNode.removeChild(node);
    }
    // Drop tool-call / thinking / artifact blocks tied to the deleted messages
    var related = chatArea.querySelectorAll(
      '.pywry-chat-tool-call, .pywry-chat-thinking, [data-thinking-id], [data-tool-id]',
    );
    related.forEach(function (n) {
      var tid = n.getAttribute('data-thinking-id') || n.getAttribute('data-tool-id') || '';
      // tool-id format is the run_id (no msg correlation), so skip;
      // thinking-id is "thinking-<messageId>"
      if (tid.indexOf('thinking-') === 0) {
        var msgIdPart = tid.substring(9);
        if (idSet[msgIdPart] && n.parentNode) n.parentNode.removeChild(n);
      }
    });
    // If the edited user message text changed, refresh its rendered content
    if (data.editedMessageId && data.editedText !== undefined) {
      var editedEl = chatArea.querySelector('[data-msg-id="' + data.editedMessageId + '"]');
      if (editedEl) {
        var contentEl = editedEl.querySelector('.pywry-chat-msg-content');
        if (contentEl) contentEl.innerHTML = renderMarkdown(data.editedText);
      }
      for (var k = 0; k < state.messages.length; k++) {
        if (state.messages[k].id === data.editedMessageId) {
          state.messages[k].text = data.editedText;
          break;
        }
      }
    }
  });

  // Complete assistant message
  pywry.on('chat:assistant-message', function (data) {
    if (state.isStreaming) {
      stopStreaming(false);
    } else if (state.isGenerating) {
      showSendButton();
    }
    var msg = {
      id: data.messageId || ('msg_' + Math.random().toString(36).substring(2, 10)),
      role: 'assistant',
      text: data.text || '',
      threadId: data.threadId || state.activeThreadId,
      stopped: false
    };
    state.messages.push(msg);
    appendMessageToDOM(msg);
  });

  // Stream chunk
  pywry.on('chat:stream-chunk', function (data) {
    if (!state.isStreaming && data.messageId) {
      startStreaming(data.messageId, data.threadId);
    }
    if (data.chunk) {
      appendStreamChunk(data.chunk);
    }
    if (data.done) {
      stopStreaming(data.stopped || false);
    }
  });

  // Typing indicator
  pywry.on('chat:typing-indicator', function (data) {
    if (typingEl) {
      typingEl.style.display = data.typing ? 'block' : 'none';
    }
  });

  // Switch thread
  pywry.on('chat:switch-thread', function (data) {
    state.activeThreadId = data.threadId;
    state.messages = [];
    // Clear any pending input-required state
    if (state.inputRequiredRequestId) {
      state.inputRequiredRequestId = null;
      if (inputEl) { inputEl.placeholder = 'Ask a question...'; inputEl.disabled = false; }
      var bar = inputEl && inputEl.closest('.pywry-chat-input-bar');
      if (bar) bar.classList.remove('pywry-chat-input-required');
      var irCtrl = chatArea && chatArea.querySelector('.pywry-chat-ir-controls');
      if (irCtrl) irCtrl.remove();
    }
    renderMessages();
    renderThreadList();
    pywry.emit('chat:request-history', {
      threadId: data.threadId,
      limit: __PYWRY_CHAT_MAX_RENDERED
    });
  });

  // Update thread list
  pywry.on('chat:update-thread-list', function (data) {
    state.threads = data.threads || [];
    renderThreadList();
  });

  // Clear
  pywry.on('chat:clear', function () {
    state.messages = [];
    // Clear any pending input-required state
    if (state.inputRequiredRequestId) {
      state.inputRequiredRequestId = null;
      if (inputEl) { inputEl.placeholder = 'Ask a question...'; inputEl.disabled = false; }
      var bar = inputEl && inputEl.closest('.pywry-chat-input-bar');
      if (bar) bar.classList.remove('pywry-chat-input-required');
      var irCtrl = chatArea && chatArea.querySelector('.pywry-chat-ir-controls');
      if (irCtrl) irCtrl.remove();
    }
    renderMessages();
  });

  // Register slash command
  pywry.on('chat:register-command', function (data) {
    var name = data.name.startsWith('/') ? data.name : '/' + data.name;
    var existing = state.slashCommands.find(function (c) { return c.name === name; });
    if (existing) {
      existing.description = data.description || existing.description;
      existing.handlerEvent = data.handlerEvent || existing.handlerEvent;
    } else {
      state.slashCommands.push({
        name: name,
        description: data.description || '',
        handlerEvent: data.handlerEvent || ''
      });
    }
  });

  // Register settings item — developer adds menu items dynamically
  pywry.on('chat:register-settings-item', function (data) {
    if (!data.id) return;
    var existing = state.settingsItems.find(function (s) { return s.id === data.id; });
    if (existing) {
      Object.assign(existing, data);
    } else {
      state.settingsItems.push({
        id: data.id,
        label: data.label || '',
        type: data.type || 'action',
        value: data.value != null ? data.value : null,
        options: data.options || null,
        min: data.min != null ? data.min : null,
        max: data.max != null ? data.max : null,
        step: data.step != null ? data.step : null,
      });
    }
    renderSettingsMenu();
  });

  // Update settings — applies values to matching items
  pywry.on('chat:update-settings', function (data) {
    Object.keys(data).forEach(function (key) {
      var item = state.settingsItems.find(function (s) { return s.id === key; });
      if (item) {
        item.value = data[key];
      }
    });
    renderSettingsMenu();
  });

  // History/state response
  pywry.on('chat:state-response', function (data) {
    if (data.messages) {
      state.messages = data.messages.map(function (m) {
        return {
          id: m.message_id || m.id,
          role: m.role,
          text: typeof m.content === 'string' ? m.content : '',
          threadId: data.threadId || state.activeThreadId,
          stopped: m.stopped || false
        };
      });
      renderMessages();
    }
    if (data.threads) {
      state.threads = data.threads;
      renderThreadList();
    }
    if (data.settingsItems) {
      state.settingsItems = data.settingsItems;
      renderSettingsMenu();
    }
    if (data.activeThreadId) {
      state.activeThreadId = data.activeThreadId;
      updateConvTitle();
    }
  });

  // Generation stopped confirmation
  pywry.on('chat:generation-stopped', function (data) {
    var msg = state.messages.find(function (m) { return m.id === data.messageId; });
    if (msg) {
      msg.stopped = true;
      if (data.partialContent) {
        msg.text = data.partialContent;
      }
    }
  });

  // =========================================================================
  // Protocol Events — tool calls, citations, artifacts, status
  // =========================================================================

  // Status update (e.g., "Searching...", "Thinking...")
  pywry.on('chat:status-update', function (data) {
    if (!chatArea) return;
    var msgEl = data.messageId ? chatArea.querySelector('[data-msg-id="' + data.messageId + '"]') : null;
    // Show as typing indicator text
    if (typingEl) {
      typingEl.textContent = data.text || 'Thinking';
      typingEl.style.display = data.text ? 'block' : 'none';
    }
  });

  // Thinking chunk — collapsible inline streaming block
  // NOT stored in conversation history. Auto-collapses when done.
  pywry.on('chat:thinking-chunk', function (data) {
    if (!chatArea) return;
    var blockId = 'thinking-' + (data.messageId || 'default');
    var existing = chatArea.querySelector('[data-thinking-id="' + blockId + '"]');

    if (existing) {
      // Append to existing thinking block
      var content = existing.querySelector('.pywry-chat-thinking-content');
      if (content) {
        content.textContent += data.text || '';
      }
    } else {
      // Create new collapsible thinking block
      var details = document.createElement('details');
      details.className = 'pywry-chat-thinking';
      details.setAttribute('data-thinking-id', blockId);
      details.open = true;

      var summary = document.createElement('summary');
      summary.className = 'pywry-chat-thinking-summary';
      summary.innerHTML = '<span class="pywry-chat-thinking-icon">&#9881;</span> Thinking';

      var spinner = document.createElement('span');
      spinner.className = 'pywry-chat-thinking-spinner';
      summary.appendChild(spinner);

      var content = document.createElement('div');
      content.className = 'pywry-chat-thinking-content';
      content.textContent = data.text || '';

      details.appendChild(summary);
      details.appendChild(content);
      chatArea.appendChild(details);
    }

    // Hide the old typing indicator when thinking block is active
    if (typingEl) typingEl.style.display = 'none';
    maybeAutoScroll();
  });

  // Thinking done — collapse the thinking block and update label
  pywry.on('chat:thinking-done', function (data) {
    if (!chatArea) return;
    var blockId = 'thinking-' + (data.messageId || 'default');
    var block = chatArea.querySelector('[data-thinking-id="' + blockId + '"]');
    if (block) {
      block.open = false;
      var spinner = block.querySelector('.pywry-chat-thinking-spinner');
      if (spinner) spinner.remove();
      var summary = block.querySelector('.pywry-chat-thinking-summary');
      if (summary) {
        // Update label to show it's done
        var content = block.querySelector('.pywry-chat-thinking-content');
        var charCount = content ? content.textContent.length : 0;
        summary.innerHTML = '<span class="pywry-chat-thinking-icon">&#128161;</span> Thought' +
          (charCount > 0 ? ' <span class="pywry-chat-thinking-count">(' + charCount + ' chars)</span>' : '');
      }
    }
  });

  // Tool call — collapsible <details> element (VS Code style)
  pywry.on('chat:tool-call', function (data) {
    if (!chatArea) return;
    var details = document.createElement('details');
    details.className = 'pywry-chat-tool-call';
    details.setAttribute('data-tool-id', data.toolId || '');

    var summary = document.createElement('summary');
    summary.className = 'pywry-chat-tool-summary';
    summary.innerHTML =
      '<span class="pywry-chat-tool-icon">&#9881;</span>' +
      '<span class="pywry-chat-tool-label">Used <span class="pywry-chat-tool-name">' +
      escapeHtml(data.name || 'tool') + '</span></span>' +
      '<span class="pywry-chat-tool-spinner"></span>';
    details.appendChild(summary);

    // Args (hidden inside collapsible body)
    if (Object.keys(data.arguments || {}).length > 0) {
      var argsEl = document.createElement('pre');
      argsEl.className = 'pywry-chat-tool-args';
      argsEl.innerHTML = '<code>' + escapeHtml(JSON.stringify(data.arguments, null, 2)) + '</code>';
      details.appendChild(argsEl);
    }

    chatArea.appendChild(details);
    maybeAutoScroll();
  });

  // Tool result — append inside the collapsible tool-call, update summary
  pywry.on('chat:tool-result', function (data) {
    if (!chatArea) return;
    var toolEl = data.toolId ? chatArea.querySelector('[data-tool-id="' + data.toolId + '"]') : null;

    if (toolEl) {
      // Remove spinner from summary
      var spinner = toolEl.querySelector('.pywry-chat-tool-spinner');
      if (spinner) spinner.remove();

      // Update summary label
      var label = toolEl.querySelector('.pywry-chat-tool-label');
      var icon = toolEl.querySelector('.pywry-chat-tool-icon');
      if (data.isError) {
        toolEl.classList.add('pywry-chat-tool-error');
        if (icon) icon.innerHTML = '&#10060;';
      } else {
        if (icon) icon.innerHTML = '&#10003;';
      }

      // Append result content inside collapsible (truncated for display)
      var resultEl = document.createElement('div');
      resultEl.className = 'pywry-chat-tool-result' + (data.isError ? ' pywry-chat-tool-error-text' : '');
      var resultText = data.result || '';
      var preview = resultText.length > 200
        ? resultText.substring(0, 200) + '\u2026 (' + resultText.length.toLocaleString() + ' chars)'
        : resultText;
      resultEl.innerHTML = '<pre><code>' + escapeHtml(preview) + '</code></pre>';
      toolEl.appendChild(resultEl);
    } else {
      // Fallback: standalone result (no matching tool-call found)
      var standalone = document.createElement('details');
      standalone.className = 'pywry-chat-tool-call' + (data.isError ? ' pywry-chat-tool-error' : '');
      var sum = document.createElement('summary');
      sum.className = 'pywry-chat-tool-summary';
      sum.innerHTML = '<span class="pywry-chat-tool-icon">' +
        (data.isError ? '&#10060;' : '&#10003;') +
        '</span><span class="pywry-chat-tool-label">Tool result</span>';
      standalone.appendChild(sum);
      var resEl = document.createElement('div');
      resEl.className = 'pywry-chat-tool-result';
      var resText = data.result || '';
      var resPreview = resText.length > 200
        ? resText.substring(0, 200) + '\u2026 (' + resText.length.toLocaleString() + ' chars)'
        : resText;
      resEl.innerHTML = '<pre><code>' + escapeHtml(resPreview) + '</code></pre>';
      standalone.appendChild(resEl);
      chatArea.appendChild(standalone);
    }
    maybeAutoScroll();
  });

  // Citation — append to current streaming message
  pywry.on('chat:citation', function (data) {
    if (!chatArea) return;
    var el = document.createElement('div');
    el.className = 'pywry-chat-citation';
    var titleText = escapeHtml(data.title || data.url || '');
    var safeUrl = data.url && !/^\s*javascript\s*:/i.test(data.url) ? data.url : '';
    var link = safeUrl
      ? '<a href="' + escapeHtml(safeUrl) + '" target="_blank" rel="noopener">' + titleText + '</a>'
      : titleText;
    el.innerHTML =
      '<span class="pywry-chat-citation-icon">&#128279;</span> ' + link +
      (data.snippet ? '<span class="pywry-chat-citation-snippet">' + escapeHtml(data.snippet) + '</span>' : '');
    chatArea.appendChild(el);
    maybeAutoScroll();
  });

  // =========================================================================
  // Dynamic asset injection (lazy-load AG Grid / Plotly on first artifact)
  // =========================================================================
  pywry.on('chat:load-assets', function (data) {
    var scripts = data.scripts || [];
    var styles = data.styles || [];
    styles.forEach(function (css) {
      var s = document.createElement('style');
      s.textContent = css;
      document.head.appendChild(s);
    });
    scripts.forEach(function (src) {
      var s = document.createElement('script');
      s.textContent = src;
      document.head.appendChild(s);
    });
  });

  // =========================================================================
  // Syntax highlighting — lightweight inline tokenizer (no external deps)
  // =========================================================================

  /** Wrap text in a highlight span. */
  function hl(cls, text) {
    return '<span class="pywry-hl-' + cls + '">' + escapeHtml(text) + '</span>';
  }

  // Language keyword sets
  var __hlKeywords = {
    python: /\b(False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b/,
    javascript: /\b(async|await|break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|finally|for|from|function|if|import|in|instanceof|let|new|of|return|super|switch|this|throw|try|typeof|var|void|while|with|yield)\b/,
    typescript: /\b(abstract|any|as|async|await|boolean|break|case|catch|class|const|constructor|continue|debugger|declare|default|delete|do|else|enum|export|extends|finally|for|from|function|get|if|implements|import|in|infer|instanceof|interface|is|keyof|let|module|namespace|never|new|null|number|object|of|package|private|protected|public|readonly|return|require|set|static|string|super|switch|symbol|this|throw|try|type|typeof|undefined|unique|unknown|var|void|while|with|yield)\b/,
    rust: /\b(as|async|await|break|const|continue|crate|dyn|else|enum|extern|false|fn|for|if|impl|in|let|loop|match|mod|move|mut|pub|ref|return|self|Self|static|struct|super|trait|true|type|union|unsafe|use|where|while)\b/,
    go: /\b(break|case|chan|const|continue|default|defer|else|fallthrough|for|func|go|goto|if|import|interface|map|package|range|return|select|struct|switch|type|var)\b/,
    java: /\b(abstract|assert|boolean|break|byte|case|catch|char|class|const|continue|default|do|double|else|enum|extends|final|finally|float|for|goto|if|implements|import|instanceof|int|interface|long|native|new|package|private|protected|public|return|short|static|strictfp|super|switch|synchronized|this|throw|throws|transient|try|void|volatile|while)\b/,
    csharp: /\b(abstract|as|base|bool|break|byte|case|catch|char|checked|class|const|continue|decimal|default|delegate|do|double|else|enum|event|explicit|extern|false|finally|fixed|float|for|foreach|goto|if|implicit|in|int|interface|internal|is|lock|long|namespace|new|null|object|operator|out|override|params|private|protected|public|readonly|ref|return|sbyte|sealed|short|sizeof|stackalloc|static|string|struct|switch|this|throw|true|try|typeof|uint|ulong|unchecked|unsafe|ushort|using|var|virtual|void|volatile|while)\b/,
    sql: /\b(ADD|ALL|ALTER|AND|ANY|AS|ASC|BACKUP|BETWEEN|BY|CASE|CHECK|COLUMN|CONSTRAINT|CREATE|DATABASE|DEFAULT|DELETE|DESC|DISTINCT|DROP|ELSE|END|EXEC|EXISTS|FOREIGN|FROM|FULL|GROUP|HAVING|IN|INDEX|INNER|INSERT|INTO|IS|JOIN|KEY|LEFT|LIKE|LIMIT|NOT|NULL|ON|OR|ORDER|OUTER|PRIMARY|PROCEDURE|RIGHT|ROWNUM|SELECT|SET|TABLE|THEN|TOP|TRUNCATE|UNION|UNIQUE|UPDATE|VALUES|VIEW|WHEN|WHERE|WITH)\b/i
  };

  // Built-in / type keyword patterns
  var __hlBuiltins = {
    python: /\b(abs|all|any|bin|bool|bytearray|bytes|callable|chr|classmethod|compile|complex|delattr|dict|dir|divmod|enumerate|eval|exec|filter|float|format|frozenset|getattr|globals|hasattr|hash|help|hex|id|input|int|isinstance|issubclass|iter|len|list|locals|map|max|memoryview|min|next|object|oct|open|ord|pow|print|property|range|repr|reversed|round|set|setattr|slice|sorted|staticmethod|str|sum|super|tuple|type|vars|zip)\b/,
    javascript: /\b(Array|Boolean|Date|Error|Function|JSON|Map|Math|Number|Object|Promise|Proxy|Reflect|RegExp|Set|String|Symbol|WeakMap|WeakSet|console|document|globalThis|isFinite|isNaN|parseFloat|parseInt|undefined|window)\b/,
    typescript: /\b(Array|Boolean|Date|Error|Function|JSON|Map|Math|Number|Object|Promise|Proxy|Readonly|Record|Reflect|RegExp|Partial|Required|Set|String|Symbol|WeakMap|WeakSet|console|document|globalThis|isFinite|isNaN|parseFloat|parseInt|undefined|window)\b/,
    rust: /\b(bool|char|f32|f64|i8|i16|i32|i64|i128|isize|str|u8|u16|u32|u64|u128|usize|Box|Option|Result|String|Vec|HashMap|HashSet|Rc|Arc|Cell|RefCell|println|eprintln|format|vec|Some|None|Ok|Err)\b/,
    java: /\b(Boolean|Byte|Character|Class|Double|Float|Integer|Long|Math|Number|Object|Short|String|System|Thread)\b/
  };

  /**
   * Highlight source code with editor-style colors.
   * Returns HTML string with <span class="pywry-hl-*"> elements.
   */
  // Keywords that introduce a class/type name as the next identifier
  var __hlClassIntro = /^(class|struct|enum|interface|trait|union|type)$/;
  // Keywords that introduce a function name as the next identifier
  var __hlFuncIntro = /^(def|fn|func|function)$/;
  // Self/cls/this identifiers
  var __hlSelfWords = { python: /^(self|cls)$/, rust: /^self$/, java: /^this$/, csharp: /^this$/, javascript: /^this$/, typescript: /^this$/, go: /^this$/ };
  // PascalCase heuristic: starts uppercase, has at least one lowercase letter
  var __hlPascalCase = /^[A-Z][a-zA-Z0-9]*[a-z][a-zA-Z0-9]*$/;

  function highlightCode(code, lang) {
    if (!code) return '';
    // Normalize language aliases
    var langMap = { py: 'python', js: 'javascript', ts: 'typescript', rs: 'rust', cs: 'csharp' };
    lang = langMap[lang] || lang;

    var kwRe = __hlKeywords[lang];
    var builtinRe = __hlBuiltins[lang];
    var selfRe = __hlSelfWords[lang];

    // Tokenize by scanning character by character
    var tokens = [];
    var i = 0;
    var len = code.length;
    var prevKeyword = '';  // tracks last keyword for context (class/def/etc.)

    while (i < len) {
      var ch = code[i];

      // Multi-line strings (Python triple quotes)
      if (lang === 'python' && (code.substr(i, 3) === '"""' || code.substr(i, 3) === "'''")) {
        var q3 = code.substr(i, 3);
        var end3 = code.indexOf(q3, i + 3);
        if (end3 === -1) end3 = len - 3;
        tokens.push({ type: 'string', text: code.substring(i, end3 + 3) });
        i = end3 + 3;
        continue;
      }

      // Strings (double/single/backtick)
      if (ch === '"' || ch === "'" || ch === '`') {
        var q = ch;
        var j = i + 1;
        while (j < len && code[j] !== q) {
          if (code[j] === '\\') j++; // skip escape
          j++;
        }
        tokens.push({ type: 'string', text: code.substring(i, j + 1) });
        i = j + 1;
        continue;
      }

      // Line comments
      if (ch === '/' && code[i + 1] === '/') {
        var eol = code.indexOf('\n', i);
        if (eol === -1) eol = len;
        tokens.push({ type: 'comment', text: code.substring(i, eol) });
        i = eol;
        continue;
      }
      // Hash comments (Python, Ruby, Shell)
      if (ch === '#' && (lang === 'python' || lang === 'ruby' || lang === 'bash' || lang === 'shell' || lang === 'sh')) {
        var eolH = code.indexOf('\n', i);
        if (eolH === -1) eolH = len;
        tokens.push({ type: 'comment', text: code.substring(i, eolH) });
        i = eolH;
        continue;
      }
      // Block comments
      if (ch === '/' && code[i + 1] === '*') {
        var endC = code.indexOf('*/', i + 2);
        if (endC === -1) endC = len - 2;
        tokens.push({ type: 'comment', text: code.substring(i, endC + 2) });
        i = endC + 2;
        continue;
      }
      // SQL line comments
      if (ch === '-' && code[i + 1] === '-' && lang === 'sql') {
        var eolS = code.indexOf('\n', i);
        if (eolS === -1) eolS = len;
        tokens.push({ type: 'comment', text: code.substring(i, eolS) });
        i = eolS;
        continue;
      }

      // Python decorator
      if (ch === '@' && lang === 'python') {
        var m = code.substring(i).match(/^@[\w.]+/);
        if (m) {
          tokens.push({ type: 'decorator', text: m[0] });
          i += m[0].length;
          continue;
        }
      }

      // Numbers (int, float, hex, etc.)
      if (/[0-9]/.test(ch) || (ch === '.' && i + 1 < len && /[0-9]/.test(code[i + 1]))) {
        var numMatch = code.substring(i).match(/^(0[xXoObB])?[\d_a-fA-F]+(\.[\d_]*)?(e[+-]?[\d_]+)?[jJfFlL]?/);
        if (numMatch) {
          tokens.push({ type: 'number', text: numMatch[0] });
          i += numMatch[0].length;
          continue;
        }
      }

      // Python f-strings: f"..." or f'...'
      if (lang === 'python' && (ch === 'f' || ch === 'F' || ch === 'r' || ch === 'R' || ch === 'b' || ch === 'B') && i + 1 < len && (code[i + 1] === '"' || code[i + 1] === "'")) {
        var prefix = ch;
        var sq = code[i + 1];
        // Check for triple-quote
        if (code.substr(i + 1, 3) === sq + sq + sq) {
          var e3 = code.indexOf(sq + sq + sq, i + 4);
          if (e3 === -1) e3 = len - 3;
          tokens.push({ type: 'string', text: code.substring(i, e3 + 3) });
          i = e3 + 3;
        } else {
          var sj = i + 2;
          while (sj < len && code[sj] !== sq) {
            if (code[sj] === '\\') sj++;
            sj++;
          }
          tokens.push({ type: 'string', text: code.substring(i, sj + 1) });
          i = sj + 1;
        }
        continue;
      }

      // Words (identifiers / keywords)
      if (/[a-zA-Z_$]/.test(ch)) {
        var wordMatch = code.substring(i).match(/^[a-zA-Z_$][\w$]*/);
        if (wordMatch) {
          var word = wordMatch[0];
          if (kwRe && kwRe.test(word)) {
            tokens.push({ type: 'keyword', text: word });
            prevKeyword = word;
          } else if (__hlClassIntro.test(prevKeyword)) {
            // Word right after class/struct/enum → class name
            tokens.push({ type: 'type', text: word });
            prevKeyword = '';
          } else if (__hlFuncIntro.test(prevKeyword)) {
            // Word right after def/fn/function → function definition
            tokens.push({ type: 'function', text: word });
            prevKeyword = '';
          } else if (builtinRe && builtinRe.test(word)) {
            tokens.push({ type: 'builtin', text: word });
          } else if (selfRe && selfRe.test(word)) {
            tokens.push({ type: 'parameter', text: word });
          } else if (word === 'true' || word === 'false' || word === 'null' || word === 'nil' || word === 'True' || word === 'False' || word === 'None') {
            tokens.push({ type: 'constant', text: word });
          } else {
            // Check if followed by '(' → function call
            var afterWord = code.substring(i + word.length).match(/^\s*\(/);
            if (afterWord) {
              tokens.push({ type: 'function', text: word });
            } else if (__hlPascalCase.test(word)) {
              // PascalCase identifier → likely a type/class reference
              tokens.push({ type: 'type', text: word });
            } else {
              tokens.push({ type: 'plain', text: word });
            }
          }
          i += word.length;
          continue;
        }
      }

      // Operators
      if (/[+\-*/%=<>!&|^~?:]/.test(ch)) {
        tokens.push({ type: 'operator', text: ch });
        i++;
        continue;
      }

      // Punctuation
      if (/[(){}[\],;.]/.test(ch)) {
        tokens.push({ type: 'punctuation', text: ch });
        i++;
        continue;
      }

      // Whitespace and other characters
      tokens.push({ type: 'plain', text: ch });
      i++;
    }

    // Build highlighted HTML
    var html = '';
    for (var t = 0; t < tokens.length; t++) {
      var tok = tokens[t];
      if (tok.type === 'plain' || !tok.type) {
        html += escapeHtml(tok.text);
      } else {
        html += hl(tok.type, tok.text);
      }
    }
    return html;
  }

  /**
   * Highlight JSON with editor-style colors.
   * Operates on the already-formatted JSON.stringify output.
   */
  function highlightJson(text) {
    if (!text) return '';
    // Process token by token using regex replacement
    return text.replace(
      /("(?:[^"\\]|\\.)*")\s*:|("(?:[^"\\]|\\.)*")|\b(true|false)\b|\b(null)\b|(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)\b/g,
      function (match, key, str, boolVal, nullVal, num) {
        if (key !== undefined) {
          // Object key (with colon)
          return hl('key', key) + ':';
        }
        if (str !== undefined) return hl('string', str);
        if (boolVal !== undefined) return hl('constant', boolVal);
        if (nullVal !== undefined) return hl('constant', nullVal);
        if (num !== undefined) return hl('number', num);
        return escapeHtml(match);
      }
    );
  }

  // =========================================================================
  // Artifact renderers — one per artifactType
  // =========================================================================
  var __artifactCounter = 0;

  function renderCodeArtifact(el, data) {
    var langClass = data.language ? ' class="language-' + escapeHtml(data.language) + '"' : '';
    var highlighted = highlightCode(data.content || '', (data.language || '').toLowerCase());
    el.innerHTML += '<pre class="pywry-chat-artifact-content"><code' + langClass + '>' +
      highlighted + '</code></pre>';
  }

  function renderMarkdownArtifact(el, data) {
    var body = document.createElement('div');
    body.className = 'pywry-chat-artifact-content pywry-chat-artifact-md';
    body.innerHTML = renderMarkdown(data.content || '');
    el.appendChild(body);
  }

  function renderHtmlArtifact(el, data) {
    var frame = document.createElement('iframe');
    frame.className = 'pywry-chat-artifact-iframe';
    // Sandbox: allow-scripts for rendering but NO allow-same-origin
    // to prevent access to parent page cookies, DOM, or storage.
    frame.sandbox = 'allow-scripts';
    frame.style.width = '100%';
    frame.style.height = '300px';
    frame.style.border = 'none';
    frame.setAttribute('csp', "default-src 'self' 'unsafe-inline'; script-src 'unsafe-inline'; style-src 'unsafe-inline'");
    frame.srcdoc = data.content || '';
    el.appendChild(frame);
  }

  function renderAppArtifact(el, data) {
    // Full PyWry widget rendered inline. Latest revision per widget_id
    // gets a live WS bridge; older revisions freeze server-side (their
    // WS is rejected with close code 4002) so the iframe just displays
    // its last known state.
    var frame = document.createElement('iframe');
    frame.className = 'pywry-chat-artifact-iframe pywry-chat-app-artifact';
    var allowSameOrigin = data.sandbox !== false;
    frame.sandbox = allowSameOrigin
      ? 'allow-scripts allow-same-origin allow-forms allow-popups'
      : 'allow-scripts';
    frame.style.width = '100%';
    frame.style.height = data.height || '600px';
    frame.style.border = 'none';

    // The HTML is self-contained; the embedded WS bridge reads the
    // revision from its own query string when it reconnects after a
    // freeze, so we bake it in here. Older iframes keep their stale
    // revision in their own copy of the HTML and get rejected when
    // they try to reconnect, which is the intended behaviour.
    var html = data.html || data.content || '';
    if (data.widgetId && data.revision) {
      var meta = '<meta name="pywry-app-revision" content="' + data.revision + '">';
      // Insert meta tag into <head> if present, else as first element.
      if (html.indexOf('<head>') !== -1) {
        html = html.replace('<head>', '<head>' + meta);
      } else if (html.indexOf('<html>') !== -1) {
        html = html.replace('<html>', '<html><head>' + meta + '</head>');
      } else {
        html = meta + html;
      }
    }
    frame.srcdoc = html;

    // postMessage bridge: forward events from iframe to parent chat so
    // the live (latest-revision) widget can fire chat-side callbacks.
    // Messages from stale revisions are ignored because their WS is
    // already closed by the server.
    function onMessage(evt) {
      if (!evt.data || typeof evt.data !== 'object') return;
      if (evt.data.source !== 'pywry-app') return;
      if (evt.data.widgetId !== data.widgetId) return;
      if (window.pywry && typeof window.pywry._fire === 'function') {
        window.pywry._fire(evt.data.type, {
          widgetId: data.widgetId,
          revision: data.revision,
          payload: evt.data.payload,
        });
      }
    }
    window.addEventListener('message', onMessage);

    // Host → iframe theme bridge. The AppArtifact HTML is baked with a
    // specific theme at render time; when the outer page's theme
    // changes, push the new value into the iframe so Plotly / AG Grid /
    // TVChart / layout all swap together. theme-manager.js inside the
    // iframe listens for {source: 'pywry-host', type: 'pywry:set-theme',
    // theme}.
    function detectHostTheme() {
      var root = document.documentElement;
      if (root.classList.contains('dark')) return 'dark';
      if (root.classList.contains('light')) return 'light';
      if (root.dataset && root.dataset.theme === 'dark') return 'dark';
      if (root.dataset && root.dataset.theme === 'light') return 'light';
      if (window.pywry && (window.pywry.theme === 'dark' || window.pywry.theme === 'light')) {
        return window.pywry.theme;
      }
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        return 'dark';
      }
      return 'light';
    }
    function pushTheme() {
      if (!frame.contentWindow) return;
      frame.contentWindow.postMessage(
        { source: 'pywry-host', type: 'pywry:set-theme', theme: detectHostTheme() },
        '*'
      );
    }
    frame.addEventListener('load', pushTheme);
    var mediaQuery = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
    function onMediaChange() { pushTheme(); }
    if (mediaQuery && mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', onMediaChange);
    }
    var themeObserver = new MutationObserver(pushTheme);
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class', 'data-theme'],
    });

    // Stop listening when the iframe is removed from the DOM.
    var observer = new MutationObserver(function (mutations) {
      for (var i = 0; i < mutations.length; i++) {
        var removed = mutations[i].removedNodes;
        for (var j = 0; j < removed.length; j++) {
          if (removed[j] === frame || (removed[j].contains && removed[j].contains(frame))) {
            window.removeEventListener('message', onMessage);
            if (mediaQuery && mediaQuery.removeEventListener) {
              mediaQuery.removeEventListener('change', onMediaChange);
            }
            themeObserver.disconnect();
            observer.disconnect();
            return;
          }
        }
      }
    });
    if (el.parentNode) {
      observer.observe(el.parentNode, { childList: true, subtree: true });
    }

    el.appendChild(frame);
  }

  function renderTableArtifact(el, data) {
    var gridId = 'pywry-chat-grid-' + (++__artifactCounter);
    var gridDiv = document.createElement('div');
    gridDiv.id = gridId;
    gridDiv.className = 'pywry-grid ag-theme-alpine-dark';
    gridDiv.style.width = '100%';
    gridDiv.style.height = data.height || '400px';
    el.appendChild(gridDiv);

    function tryInit() {
      if (typeof agGrid === 'undefined') { setTimeout(tryInit, 100); return; }
      // Ensure gridDiv is in the document before creating grid
      if (!gridDiv.isConnected) { setTimeout(tryInit, 50); return; }
      var colDefs = data.columnDefs;
      if (!colDefs && data.columns) {
        colDefs = data.columns.map(function (c) {
          var def = { field: c, headerName: c };
          var ct = (data.columnTypes || {})[c];
          if (ct) def.cellDataType = ct;
          return def;
        });
      }
      var gridConfig = {
        columnDefs: colDefs || [],
        rowData: data.rowData || [],
        defaultColDef: {
          sortable: true, filter: true, resizable: true,
          flex: 1, minWidth: 100
        },
        animateRows: false,
        suppressColumnVirtualisation: false
      };
      if (data.gridOptions) {
        for (var k in data.gridOptions) {
          if (data.gridOptions.hasOwnProperty(k)) gridConfig[k] = data.gridOptions[k];
        }
      }
      var opts = window.PYWRY_AGGRID_BUILD_OPTIONS
        ? window.PYWRY_AGGRID_BUILD_OPTIONS(gridConfig, gridId)
        : gridConfig;
      agGrid.createGrid(gridDiv, opts);
    }
    tryInit();
  }

  function renderPlotlyArtifact(el, data) {
    var chartId = 'pywry-chat-plotly-' + (++__artifactCounter);
    var chartDiv = document.createElement('div');
    chartDiv.id = chartId;
    chartDiv.className = 'pywry-plotly';
    chartDiv.style.width = '100%';
    chartDiv.style.height = data.height || '400px';
    el.appendChild(chartDiv);

    function tryInit() {
      if (typeof Plotly === 'undefined') { setTimeout(tryInit, 100); return; }
      if (!chartDiv.isConnected) { setTimeout(tryInit, 50); return; }
      var fig = data.figure || {};
      var layout = fig.layout || {};
      var templates = window.PYWRY_PLOTLY_TEMPLATES || {};
      if (!layout.template) {
        layout.template = templates['plotly_dark'] || null;
      } else if (typeof layout.template === 'object') {
        // User provided custom template - merge with dark theme base (user wins)
        var base = templates['plotly_dark'] || {};
        layout.template = window.__pywryDeepMerge ? window.__pywryDeepMerge(base, layout.template) : layout.template;
      }
      layout.autosize = true;
      fig.layout = layout;

      var config = fig.config || { displaylogo: false, responsive: true, displayModeBar: 'hover' };
      Plotly.newPlot(chartDiv, fig.data || [], fig.layout, config).then(function (gd) {
        if (window.registerPyWryChart) window.registerPyWryChart(chartId, gd);
      });
    }
    tryInit();
  }

  function renderImageArtifact(el, data) {
    var url = data.url || '';
    // Only allow safe URL schemes — block javascript: and data: text/html
    if (/^\s*javascript\s*:/i.test(url)) return;
    var img = document.createElement('img');
    img.className = 'pywry-chat-artifact-image';
    img.src = url;
    img.alt = escapeHtml(data.alt || data.title || 'Image');
    img.style.maxWidth = '100%';
    img.style.borderRadius = 'var(--pywry-radius, 4px)';
    el.appendChild(img);
  }

  function renderJsonArtifact(el, data) {
    var body = document.createElement('pre');
    body.className = 'pywry-chat-artifact-content pywry-chat-artifact-json';
    var code = document.createElement('code');
    try {
      code.innerHTML = highlightJson(JSON.stringify(data.data, null, 2));
    } catch (e) {
      code.textContent = String(data.data);
    }
    body.appendChild(code);
    el.appendChild(body);
  }

  function renderTradingViewArtifact(el, data) {
    var chartId = 'pywry-chat-tv-' + (++__artifactCounter);
    var chartDiv = document.createElement('div');
    chartDiv.id = chartId;
    chartDiv.className = 'pywry-tradingview';
    chartDiv.style.height = data.height || '400px';
    chartDiv.style.width = '100%';
    el.appendChild(chartDiv);

    function tryInit() {
      if (typeof LightweightCharts === 'undefined') {
        setTimeout(tryInit, 100);
        return;
      }
      var opts = Object.assign({
        layout: { background: { color: '#1e1e2e' }, textColor: '#cdd6f4' },
        grid: { vertLines: { color: '#313244' }, horzLines: { color: '#313244' } },
        crosshair: { mode: 0 },
        timeScale: { borderColor: '#45475a', timeVisible: true },
        rightPriceScale: { borderColor: '#45475a' }
      }, data.options || {});

      var chart = LightweightCharts.createChart(chartDiv, opts);

      (data.series || []).forEach(function (s) {
        var series;
        switch (s.type) {
          case 'candlestick': series = chart.addCandlestickSeries(s.options || {}); break;
          case 'line':        series = chart.addLineSeries(s.options || {}); break;
          case 'area':        series = chart.addAreaSeries(s.options || {}); break;
          case 'bar':         series = chart.addBarSeries(s.options || {}); break;
          case 'baseline':    series = chart.addBaselineSeries(s.options || {}); break;
          case 'histogram':   series = chart.addHistogramSeries(s.options || {}); break;
          default:            series = chart.addLineSeries(s.options || {}); break;
        }
        if (series) {
          series.setData(s.data || []);
          if (s.markers) series.setMarkers(s.markers);
        }
      });

      chart.timeScale().fitContent();

      new ResizeObserver(function () {
        chart.applyOptions({ width: chartDiv.clientWidth });
      }).observe(chartDiv);
    }
    tryInit();
  }

  // Artifact — multi-type artifact rendering (collapsible)
  pywry.on('chat:artifact', function (data) {
    if (!chatArea) return;
    var el = document.createElement('div');
    var safeType = (data.artifactType || 'code').replace(/[^a-z0-9-]/gi, '');
    el.className = 'pywry-chat-artifact pywry-chat-artifact-' + safeType;

    // Collapsible header with chevron
    var headerEl = document.createElement('div');
    headerEl.className = 'pywry-chat-artifact-header';
    headerEl.innerHTML =
      '<span class="pywry-chat-artifact-chevron">&#9660;</span>' +
      '<span class="pywry-chat-artifact-icon">&#128196;</span> ' +
      '<span class="pywry-chat-artifact-title">' + escapeHtml(data.title || data.artifactType || 'Artifact') + '</span>';
    el.appendChild(headerEl);

    // Body wrapper for collapse toggle
    var bodyWrap = document.createElement('div');
    bodyWrap.className = 'pywry-chat-artifact-body';
    el.appendChild(bodyWrap);

    var type = data.artifactType || 'code';
    if (type === 'code') renderCodeArtifact(bodyWrap, data);
    else if (type === 'markdown') renderMarkdownArtifact(bodyWrap, data);
    else if (type === 'html') renderHtmlArtifact(bodyWrap, data);
    else if (type === 'app') renderAppArtifact(bodyWrap, data);
    else if (type === 'table') renderTableArtifact(bodyWrap, data);
    else if (type === 'plotly') renderPlotlyArtifact(bodyWrap, data);
    else if (type === 'image') renderImageArtifact(bodyWrap, data);
    else if (type === 'json') renderJsonArtifact(bodyWrap, data);
    else if (type === 'tradingview') renderTradingViewArtifact(bodyWrap, data);
    else renderCodeArtifact(bodyWrap, data);

    // Toggle collapse on header click
    headerEl.addEventListener('click', function () {
      var collapsed = el.classList.toggle('pywry-chat-artifact-collapsed');
      headerEl.querySelector('.pywry-chat-artifact-chevron').innerHTML = collapsed ? '&#9654;' : '&#9660;';
    });

    chatArea.appendChild(el);
    maybeAutoScroll();
  });

  // Todo list — collapsible task list above the input bar
  pywry.on('chat:todo-update', function (data) {
    if (!todoEl) return;
    var items = data.items || [];

    if (items.length === 0) {
      todoEl.innerHTML = '';
      todoEl.style.display = 'none';
      return;
    }

    var completed = items.filter(function (t) { return t.status === 'completed'; }).length;
    var inProgress = items.filter(function (t) { return t.status === 'in-progress'; }).length;
    var total = items.length;
    var allDone = completed === total;
    var pct = Math.round((completed / total) * 100);

    var summaryLabel = allDone
      ? 'All tasks completed (' + total + '/' + total + ')'
      : (inProgress > 0
        ? 'Working... (' + completed + '/' + total + ' done)'
        : 'Tasks (' + completed + '/' + total + ' done)');

    var html = '<details class="pywry-chat-todo-details"' + (allDone ? '' : ' open') + '>'
      + '<summary class="pywry-chat-todo-summary">'
      + '<span class="pywry-chat-todo-label">' + escapeHtml(summaryLabel) + '</span>'
      + '<div class="pywry-chat-todo-actions">'
      + '<div class="pywry-chat-todo-progress"><div class="pywry-chat-todo-progress-fill" style="width:' + pct + '%"></div></div>'
      + '<button class="pywry-chat-todo-clear" data-tooltip="Clear tasks">&times;</button>'
      + '</div>'
      + '</summary>'
      + '<ul class="pywry-chat-todo-list">';

    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var icon = item.status === 'completed'
        ? '<span class="pywry-chat-todo-icon pywry-chat-todo-done">&#10003;</span>'
        : item.status === 'in-progress'
          ? '<span class="pywry-chat-todo-icon pywry-chat-todo-active">&#9654;</span>'
          : '<span class="pywry-chat-todo-icon">&#9679;</span>';
      var cls = 'pywry-chat-todo-item'
        + (item.status === 'completed' ? ' pywry-chat-todo-item-done' : '')
        + (item.status === 'in-progress' ? ' pywry-chat-todo-item-active' : '');
      html += '<li class="' + cls + '">' + icon + '<span>' + escapeHtml(item.title || '') + '</span></li>';
    }

    html += '</ul></details>';
    todoEl.innerHTML = html;
    todoEl.style.display = 'block';

    // Wire up clear button
    var clearBtn = todoEl.querySelector('.pywry-chat-todo-clear');
    if (clearBtn) {
      clearBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        pywry.emit('chat:todo-clear', {});
      });
    }
  });

  // Input required — agent pauses to request user input mid-stream
  // Compatible with OpenAI API confirmations and MCP A2A input_required.
  // Supports three input types:
  //   "text"    — re-enable textarea for free-form input (default)
  //   "buttons" — inline button row (e.g. Yes/No) in chat area
  //   "radio"   — vertical radio select + submit button in chat area
  pywry.on('chat:input-required', function (data) {
    // End streaming visual state if still active
    if (state.isStreaming) {
      stopStreaming(false);
    }

    var inputType = data.inputType || 'text';
    var options = data.options || [];

    // Show prompt as a question element in the chat area
    if (data.prompt && chatArea) {
      var promptEl = document.createElement('div');
      promptEl.className = 'pywry-chat-input-prompt';
      promptEl.innerHTML = '<span class="pywry-chat-input-prompt-icon">?</span>'
        + '<span>' + escapeHtml(data.prompt) + '</span>';
      chatArea.appendChild(promptEl);
      maybeAutoScroll();
    }

    state.inputRequiredRequestId = data.requestId;

    // Helper: send the user's choice back to the handler
    function submitInputResponse(text) {
      // Show choice as user message
      var irMsgId = 'msg_' + Math.random().toString(36).substring(2, 10);
      var irMsg = {
        id: irMsgId,
        role: 'user',
        text: text,
        threadId: state.activeThreadId,
        stopped: false
      };
      state.messages.push(irMsg);
      appendMessageToDOM(irMsg);

      pywry.emit('chat:input-response', {
        requestId: state.inputRequiredRequestId,
        text: text,
        threadId: state.activeThreadId
      });

      state.inputRequiredRequestId = null;

      // Remove inline controls from chat area
      var controls = chatArea && chatArea.querySelector('.pywry-chat-ir-controls');
      if (controls) controls.remove();

      // Reset input bar
      var bar = inputEl && inputEl.closest('.pywry-chat-input-bar');
      if (bar) bar.classList.remove('pywry-chat-input-required');
    }

    if (inputType === 'buttons') {
      // Render inline button row in chat area
      var btnGroup = document.createElement('div');
      btnGroup.className = 'pywry-chat-ir-controls pywry-chat-ir-buttons';
      var btnLabels = options.length > 0 ? options : ['Yes', 'No'];
      btnLabels.forEach(function (label) {
        var btn = document.createElement('button');
        btn.className = 'pywry-chat-ir-btn';
        btn.textContent = label;
        btn.addEventListener('click', function () {
          submitInputResponse(label);
        });
        btnGroup.appendChild(btn);
      });
      if (chatArea) {
        chatArea.appendChild(btnGroup);
        maybeAutoScroll();
      }
      // Disable textarea — interaction is via buttons
      if (inputEl) inputEl.disabled = true;

    } else if (inputType === 'radio') {
      // Render vertical radio list + submit button in chat area
      var radioGroup = document.createElement('div');
      radioGroup.className = 'pywry-chat-ir-controls pywry-chat-ir-radio-group';
      var radioName = 'pywry_ir_' + (data.requestId || 'radio');
      options.forEach(function (opt, idx) {
        var label = document.createElement('label');
        label.className = 'pywry-chat-ir-radio-item';
        var radio = document.createElement('input');
        radio.type = 'radio';
        radio.name = radioName;
        radio.value = opt;
        radio.className = 'pywry-chat-ir-radio-input';
        if (idx === 0) radio.checked = true;
        label.appendChild(radio);
        var span = document.createElement('span');
        span.className = 'pywry-chat-ir-radio-label';
        span.textContent = opt;
        label.appendChild(span);
        radioGroup.appendChild(label);
      });
      var submitBtn = document.createElement('button');
      submitBtn.className = 'pywry-chat-ir-btn pywry-chat-ir-radio-submit';
      submitBtn.textContent = 'Submit';
      submitBtn.addEventListener('click', function () {
        var checked = radioGroup.querySelector('input[type=radio]:checked');
        submitInputResponse(checked ? checked.value : (options[0] || ''));
      });
      radioGroup.appendChild(submitBtn);
      if (chatArea) {
        chatArea.appendChild(radioGroup);
        maybeAutoScroll();
      }
      // Disable textarea — interaction is via radio
      if (inputEl) inputEl.disabled = true;

    } else {
      // Text mode — re-enable textarea with accent border
      if (inputEl) {
        inputEl.placeholder = data.placeholder || 'Type your response...';
        inputEl.disabled = false;
        inputEl.focus();
      }
      var bar = inputEl && inputEl.closest('.pywry-chat-input-bar');
      if (bar) bar.classList.add('pywry-chat-input-required');
    }
  });

  // =========================================================================
  // DOM Event Wiring
  // =========================================================================

  // Enter to send, Shift+Enter for newline, arrows for palette navigation
  inputEl.addEventListener('keydown', function (e) {
    var paletteVisible = cmdPalette && cmdPalette.style.display === 'block';
    var items = paletteVisible ? cmdPalette.querySelectorAll('.pywry-chat-cmd-item') : [];

    if (paletteVisible && items.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        var next = cmdPaletteIndex < items.length - 1 ? cmdPaletteIndex + 1 : 0;
        setCmdPaletteActive(next);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        var prev = cmdPaletteIndex > 0 ? cmdPaletteIndex - 1 : items.length - 1;
        setCmdPaletteActive(prev);
        return;
      }
      if (e.key === 'Enter' && !e.shiftKey && cmdPaletteIndex >= 0) {
        e.preventDefault();
        var activeItem = items[cmdPaletteIndex];
        if (activeItem) {
          var strong = activeItem.querySelector('strong');
          if (strong) selectPaletteItem(strong.textContent);
        }
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        hideCommandPalette();
        return;
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  // Auto-resize + slash palette
  inputEl.addEventListener('input', function () {
    autoResizeInput(this);
    var val = this.value;
    if (val.startsWith('/') && val.indexOf(' ') === -1) {
      showCommandPalette(val.toLowerCase());
    } else {
      hideCommandPalette();
    }
  });

  // Send button
  if (sendBtnEl) {
    sendBtnEl.addEventListener('click', handleSend);
  }

  // Conversation picker toggle
  if (convBtnEl) {
    convBtnEl.addEventListener('click', function (e) {
      e.stopPropagation();
      toggleConvDropdown();
    });
  }

  // New thread button
  var newBtn = $('#pywry-chat-new-thread');
  if (newBtn) {
    newBtn.addEventListener('click', function () {
      closeConvDropdown();
      closeSettingsMenu();
      pywry.emit('chat:thread-create', { title: 'New Chat' });
    });
  }

  // Settings toggle — opens dropdown menu
  var settingsToggle = $('#pywry-chat-settings-toggle');
  if (settingsToggle) {
    settingsToggle.addEventListener('click', function (e) {
      e.stopPropagation();
      toggleSettingsMenu();
    });
  }

  // Fullscreen toggle
  var fullscreenBtn = $('#pywry-chat-fullscreen-btn');
  if (fullscreenBtn) {
    fullscreenBtn.addEventListener('click', function () {
      var chat = queryRoot.classList && queryRoot.classList.contains('pywry-chat')
        ? queryRoot
        : queryRoot.querySelector('.pywry-chat');
      if (!chat) return;
      var isFullscreen = chat.classList.toggle('pywry-chat-fullscreen');
      var expandIcon = fullscreenBtn.querySelector('.pywry-chat-fullscreen-expand');
      var collapseIcon = fullscreenBtn.querySelector('.pywry-chat-fullscreen-collapse');
      if (expandIcon) expandIcon.style.display = isFullscreen ? 'none' : '';
      if (collapseIcon) collapseIcon.style.display = isFullscreen ? '' : 'none';
      fullscreenBtn.setAttribute('data-tooltip', isFullscreen ? 'Exit full width' : 'Toggle full width');
    });
  }

  // Edit / resend / retry buttons on message bubbles (delegated)
  if (chatArea) {
    chatArea.addEventListener('click', function (e) {
      var btn = e.target && e.target.closest && e.target.closest('.pywry-chat-msg-action');
      if (!btn) return;
      var msgEl = btn.closest('.pywry-chat-msg');
      if (!msgEl) return;
      var msgId = msgEl.getAttribute('data-msg-id') || '';
      if (!msgId) return;
      var action = btn.getAttribute('data-action');

      if (action === 'edit') {
        startEditingMessage(msgEl, msgId);
      } else if (action === 'resend') {
        emitResend(msgId);
      }
    });
  }

  function emitResend(messageId) {
    if (!pywry || !pywry.emit) return;
    pywry.emit('chat:resend-from', {
      messageId: messageId,
      threadId: state.activeThreadId,
    });
  }

  function startEditingMessage(msgEl, msgId) {
    if (msgEl.classList.contains('pywry-chat-msg-editing')) return;
    var contentEl = msgEl.querySelector('.pywry-chat-msg-content');
    if (!contentEl) return;
    // Find the underlying text from state.messages — content has been markdown-rendered
    var msgObj = null;
    for (var i = 0; i < state.messages.length; i++) {
      if (state.messages[i].id === msgId) { msgObj = state.messages[i]; break; }
    }
    var originalText = msgObj ? (msgObj.text || '') : (contentEl.textContent || '');
    msgEl.classList.add('pywry-chat-msg-editing');

    var ta = document.createElement('textarea');
    ta.className = 'pywry-chat-msg-edit-textarea';
    ta.value = originalText;
    ta.rows = Math.max(2, Math.min(10, originalText.split('\n').length + 1));

    var actionsEl = msgEl.querySelector('.pywry-chat-msg-actions');
    var savedActionsHtml = actionsEl ? actionsEl.innerHTML : '';
    var savedContentHtml = contentEl.innerHTML;
    contentEl.innerHTML = '';
    contentEl.appendChild(ta);
    ta.focus();
    ta.setSelectionRange(ta.value.length, ta.value.length);

    if (actionsEl) {
      actionsEl.innerHTML =
        '<button class="pywry-chat-msg-action" data-edit-action="save" data-tooltip="Save and resend">Save &amp; Resend</button>' +
        '<button class="pywry-chat-msg-action" data-edit-action="cancel" data-tooltip="Cancel edit">Cancel</button>';
    }

    function cancel() {
      contentEl.innerHTML = savedContentHtml;
      if (actionsEl) actionsEl.innerHTML = savedActionsHtml;
      msgEl.classList.remove('pywry-chat-msg-editing');
    }

    function save() {
      var newText = ta.value.trim();
      if (!newText) { cancel(); return; }
      msgEl.classList.remove('pywry-chat-msg-editing');
      // Restore the original markdown render of the new text immediately
      contentEl.innerHTML = renderMarkdown(newText);
      if (actionsEl) actionsEl.innerHTML = savedActionsHtml;
      // Update state.messages too
      if (msgObj) msgObj.text = newText;
      if (pywry && pywry.emit) {
        pywry.emit('chat:edit-message', {
          messageId: msgId,
          threadId: state.activeThreadId,
          text: newText,
        });
      }
    }

    if (actionsEl) {
      actionsEl.addEventListener('click', function (ev) {
        var btn = ev.target && ev.target.closest && ev.target.closest('[data-edit-action]');
        if (!btn) return;
        ev.stopPropagation();
        if (btn.getAttribute('data-edit-action') === 'save') save();
        else cancel();
      });
    }
    ta.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') { ev.preventDefault(); cancel(); }
      else if (ev.key === 'Enter' && (ev.metaKey || ev.ctrlKey)) { ev.preventDefault(); save(); }
    });
  }

  // Scroll badge
  if (chatArea) {
    var __scrollTimer = null;
    chatArea.addEventListener('scroll', function () {
      var nearBottom = (chatArea.scrollHeight - chatArea.scrollTop - chatArea.clientHeight) < __PYWRY_CHAT_SCROLL_THRESHOLD;
      if (nearBottom) {
        state.userScrolledUp = false;
        if (badgeEl) badgeEl.style.display = 'none';
      } else {
        // Debounce: only set userScrolledUp after scroll settles
        // This prevents programmatic scrolls from triggering the flag
        clearTimeout(__scrollTimer);
        __scrollTimer = setTimeout(function () {
          var still = (chatArea.scrollHeight - chatArea.scrollTop - chatArea.clientHeight) >= __PYWRY_CHAT_SCROLL_THRESHOLD;
          if (still) state.userScrolledUp = true;
        }, 150);
      }
    });
  }
  if (badgeEl) {
    badgeEl.addEventListener('click', function () {
      state.userScrolledUp = false;
      if (chatArea) chatArea.scrollTop = chatArea.scrollHeight;
      badgeEl.style.display = 'none';
    });
  }

  // Click outside closes all dropdowns
  eventRoot.addEventListener('click', function (e) {
    if (convPickerEl && !convPickerEl.contains(e.target)) {
      closeConvDropdown();
    }
    if (settingsMenuEl && !settingsMenuEl.contains(e.target)) {
      closeSettingsMenu();
    }
    if (cmdPalette && !cmdPalette.contains(e.target) && e.target !== inputEl) {
      hideCommandPalette();
    }
  });

  // =========================================================================
  // Context / Attachment handlers
  // =========================================================================

  var __PYWRY_MAX_ATTACHMENTS = 20;

  // Accepted file types from developer config (data attribute on container)
  var __PYWRY_ACCEPT_TYPES = (function () {
    var raw = queryRoot.getAttribute && queryRoot.getAttribute('data-accept-types') || '';
    if (!raw) return null;
    return raw.split(',').map(function (t) { return t.trim().toLowerCase(); });
  })();

  function isAcceptedFile(filename) {
    if (!__PYWRY_ACCEPT_TYPES) return false;
    var dot = filename.lastIndexOf('.');
    if (dot < 0) return false;
    var ext = filename.substring(dot).toLowerCase();
    return __PYWRY_ACCEPT_TYPES.indexOf(ext) !== -1;
  }

  // Extract just the filename from a full path
  function pathBasename(fullPath) {
    var sep = fullPath.lastIndexOf('/');
    var backslash = fullPath.lastIndexOf('\\');
    var idx = Math.max(sep, backslash);
    return idx >= 0 ? fullPath.substring(idx + 1) : fullPath;
  }

  function renderAttachmentPills() {
    if (!attachBarEl) return;
    if (state.attachments.length === 0) {
      attachBarEl.style.display = 'none';
      attachBarEl.innerHTML = '';
      return;
    }
    attachBarEl.style.display = 'flex';
    var html = '';
    for (var i = 0; i < state.attachments.length; i++) {
      var att = state.attachments[i];
      var icon = att.type === 'widget' ? '@' : '\u{1F4CE}';
      html += '<span class="pywry-chat-attachment-pill" data-idx="' + i + '">' +
        '<span class="pywry-chat-attachment-pill-icon">' + icon + '</span>' +
        '<span class="pywry-chat-attachment-pill-name">' + escapeHtml(att.name) + '</span>' +
        '<button class="pywry-chat-attachment-pill-remove" data-idx="' + i + '">&times;</button>' +
        '</span>';
    }
    attachBarEl.innerHTML = html;

    // Bind remove buttons
    var removeBtns = attachBarEl.querySelectorAll('.pywry-chat-attachment-pill-remove');
    for (var j = 0; j < removeBtns.length; j++) {
      removeBtns[j].addEventListener('click', function (e) {
        e.stopPropagation();
        var idx = parseInt(this.getAttribute('data-idx'), 10);
        state.attachments.splice(idx, 1);
        renderAttachmentPills();
      });
    }
  }

  function addFileAttachment(filePath) {
    if (state.attachments.length >= __PYWRY_MAX_ATTACHMENTS) return;
    var name = pathBasename(filePath);
    if (!isAcceptedFile(name)) return;
    // Prevent duplicates
    var exists = state.attachments.some(function (a) {
      return a.type === 'file' && a.path === filePath;
    });
    if (exists) return;
    state.attachments.push({
      type: 'file',
      name: name,
      path: filePath
    });
    renderAttachmentPills();
  }

  // Browser fallback — used when __TAURI__ is not available (inline/iframe mode)
  function addBrowserFileAttachment(file) {
    if (state.attachments.length >= __PYWRY_MAX_ATTACHMENTS) return;
    if (!isAcceptedFile(file.name)) return;
    // Prevent duplicates by name (no path in browser)
    var exists = state.attachments.some(function (a) {
      return a.type === 'file' && a.name === file.name;
    });
    if (exists) return;
    var reader = new FileReader();
    reader.onload = function () {
      state.attachments.push({
        type: 'file',
        name: file.name,
        content: reader.result
      });
      renderAttachmentPills();
    };
    reader.readAsText(file);
  }

  function addWidgetAttachment(source) {
    if (state.attachments.length >= __PYWRY_MAX_ATTACHMENTS) return;
    // Prevent duplicates
    var exists = state.attachments.some(function (a) {
      return a.type === 'widget' && a.widgetId === source.id;
    });
    if (exists) return;
    state.attachments.push({
      type: 'widget',
      name: source.name,
      widgetId: source.id,
      componentId: source.componentId || ''
    });
    renderAttachmentPills();
  }

  // --- Attach button — opens native Tauri file dialog, or falls back to browser input ---
  if (attachBtnEl) {
    attachBtnEl.addEventListener('click', function (e) {
      e.stopPropagation();

      // Tauri desktop — use native file dialog (returns full filesystem paths)
      if (window.__TAURI__ && window.__TAURI__.dialog) {
        var filters = [];
        if (__PYWRY_ACCEPT_TYPES) {
          var exts = __PYWRY_ACCEPT_TYPES.map(function (t) {
            return t.replace(/^\./, '');
          });
          filters.push({ name: 'Allowed files', extensions: exts });
        }
        window.__TAURI__.dialog.open({
          multiple: true,
          filters: filters.length > 0 ? filters : undefined
        }).then(function (selected) {
          if (!selected) return;
          var paths = Array.isArray(selected) ? selected : [selected];
          for (var i = 0; i < paths.length; i++) {
            addFileAttachment(paths[i]);
          }
        }).catch(function (err) {
          console.warn('[PyWry] File dialog error:', err);
        });
        return;
      }

      // Browser fallback — use hidden <input type="file">
      var input = document.createElement('input');
      input.type = 'file';
      input.multiple = true;
      if (__PYWRY_ACCEPT_TYPES) {
        input.accept = __PYWRY_ACCEPT_TYPES.join(',');
      }
      input.style.display = 'none';
      input.addEventListener('change', function () {
        var files = input.files || [];
        for (var j = 0; j < files.length; j++) {
          addBrowserFileAttachment(files[j]);
        }
        input.remove();
      });
      document.body.appendChild(input);
      input.click();
    });
  }

  // --- Drag and drop ---
  if (dropOverlayEl) {
    if (window.__TAURI__ && window.__TAURI__.event) {
      // Tauri desktop — listen for native drag-drop events (full paths)
      window.__TAURI__.event.listen('tauri://drag-over', function () {
        dropOverlayEl.style.display = 'flex';
      });
      window.__TAURI__.event.listen('tauri://drag-leave', function () {
        dropOverlayEl.style.display = 'none';
      });
      window.__TAURI__.event.listen('tauri://drag-drop', function (event) {
        dropOverlayEl.style.display = 'none';
        var paths = event.payload && event.payload.paths ? event.payload.paths : [];
        for (var i = 0; i < paths.length; i++) {
          addFileAttachment(paths[i]);
        }
      });
    } else {
      // Browser fallback — HTML5 drag-and-drop (reads file content)
      var chatEl = container;
      chatEl.addEventListener('dragenter', function (e) {
        e.preventDefault();
        e.stopPropagation();
        dropOverlayEl.style.display = 'flex';
      });
      chatEl.addEventListener('dragover', function (e) {
        e.preventDefault();
        e.stopPropagation();
      });
      chatEl.addEventListener('dragleave', function (e) {
        e.preventDefault();
        e.stopPropagation();
        // Only hide if leaving the container entirely
        if (!chatEl.contains(e.relatedTarget)) {
          dropOverlayEl.style.display = 'none';
        }
      });
      chatEl.addEventListener('drop', function (e) {
        e.preventDefault();
        e.stopPropagation();
        dropOverlayEl.style.display = 'none';
        var files = e.dataTransfer && e.dataTransfer.files ? e.dataTransfer.files : [];
        for (var k = 0; k < files.length; k++) {
          addBrowserFileAttachment(files[k]);
        }
      });
    }
  }

  // --- @mention popup ---

  function removeTypedMention() {
    if (!mentionPopupEl || !inputEl) return;
    var mentionStart = typeof mentionPopupEl.__mentionStart === 'number'
      ? mentionPopupEl.__mentionStart
      : -1;
    if (mentionStart < 0) return;

    var value = inputEl.value || '';
    var mentionEnd = mentionStart + 1;
    while (mentionEnd < value.length && /[\w\s]/.test(value.charAt(mentionEnd))) {
      mentionEnd++;
    }

    var before = value.substring(0, mentionStart);
    var after = value.substring(mentionEnd);
    inputEl.value = before + after;
    inputEl.selectionStart = inputEl.selectionEnd = before.length;
    mentionPopupEl.__mentionStart = -1;
  }

  // Helper: show the mention popup with all (or filtered) context sources
  function showMentionPopup(query) {
    if (!mentionPopupEl || state.contextSources.length === 0) return;
    var q = (query || '').toLowerCase();
    var filtered = state.contextSources.filter(function (s) {
      return s.name.toLowerCase().indexOf(q) !== -1;
    });
    if (filtered.length === 0) {
      mentionPopupEl.style.display = 'none';
      return;
    }
    var html = '';
    for (var i = 0; i < filtered.length; i++) {
      html += '<div class="pywry-chat-mention-item" data-idx="' + i + '">' +
        '<span class="pywry-chat-mention-icon">@</span>' +
        '<span>' + escapeHtml(filtered[i].name) + '</span>' +
        '</div>';
    }
    mentionPopupEl.innerHTML = html;
    mentionPopupEl.style.display = 'block';
    mentionPopupEl.__filtered = filtered;

    // Bind click handlers on items
    var items = mentionPopupEl.querySelectorAll('.pywry-chat-mention-item');
    for (var j = 0; j < items.length; j++) {
      items[j].addEventListener('click', function () {
        var idx = parseInt(this.getAttribute('data-idx'), 10);
        var source = mentionPopupEl.__filtered[idx];
        addWidgetAttachment(source);
        removeTypedMention();
        mentionPopupEl.style.display = 'none';
        inputEl.focus();
      });
    }
  }

  // Typing @ in the input
  if (mentionPopupEl && inputEl) {
    inputEl.addEventListener('input', function () {
      var val = inputEl.value;
      var cursorPos = inputEl.selectionStart || 0;

      // Find @ that starts a mention (preceded by start or whitespace)
      var textBefore = val.substring(0, cursorPos);
      var mentionMatch = textBefore.match(/(?:^|\s)@([\w\s]*)$/);

      if (mentionMatch && state.contextSources.length > 0) {
        mentionPopupEl.__mentionStart = textBefore.lastIndexOf('@');
        showMentionPopup(mentionMatch[1]);
      } else {
        mentionPopupEl.style.display = 'none';
      }
    });
  }

  // Close popup when clicking outside
  document.addEventListener('click', function (e) {
    if (mentionPopupEl && mentionPopupEl.style.display === 'block') {
      if (!mentionPopupEl.contains(e.target)) {
        mentionPopupEl.style.display = 'none';
      }
    }
  });

  // --- Context sources from backend ---
  pywry.on('chat:context-sources', function (data) {
    state.contextSources = data.sources || [];
  });

  // --- ACP: Permission request ---
  pywry.on('chat:permission-request', function (data) {
    if (!chatArea) return;
    var el = document.createElement('div');
    el.className = 'pywry-chat-permission-request';
    el.innerHTML =
      '<div class="pywry-chat-permission-title">' + escapeHtml(data.title || 'Permission required') + '</div>' +
      '<div class="pywry-chat-permission-actions"></div>';
    var actions = el.querySelector('.pywry-chat-permission-actions');
    (data.options || []).forEach(function (opt) {
      var btn = document.createElement('button');
      btn.className = 'pywry-chat-permission-btn pywry-chat-permission-btn-' + (opt.id || '').replace(/[^a-z_]/gi, '');
      btn.textContent = opt.label || opt.id;
      btn.addEventListener('click', function () {
        pywry.emit('chat:permission-response', {
          requestId: data.requestId,
          optionId: opt.id,
          threadId: data.threadId
        });
        el.remove();
      });
      actions.appendChild(btn);
    });
    chatArea.appendChild(el);
    maybeAutoScroll();
  });

  // --- ACP: Plan update ---
  // Reuses the styled ``pywry-chat-todo-*`` classes so the plan card
  // gets the same collapsible details/summary + progress bar look as
  // the agent-driven todo list.  (The plan and todo renderers share
  // one container — ``#pywry-chat-todo`` — and one stylesheet; using
  // separate ``pywry-chat-plan-*`` classes here would produce
  // unstyled markup and the card would appear to never render.)
  pywry.on('chat:plan-update', function (data) {
    if (!todoEl) return;
    var entries = data.entries || [];
    if (entries.length === 0) {
      todoEl.innerHTML = '';
      todoEl.style.display = 'none';
      return;
    }

    var total = entries.length;
    var completed = 0;
    var inProgress = 0;
    for (var ci = 0; ci < entries.length; ci++) {
      var st = entries[ci].status;
      if (st === 'completed') completed += 1;
      else if (st === 'in_progress') inProgress += 1;
    }
    var allDone = completed === total && total > 0;
    var pct = total > 0 ? Math.round((completed / total) * 100) : 0;
    var summaryLabel = allDone
      ? 'All tasks completed (' + total + '/' + total + ')'
      : (inProgress > 0
        ? 'Working... (' + completed + '/' + total + ' done)'
        : 'Plan (' + completed + '/' + total + ' done)');

    var html = '<details class="pywry-chat-todo-details"' + (allDone ? '' : ' open') + '>'
      + '<summary class="pywry-chat-todo-summary">'
      + '<span class="pywry-chat-todo-label">' + escapeHtml(summaryLabel) + '</span>'
      + '<div class="pywry-chat-todo-actions">'
      + '<div class="pywry-chat-todo-progress"><div class="pywry-chat-todo-progress-fill" style="width:' + pct + '%"></div></div>'
      + '</div>'
      + '</summary>'
      + '<ul class="pywry-chat-todo-list">';
    entries.forEach(function (e) {
      var status = e.status || 'pending';
      var icon = status === 'completed'
        ? '<span class="pywry-chat-todo-icon pywry-chat-todo-done">&#10003;</span>'
        : status === 'in_progress'
          ? '<span class="pywry-chat-todo-icon pywry-chat-todo-active">&#9654;</span>'
          : '<span class="pywry-chat-todo-icon">&#9679;</span>';
      var cls = 'pywry-chat-todo-item'
        + (status === 'completed' ? ' pywry-chat-todo-item-done' : '')
        + (status === 'in_progress' ? ' pywry-chat-todo-item-active' : '');
      html += '<li class="' + cls + '">' + icon +
        '<span>' + escapeHtml(e.content || '') + '</span></li>';
    });
    html += '</ul></details>';
    todoEl.innerHTML = html;
    todoEl.style.display = 'block';
  });

  // --- ACP: Mode update ---
  pywry.on('chat:mode-update', function (data) {
    // Store mode state for settings panel rendering
    state.currentModeId = data.currentModeId || '';
    state.availableModes = data.availableModes || [];
  });

  // --- ACP: Config option update ---
  pywry.on('chat:config-update', function (data) {
    // Store config options for settings panel rendering
    state.configOptions = data.options || [];
  });

  // --- ACP: Commands update ---
  pywry.on('chat:commands-update', function (data) {
    var commands = data.commands || [];
    state.slashCommands = [];
    commands.forEach(function (cmd) {
      var cmdName = cmd.name.charAt(0) === '/' ? cmd.name : '/' + cmd.name;
      state.slashCommands.push({ name: cmdName, description: cmd.description || '' });
    });
  });

  // =========================================================================
  // Done — render initial state
  // =========================================================================
  renderSettingsMenu();
  renderThreadList();

  // Request initial state from backend
  pywry.emit('chat:request-state', {});
}
