---
description: Scaffold a minimal PyWry app in a new directory (main.py, pyproject.toml, README.md).
argument-hint: "<app-name> [--kind widget|chat|tvchart|dashboard]"
---

Scaffold a new PyWry app in a fresh directory named by the first positional argument `$ARGUMENTS`. If no argument is given, ask the user for a name.

**Before writing any files**, call the `get_skills` MCP tool with the topic that matches `--kind` (default `widget` → skill `component_reference`, `chat` → `chat`, `tvchart` → `tvchart`, `dashboard` → `data_visualization`). Read the returned skill text before choosing the template.

Then create the following files in `./<app-name>/`:

1. **`main.py`** — a runnable PyWry app using `PyWry().show*(...)` appropriate to `--kind`. Keep it under 40 lines. Use headless‑friendly patterns (no hard‑coded `block()` call at module import level).
2. **`pyproject.toml`** — minimal, pinned to `pywry[mcp]>=2.0.0rc7`. Use the user's Python version.
3. **`README.md`** — one paragraph describing the app and a `python main.py` quick start.
4. **`.gitignore`** — standard Python entries (`__pycache__/`, `*.pyc`, `.venv/`).

After writing files:
- Run `ruff format` on `main.py`
- Print the directory listing
- Tell the user: `cd <app-name> && pip install -e . && PYWRY_HEADLESS=1 python main.py` to run headlessly, or drop `PYWRY_HEADLESS=1` to see the native window

Do **not** install the package or run the app automatically. The user should review the generated code first.
