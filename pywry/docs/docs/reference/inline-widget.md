# InlineWidget

The `InlineWidget` class powers browser-based rendering in PyWry. It starts a FastAPI server and serves widgets via IFrame or direct HTML, enabling Jupyter notebooks, browser tabs, and multi-user deploy mode.

```python
from pywry.inline import InlineWidget
```

---

## InlineWidget Class

::: pywry.inline.InlineWidget
    options:
      show_root_heading: true
      heading_level: 2
      members: true

---

## Helper Functions

### show

::: pywry.inline.show
    options:
      show_root_heading: true
      heading_level: 4

### show_plotly

::: pywry.inline.show_plotly
    options:
      show_root_heading: true
      heading_level: 4

### show_dataframe

::: pywry.inline.show_dataframe
    options:
      show_root_heading: true
      heading_level: 4

---

## Server Functions

### block

::: pywry.inline.block
    options:
      show_root_heading: true
      heading_level: 4

### deploy

::: pywry.inline.deploy
    options:
      show_root_heading: true
      heading_level: 4

### get_server_app

::: pywry.inline.get_server_app
    options:
      show_root_heading: true
      heading_level: 4

### get_widget_html

::: pywry.inline.get_widget_html
    options:
      show_root_heading: true
      heading_level: 4

### get_widget_html_async

::: pywry.inline.get_widget_html_async
    options:
      show_root_heading: true
      heading_level: 4

### stop_server

::: pywry.inline.stop_server
    options:
      show_root_heading: true
      heading_level: 4

---

## URL & HTML Generation

::: pywry.inline.get_widget_url
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.inline.generate_plotly_html
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.inline.generate_dataframe_html
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.inline.generate_dataframe_html_from_config
    options:
      show_root_heading: true
      heading_level: 2
