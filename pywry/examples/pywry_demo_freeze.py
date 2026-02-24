"""Minimal PyWry app that can be built as a standalone distributable.

No special code is required — pywry handles frozen executable detection
automatically when imported.

Build with PyInstaller (recommended ``--onedir`` for best startup time)::

    pip install pywry[freeze]
    pyinstaller --windowed --name MyApp pywry_demo_freeze.py

Build with Nuitka::

    pip install nuitka
    nuitka --standalone --include-package=pywry pywry_demo_freeze.py

The output directory (``dist/MyApp/``) is fully self-contained and can
be distributed to machines that have no Python installation.

System requirements for the target machine:
- Windows: WebView2 runtime (pre-installed on Windows 10 1803+ / 11)
- Linux: libwebkit2gtk-4.1
- macOS: None (WKWebView is built-in)
"""

from pywry import PyWry, WindowMode


app = PyWry(mode=WindowMode.SINGLE_WINDOW, title="Standalone App")
app.show(
    """
    <html>
    <body style="background:#1e1e1e; color:white; font-family:sans-serif;
                 display:flex; align-items:center; justify-content:center;
                 height:100vh; margin:0;">
      <div style="text-align:center;">
        <h1>Hello from a distributable executable!</h1>
        <p style="color:#888;">No Python installation required on the target machine.</p>
      </div>
    </body>
    </html>
    """
)
app.block()
