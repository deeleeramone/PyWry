# Toast Stylesheet

Source: `frontend/style/toast.css` — Toast notification styling with five types, four positions, and a blocking overlay for confirmations.

---

## Container

```css
.pywry-toast-container { /* Fixed-position container — holds all active toasts */ }
.pywry-toast-container--top-right { /* Top right (default) */ }
.pywry-toast-container--top-left { /* Top left */ }
.pywry-toast-container--bottom-right { /* Bottom right */ }
.pywry-toast-container--bottom-left { /* Bottom left */ }
.pywry-toast-container--blocking { /* Blocking variant — disables background interaction */ }
```

---

## Toast

```css
.pywry-toast { /* Individual toast — backdrop blur, accent left border */ }
```

### Type Variants

Each type sets `--pywry-toast-accent` to a unique color for the left border:

```css
.pywry-toast--info { /* Info — blue (#0ea5e9) */ }
.pywry-toast--success { /* Success — green (#22c55e) */ }
.pywry-toast--warning { /* Warning — amber (#f59e0b) */ }
.pywry-toast--error { /* Error — red (#ef4444) */ }
.pywry-toast--confirm { /* Confirm — indigo (#6366f1) */ }
```

### Theme

```css
.pywry-toast--light { /* Light theme variant — inverted shadows and borders */ }
```

---

## Inner Elements

```css
.pywry-toast__icon { /* Icon element (emoji or SVG) */ }
.pywry-toast__content { /* Content wrapper (title + message) */ }
.pywry-toast__title { /* Title text — bold */ }
.pywry-toast__message { /* Message text — secondary color */ }
.pywry-toast__close { /* Close button (×) */ }
```

---

## Confirm Buttons

Used by the `confirm` toast type:

```css
.pywry-toast__buttons { /* Button group container */ }
.pywry-toast__btn { /* Base button */ }
.pywry-toast__btn--cancel { /* Cancel button */ }
.pywry-toast__btn--confirm { /* Confirm button — accent color background */ }
```

---

## Blocking Overlay

When a `confirm` toast is shown with `blocking=True`, a semi-transparent overlay covers the page:

```css
.pywry-toast-overlay { /* Overlay element (hidden by default) */ }
.pywry-toast-overlay--visible { /* Visible state — covers viewport */ }
```
