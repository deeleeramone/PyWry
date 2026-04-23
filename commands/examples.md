---
description: List bundled PyWry examples or run one headlessly and report its output.
argument-hint: "[example-name]"
---

If `$ARGUMENTS` is empty:

List every script in the PyWry examples directory. For each, print `<filename> — <one‑line description from the script's module docstring>`. Find the examples directory by running `python -c "import pywry, os; print(os.path.join(os.path.dirname(pywry.__file__), '..', 'examples'))"` and listing `*.py` files there (or fall back to `./pywry/examples/` if running from the repo).

If `$ARGUMENTS` names an example:

1. Verify the file exists (case‑insensitive match on filename stem).
2. Run it with `PYWRY_HEADLESS=1 python <path>` and a 20‑second timeout.
3. Capture stdout and stderr.
4. Report: exit code, a summary of any widget IDs created (parse from stdout), and the last 40 lines of output.

Do not modify the example file. Do not `pip install` anything. If the example requires an extra (e.g. `pywry[openai]`, `pywry[anthropic]`), surface the `ImportError` and tell the user which extra to install.
