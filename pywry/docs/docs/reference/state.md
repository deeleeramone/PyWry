# pywry.state

State management interfaces and implementations.

---

## Factory Functions

::: pywry.state.get_widget_store
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.get_event_bus
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.get_connection_router
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.get_session_store
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.get_callback_registry
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.get_worker_id
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.get_state_backend
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.is_deploy_mode
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.clear_state_caches
    options:
      show_root_heading: true
      heading_level: 2

---

## Abstract Interfaces

::: pywry.state.WidgetStore
    options:
      show_root_heading: true
      heading_level: 2
      members_order: source

::: pywry.state.EventBus
    options:
      show_root_heading: true
      heading_level: 2
      members_order: source

::: pywry.state.ConnectionRouter
    options:
      show_root_heading: true
      heading_level: 2
      members_order: source

::: pywry.state.SessionStore
    options:
      show_root_heading: true
      heading_level: 2
      members_order: source

---

## Data Types

::: pywry.state.WidgetData
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.EventMessage
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.ConnectionInfo
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.UserSession
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.StateBackend
    options:
      show_root_heading: true
      heading_level: 2

---

## Callback Registry

::: pywry.state.CallbackRegistry
    options:
      show_root_heading: true
      heading_level: 2
      members_order: source

::: pywry.state.reset_callback_registry
    options:
      show_root_heading: true
      heading_level: 2

---

## Memory Implementations

::: pywry.state.MemoryWidgetStore
    options:
      show_root_heading: true
      heading_level: 2
      inherited_members: false

::: pywry.state.MemoryEventBus
    options:
      show_root_heading: true
      heading_level: 2
      inherited_members: false

::: pywry.state.MemoryConnectionRouter
    options:
      show_root_heading: true
      heading_level: 2
      inherited_members: false

::: pywry.state.MemorySessionStore
    options:
      show_root_heading: true
      heading_level: 2
      inherited_members: false

---

## Server State

::: pywry.state.ServerStateManager
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.get_server_state
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.reset_server_state
    options:
      show_root_heading: true
      heading_level: 2

---

## Sync Helpers

::: pywry.state.run_async
    options:
      show_root_heading: true
      heading_level: 2

::: pywry.state.run_async_fire_and_forget
    options:
      show_root_heading: true
      heading_level: 2

---

## Additional Types

::: pywry.state.callbacks.CallbackRegistration
    options:
      show_root_heading: true
      heading_level: 2
      members: true

---

## Memory Store Factory

::: pywry.state.memory.create_memory_stores
    options:
      show_root_heading: true
      heading_level: 2
