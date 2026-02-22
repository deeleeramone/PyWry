"""Configuration system for PyWry using pydantic-settings.

Supports layered configuration:
1. Built-in defaults (lowest priority)
2. pyproject.toml [tool.pywry] section (project-level)
3. ./pywry.toml (project-level, explicit)
4. ~/.config/pywry/config.toml (user-level, overrides project)
5. Environment variables (highest priority)

Environment variables use PYWRY_ prefix with nested delimiter __.
Example: PYWRY_CSP__CONNECT_SRC, PYWRY_TIMEOUT__STARTUP
"""

# pylint: disable=too-many-lines

from __future__ import annotations

import os
import sys

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, ClassVar, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[import-not-found]
    except ImportError:
        tomllib = None


def _find_config_files() -> list[Path]:
    """Find all configuration files in order of precedence (lowest first)."""
    files = []

    # Project-level pyproject.toml [tool.pywry] (lowest file priority)
    pyproject = Path("pyproject.toml")
    if pyproject.exists():
        files.append(pyproject)

    # Explicit pywry.toml (project-level)
    pywry_toml = Path("pywry.toml")
    if pywry_toml.exists():
        files.append(pywry_toml)

    # User-level config (overrides project configs)
    if sys.platform == "win32":
        user_config = Path(os.environ.get("APPDATA", "~")) / "pywry" / "config.toml"
    else:
        user_config = Path("~/.config/pywry/config.toml")
    user_config = user_config.expanduser()
    if user_config.exists():
        files.append(user_config)

    # Environment variable override for config file (highest file priority)
    env_config = os.environ.get("PYWRY_CONFIG_FILE")
    if env_config:
        env_path = Path(env_config)
        if env_path.exists():
            files.append(env_path)

    return files


def _load_toml_config() -> dict[str, Any]:
    """Load and merge all TOML configuration files."""
    if tomllib is None:
        return {}

    merged: dict[str, Any] = {}

    for config_file in _find_config_files():
        try:
            content = config_file.read_text(encoding="utf-8")
            data = tomllib.loads(content)

            # Handle pyproject.toml [tool.pywry] section
            if config_file.name == "pyproject.toml":
                data = data.get("tool", {}).get("pywry", {})

            # Deep merge
            merged = _deep_merge(merged, data)
        except Exception:
            pass  # Silently ignore invalid config files

    return merged


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# Field names that contain sensitive data and must be redacted in output.
_SENSITIVE_FIELDS: set[str] = {
    "client_secret",
    "ssl_keyfile_password",
    "internal_api_token",
    "redis_url",
}

_REDACTED = "********"


class SecuritySettings(BaseSettings):
    """Content Security Policy settings.

    Environment prefix: PYWRY_CSP__
    Example: PYWRY_CSP__CONNECT_SRC="'self' https://api.example.com"
    """

    model_config = SettingsConfigDict(
        env_prefix="PYWRY_CSP__",
        extra="ignore",
    )

    default_src: str = "'self' 'unsafe-inline' 'unsafe-eval' data: blob:"
    connect_src: str = "'self' http://*:* https://*:* ws://*:* wss://*:* data: blob:"
    script_src: str = "'self' 'unsafe-inline' 'unsafe-eval'"
    style_src: str = "'self' 'unsafe-inline'"
    img_src: str = "'self' http://*:* https://*:* data: blob:"
    font_src: str = "'self' data:"

    def build_csp(self) -> str:
        """Build the complete CSP meta tag content."""
        directives = [
            f"default-src {self.default_src}",
            f"connect-src {self.connect_src}",
            f"script-src {self.script_src}",
            f"style-src {self.style_src}",
            f"img-src {self.img_src}",
            f"font-src {self.font_src}",
        ]
        return "; ".join(directives)

    @classmethod
    def permissive(cls) -> SecuritySettings:
        """Create permissive CSP settings for development mode."""
        return cls()

    @classmethod
    def strict(cls) -> SecuritySettings:
        """Create strict CSP settings for production mode.

        Removes unsafe-eval, restricts to self and specific CDNs.
        """
        return cls(
            default_src="'self' 'unsafe-inline' data: blob:",
            connect_src="'self' data: blob:",
            script_src="'self' 'unsafe-inline'",
            style_src="'self' 'unsafe-inline'",
            img_src="'self' data: blob:",
            font_src="'self' data:",
        )

    @classmethod
    def localhost(cls, ports: list[int] | None = None) -> SecuritySettings:
        """Create localhost-only CSP settings.

        Parameters
        ----------
        ports : list of int or None, optional
            Specific ports to allow. If None, allows all localhost ports.

        Returns
        -------
        SecuritySettings
            Configured security settings for localhost.
        """
        if ports:
            port_list = " ".join(
                f"http://localhost:{p} http://127.0.0.1:{p} ws://localhost:{p} ws://127.0.0.1:{p}"
                for p in ports
            )
            connect = f"'self' {port_list} data: blob:"
        else:
            connect = (
                "'self' http://localhost:* http://127.0.0.1:* "
                "ws://localhost:* ws://127.0.0.1:* data: blob:"
            )

        return cls(
            default_src="'self' 'unsafe-inline' data: blob:",
            connect_src=connect,
            script_src="'self' 'unsafe-inline'",
            style_src="'self' 'unsafe-inline'",
            img_src="'self' http://localhost:* http://127.0.0.1:* data: blob:",
            font_src="'self' data:",
        )


class ThemeSettings(BaseSettings):
    """Theme and styling settings.

    Controls the visual appearance of PyWry windows and widgets.
    The mode setting determines light/dark theme behavior.

    Environment prefix: PYWRY_THEME__
    Example: PYWRY_THEME__MODE=dark
    Example: PYWRY_THEME__CSS_FILE=/path/to/custom.css
    """

    model_config = SettingsConfigDict(
        env_prefix="PYWRY_THEME__",
        extra="ignore",
    )

    mode: Literal["system", "dark", "light"] = Field(
        default="system",
        description="Theme mode: 'system' follows browser/OS preference, 'dark' or 'light' forces theme",
    )
    css_file: str | None = Field(
        default=None,
        description="Path to external CSS file for custom styling",
    )


class TimeoutSettings(BaseSettings):
    """Timeout settings for IPC and subprocess.

    Environment prefix: PYWRY_TIMEOUT__
    Example: PYWRY_TIMEOUT__STARTUP=15.0
    """

    model_config = SettingsConfigDict(
        env_prefix="PYWRY_TIMEOUT__",
        extra="ignore",
    )

    startup: float = Field(default=10.0, ge=1.0, description="Subprocess ready timeout in seconds")
    response: float = Field(default=5.0, ge=0.5, description="IPC response timeout in seconds")
    create_window: float = Field(
        default=5.0, ge=0.5, description="Window creation timeout in seconds"
    )
    set_content: float = Field(default=5.0, ge=0.5, description="Content update timeout in seconds")
    shutdown: float = Field(default=2.0, ge=0.5, description="Graceful shutdown timeout in seconds")


class AssetSettings(BaseSettings):
    """Asset and library settings.

    Environment prefix: PYWRY_ASSET__
    Example: PYWRY_ASSET__PLOTLY_VERSION="3.4.0"
    """

    model_config = SettingsConfigDict(
        env_prefix="PYWRY_ASSET__",
        extra="ignore",
    )

    # Library versions
    plotly_version: str = "3.3.1"
    aggrid_version: str = "35.0.0"

    # Custom asset directory
    path: str = ""

    # Default CSS/JS files to load
    css_files: list[str] = Field(default_factory=list)
    script_files: list[str] = Field(default_factory=list)

    @field_validator("css_files", "script_files", mode="before")
    @classmethod
    def parse_comma_separated(cls, v: Any) -> list[str]:
        """Parse comma-separated strings from env vars."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v or []


class LogSettings(BaseSettings):
    """Logging settings.

    Environment prefix: PYWRY_LOG__
    Example: PYWRY_LOG__LEVEL=DEBUG
    """

    model_config = SettingsConfigDict(
        env_prefix="PYWRY_LOG__",
        extra="ignore",
    )

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "WARNING"
    format: str = "%(name)s - %(levelname)s - %(message)s"


class WindowSettings(BaseSettings):
    """Default window settings.

    These settings correspond to WindowConfig fields and are used
    when creating native windows via the window manager.

    Environment prefix: PYWRY_WINDOW__
    Example: PYWRY_WINDOW__TITLE="My App"
    """

    model_config = SettingsConfigDict(
        env_prefix="PYWRY_WINDOW__",
        extra="ignore",
    )

    # Window basics
    title: str = "PyWry"
    width: int = Field(default=1280, ge=200, description="Window width in pixels")
    height: int = Field(default=720, ge=150, description="Window height in pixels")
    min_width: int = Field(default=400, ge=100, description="Minimum window width")
    min_height: int = Field(default=300, ge=100, description="Minimum window height")

    # Window behavior
    center: bool = Field(default=True, description="Center window on screen")
    resizable: bool = Field(default=True, description="Allow window resizing")
    decorations: bool = Field(
        default=True, description="Show window decorations (title bar, borders)"
    )
    always_on_top: bool = Field(default=False, description="Keep window above others")
    devtools: bool = Field(default=False, description="Open developer tools on start")
    allow_network: bool = Field(default=True, description="Allow network requests")

    # Window close behavior
    on_window_close: Literal["hide", "close"] = Field(
        default="hide",
        description="What happens when user clicks X: 'hide' keeps window alive, 'close' destroys it",
    )

    # Library integration
    enable_plotly: bool = Field(default=False, description="Include Plotly.js in window")
    enable_aggrid: bool = Field(default=False, description="Include AG Grid in window")
    plotly_theme: Literal[
        "plotly", "plotly_white", "plotly_dark", "ggplot2", "seaborn", "simple_white"
    ] = Field(default="plotly_dark", description="Default Plotly theme")
    aggrid_theme: Literal["quartz", "alpine", "balham", "material"] = Field(
        default="alpine", description="Default AG Grid theme"
    )


class HotReloadSettings(BaseSettings):
    """Hot reload settings.

    Environment prefix: PYWRY_HOT_RELOAD__
    Example: PYWRY_HOT_RELOAD__ENABLED=true
    """

    model_config = SettingsConfigDict(
        env_prefix="PYWRY_HOT_RELOAD__",
        extra="ignore",
    )

    enabled: bool = False
    debounce_ms: int = Field(
        default=100, ge=10, description="Debounce time for file changes in milliseconds"
    )
    css_reload: Literal["inject", "refresh"] = "inject"  # CSS: hot-swap or full reload
    script_reload: Literal["refresh"] = "refresh"  # JS: always full reload
    preserve_scroll: bool = True
    watch_directories: list[str] = Field(default_factory=list)

    @field_validator("watch_directories", mode="before")
    @classmethod
    def parse_comma_separated(cls, v: Any) -> list[str]:
        """Parse comma-separated strings from env vars."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v or []


class DeploySettings(BaseSettings):
    """Deploy mode settings for scalable production deployments.

    Deploy mode is activated when both PYWRY_HEADLESS=1 and a state backend
    is configured. This enables horizontal scaling with Redis for state storage.

    Environment prefix: PYWRY_DEPLOY__
    Example: PYWRY_DEPLOY__STATE_BACKEND=redis
    Example: PYWRY_DEPLOY__REDIS_URL=redis://redis:6379/0
    """

    model_config = SettingsConfigDict(
        env_prefix="PYWRY_DEPLOY__",
        extra="ignore",
    )

    # State backend configuration
    state_backend: Literal["memory", "redis"] = Field(
        default="memory",
        description=(
            "State storage backend: 'memory' (single process) or 'redis' (distributed). "
            "Redis enables multi-worker horizontal scaling."
        ),
    )

    # Redis connection settings
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description=(
            "Redis connection URL. Supports standard redis:// and redis+sentinel:// schemes. "
            "Examples: 'redis://host:port/db', 'redis://:password@host:port/db'"
        ),
    )
    redis_prefix: str = Field(
        default="pywry",
        description="Key prefix for all Redis keys (namespace isolation)",
    )
    redis_pool_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Redis connection pool size per store",
    )

    # TTL settings (seconds)
    widget_ttl: int = Field(
        default=86400,  # 24 hours
        ge=60,
        description="Widget data TTL in seconds (auto-deleted after expiry)",
    )
    connection_ttl: int = Field(
        default=300,  # 5 minutes
        ge=30,
        description="Connection routing TTL in seconds (refresh on heartbeat)",
    )
    session_ttl: int = Field(
        default=86400,  # 24 hours
        ge=60,
        description="User session TTL in seconds",
    )

    # Worker identification
    worker_id: str | None = Field(
        default=None,
        description=(
            "Unique worker identifier for connection routing. "
            "Auto-generated if None (recommended for most deployments)."
        ),
    )

    # Authentication settings
    auth_enabled: bool = Field(
        default=False,
        description="Enable user authentication and session management",
    )
    auth_session_cookie: str = Field(
        default="pywry_session",
        description="Name of the session cookie for authentication",
    )
    auth_header: str = Field(
        default="Authorization",
        description="HTTP header for bearer token authentication",
    )

    # RBAC settings
    default_roles: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["viewer"],
        description="Default roles assigned to new users",
    )
    admin_users: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description="List of user IDs with admin privileges",
    )

    @field_validator("default_roles", "admin_users", mode="before")
    @classmethod
    def parse_comma_separated(cls, v: Any) -> list[str]:
        """Parse comma-separated strings from env vars."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v or []

    # OAuth2 integration
    oauth2_login_path: str = Field(
        default="/auth/login",
        description="Path for the OAuth2 login endpoint in deploy mode",
    )
    oauth2_callback_path: str = Field(
        default="/auth/callback",
        description="Path for the OAuth2 callback endpoint in deploy mode",
    )
    auth_public_paths: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["/auth/login", "/auth/callback", "/auth/status"],
        description="Paths that do not require authentication (pre-auth routes)",
    )

    # Security: explicit redirect URI and HTTPS enforcement
    auth_redirect_uri: str = Field(
        default="",
        description=(
            "Explicit OAuth2 redirect URI for deploy mode. "
            "When set, overrides request-derived Host header to prevent poisoning. "
            "Example: https://myapp.example.com/auth/callback"
        ),
    )
    force_https: bool = Field(
        default=False,
        description=(
            "Enforce HTTPS for redirect URIs and cookies in deploy mode. "
            "Should be True in production. When False, allows localhost HTTP for development."
        ),
    )

    @field_validator("auth_public_paths", mode="before")
    @classmethod
    def parse_public_paths(cls, v: Any) -> list[str]:
        """Parse comma-separated strings from env vars."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v or []


class OAuth2Settings(BaseSettings):
    """OAuth2 authentication configuration.

    Environment prefix: PYWRY_OAUTH2__
    Example: PYWRY_OAUTH2__CLIENT_ID=your-client-id
    Example: PYWRY_OAUTH2__PROVIDER=google

    TOML section: [tool.pywry.oauth2]
    """

    model_config = SettingsConfigDict(
        env_prefix="PYWRY_OAUTH2__",
        extra="ignore",
    )

    # Provider selection
    provider: Literal["google", "github", "microsoft", "oidc", "custom"] = Field(
        default="custom",
        description="OAuth2 provider type: google, github, microsoft, oidc, or custom",
    )

    # Client credentials
    client_id: str = Field(
        default="",
        description="OAuth2 client ID from the provider",
    )
    client_secret: str = Field(
        default="",
        description="OAuth2 client secret (empty for public clients with PKCE)",
    )

    # Scopes
    scopes: str = Field(
        default="openid email profile",
        description="Space-separated OAuth2 scopes to request",
    )

    # Endpoint URLs (required for custom/oidc providers)
    authorize_url: str = Field(
        default="",
        description="Authorization endpoint URL (required for custom provider)",
    )
    token_url: str = Field(
        default="",
        description="Token exchange endpoint URL (required for custom provider)",
    )
    userinfo_url: str = Field(
        default="",
        description="User info endpoint URL (optional)",
    )
    issuer_url: str = Field(
        default="",
        description="OIDC issuer URL for auto-discovery (used by oidc provider)",
    )

    # Provider-specific
    tenant_id: str = Field(
        default="common",
        description="Azure AD tenant ID (for Microsoft provider)",
    )

    # PKCE
    use_pkce: bool = Field(
        default=True,
        description="Use PKCE (Proof Key for Code Exchange) for public clients",
    )

    # Token storage
    token_store_backend: Literal["memory", "keyring", "redis"] = Field(
        default="memory",
        description="Token storage backend: memory, keyring, or redis",
    )

    # Timeouts
    auth_timeout_seconds: float = Field(
        default=120.0,
        ge=10.0,
        description="Maximum seconds to wait for OAuth2 callback",
    )
    refresh_buffer_seconds: int = Field(
        default=60,
        ge=10,
        description="Seconds before token expiry to trigger background refresh",
    )

    @field_validator("client_id")
    @classmethod
    def validate_custom_provider(cls, v: str, info: Any) -> str:  # pylint: disable=unused-argument
        """Validate that required fields are set for custom providers."""
        # Validation happens at usage time rather than init time
        # to allow partial configuration via env vars
        return v


class ServerSettings(BaseSettings):
    """Inline server settings for notebook/web mode.

    Exposes full uvicorn configuration for deployment.

    Environment prefix: PYWRY_SERVER__
    Example: PYWRY_SERVER__PORT=8080
    """

    model_config = SettingsConfigDict(
        env_prefix="PYWRY_SERVER__",
        extra="ignore",
    )

    # Core server settings
    host: str = Field(default="127.0.0.1", description="Server bind address")
    port: int = Field(default=8765, ge=1, le=65535, description="Server port")
    widget_prefix: str = Field(
        default="/widget",
        description="URL prefix for widget routes (e.g., '/widget' -> /widget/{id})",
    )
    auto_start: bool = Field(default=True, description="Auto-start server when needed")
    force_notebook: bool = Field(
        default=False,
        description="Force notebook mode even in headless environments (for web deployments)",
    )

    # Uvicorn settings
    workers: int = Field(default=1, ge=1, description="Number of worker processes")
    log_level: Literal["critical", "error", "warning", "info", "debug", "trace"] = Field(
        default="info", description="Uvicorn log level"
    )
    access_log: bool = Field(default=True, description="Enable access logging")
    reload: bool = Field(default=False, description="Enable auto-reload (dev mode)")

    # Timeouts
    timeout_keep_alive: int = Field(default=5, ge=0, description="Keep-alive timeout in seconds")
    timeout_graceful_shutdown: int | None = Field(
        default=None, description="Graceful shutdown timeout (None = wait forever)"
    )

    # SSL/TLS settings (for HTTPS)
    ssl_keyfile: str | None = Field(default=None, description="SSL key file path")
    ssl_certfile: str | None = Field(default=None, description="SSL certificate file path")
    ssl_keyfile_password: str | None = Field(default=None, description="SSL key file password")
    ssl_ca_certs: str | None = Field(default=None, description="CA certificates file")

    # CORS settings - use NoDecode to disable JSON parsing and use our validator
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["*"], description="Allowed CORS origins"
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow credentials in CORS")
    cors_allow_methods: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["*"], description="Allowed CORS methods"
    )
    cors_allow_headers: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["*"], description="Allowed CORS headers"
    )

    # Limits
    limit_concurrency: int | None = Field(default=None, description="Max concurrent connections")
    limit_max_requests: int | None = Field(
        default=None, description="Max requests before worker restart"
    )
    backlog: int = Field(default=2048, ge=1, description="Socket backlog size")

    # WebSocket security settings
    websocket_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description="List of allowed origins for WebSocket connections. Empty list allows any origin (rely on token auth only). Examples: ['http://localhost:8080', 'https://app.example.com']",
    )
    websocket_require_token: bool = Field(
        default=True,
        description="Require per-widget authentication token for WebSocket connections. Each widget gets a unique short-lived token embedded in its HTML.",
    )

    # Internal API security - protects internal endpoints from external access
    internal_api_header: str = Field(
        default="X-PyWry-Token",
        description="Header name for internal API authentication.",
    )
    internal_api_token: str | None = Field(
        default=None,
        description="Token for internal API access. If None, auto-generated on server start. Required for /register_widget, /disconnect, /health endpoints.",
    )
    strict_widget_auth: bool = Field(
        default=False,
        description="If True, /widget/{id} endpoint also requires internal API header (browser mode). If False, only checks widget exists (notebook mode, allows iframes).",
    )

    @field_validator(
        "cors_origins",
        "cors_allow_methods",
        "cors_allow_headers",
        "websocket_allowed_origins",
        mode="before",
    )
    @classmethod
    def parse_comma_separated(cls, v: Any) -> list[str]:
        """Parse comma-separated strings from env vars."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v or []


class MCPSettings(BaseSettings):
    """MCP (Model Context Protocol) server settings.

    Controls the MCP server for AI agent integration using FastMCP.
    The MCP server manages its own runtime (native windows or headless mode) and state.

    Environment prefix: PYWRY_MCP__
    Example: PYWRY_MCP__TRANSPORT=sse
    Example: PYWRY_MCP__PORT=8001
    Example: PYWRY_MCP__HEADLESS=false
    """

    model_config = SettingsConfigDict(
        env_prefix="PYWRY_MCP__",
        extra="ignore",
    )

    # Server identity
    name: str = Field(
        default="pywry-widgets",
        description="MCP server name (advertised to clients)",
    )
    version: str | None = Field(
        default=None,
        description="Server version string (auto-detected from package if None)",
    )
    instructions: str | None = Field(
        default=None,
        description="Server instructions shown to AI agents describing capabilities",
    )

    # Transport settings
    transport: Literal["stdio", "sse", "streamable-http"] = Field(
        default="stdio",
        description="Transport type: 'stdio' for CLI/Claude Desktop, 'sse' or 'streamable-http' for HTTP",
    )
    host: str = Field(
        default="127.0.0.1",
        description="Host for HTTP transports (SSE/streamable-http)",
    )
    port: int = Field(
        default=8001,
        ge=1,
        le=65535,
        description="Port for HTTP transports",
    )

    # HTTP endpoint paths (FastMCP)
    sse_path: str = Field(
        default="/sse",
        description="SSE endpoint path (for SSE transport)",
    )
    message_path: str = Field(
        default="/messages/",
        description="Message endpoint path (for SSE transport)",
    )
    streamable_http_path: str = Field(
        default="/mcp",
        description="Streamable HTTP endpoint path (for streamable-http transport)",
    )

    # HTTP behavior (FastMCP)
    json_response: bool = Field(
        default=False,
        description="Return JSON instead of SSE for HTTP transports",
    )
    stateless_http: bool = Field(
        default=False,
        description="Enable stateless HTTP mode (no session management)",
    )

    # Validation and error handling (FastMCP)
    strict_input_validation: bool = Field(
        default=False,
        description="Enable stricter JSON schema validation for tool inputs",
    )
    mask_error_details: bool = Field(
        default=False,
        description="Hide detailed error messages in production (show generic errors)",
    )
    debug: bool = Field(
        default=False,
        description="Enable FastMCP debug mode (verbose logging, detailed errors)",
    )

    # Tool filtering (FastMCP)
    include_tags: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description="Only expose tools with these tags (empty = all tools)",
    )
    exclude_tags: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description="Exclude tools with these tags",
    )

    # Rendering mode
    headless: bool = Field(
        default=False,
        description=(
            "Run in headless mode (inline widgets via browser) or desktop mode (native windows). "
            "Can also be set via PYWRY_HEADLESS environment variable."
        ),
    )

    # Widget management
    widget_ttl: int = Field(
        default=0,
        ge=0,
        description="Widget auto-cleanup TTL in seconds (0 = disabled, widgets persist until destroyed)",
    )
    max_widgets: int = Field(
        default=100,
        ge=1,
        description="Maximum number of concurrent widgets",
    )
    event_buffer_size: int = Field(
        default=1000,
        ge=10,
        description="Maximum events buffered per widget before oldest are dropped",
    )

    # Window defaults (for native mode)
    default_width: int = Field(
        default=800,
        ge=200,
        description="Default window width for new widgets",
    )
    default_height: int = Field(
        default=600,
        ge=150,
        description="Default window height for new widgets",
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="MCP server log level",
    )
    log_tools: bool = Field(
        default=False,
        description="Log tool calls and results for debugging",
    )

    # Skills and prompts
    skills_auto_load: bool = Field(
        default=True,
        description="Auto-load skill documents when agents connect",
    )

    @field_validator("include_tags", "exclude_tags", mode="before")
    @classmethod
    def parse_comma_separated(cls, v: Any) -> list[str]:
        """Parse comma-separated strings from env vars."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v or []


# All Tauri plugins supported by the bundled pytauri_wheel.
# Maps plugin name -> (feature flag constant name, module path).
TAURI_PLUGIN_REGISTRY: dict[str, tuple[str, str]] = {
    "autostart": ("PLUGIN_AUTOSTART", "pytauri_plugins.autostart"),
    "clipboard_manager": ("PLUGIN_CLIPBOARD_MANAGER", "pytauri_plugins.clipboard_manager"),
    "deep_link": ("PLUGIN_DEEP_LINK", "pytauri_plugins.deep_link"),
    "dialog": ("PLUGIN_DIALOG", "pytauri_plugins.dialog"),
    "fs": ("PLUGIN_FS", "pytauri_plugins.fs"),
    "global_shortcut": ("PLUGIN_GLOBAL_SHORTCUT", "pytauri_plugins.global_shortcut"),
    "http": ("PLUGIN_HTTP", "pytauri_plugins.http"),
    "notification": ("PLUGIN_NOTIFICATION", "pytauri_plugins.notification"),
    "opener": ("PLUGIN_OPENER", "pytauri_plugins.opener"),
    "os": ("PLUGIN_OS", "pytauri_plugins.os"),
    "persisted_scope": ("PLUGIN_PERSISTED_SCOPE", "pytauri_plugins.persisted_scope"),
    "positioner": ("PLUGIN_POSITIONER", "pytauri_plugins.positioner"),
    "process": ("PLUGIN_PROCESS", "pytauri_plugins.process"),
    "shell": ("PLUGIN_SHELL", "pytauri_plugins.shell"),
    "single_instance": ("PLUGIN_SINGLE_INSTANCE", "pytauri_plugins.single_instance"),
    "updater": ("PLUGIN_UPDATER", "pytauri_plugins.updater"),
    "upload": ("PLUGIN_UPLOAD", "pytauri_plugins.upload"),
    "websocket": ("PLUGIN_WEBSOCKET", "pytauri_plugins.websocket"),
    "window_state": ("PLUGIN_WINDOW_STATE", "pytauri_plugins.window_state"),
}

#: Names of all known Tauri plugins (for validation).
AVAILABLE_TAURI_PLUGINS: frozenset[str] = frozenset(TAURI_PLUGIN_REGISTRY)

#: Default plugins that ship enabled with PyWry.
DEFAULT_TAURI_PLUGINS: list[str] = ["dialog", "fs"]


class PyWrySettings(BaseSettings):
    """Main settings aggregating all configuration sections.

    Environment prefix: PYWRY__

    Configuration sources (in order of precedence):
    1. Built-in defaults
    2. pyproject.toml [tool.pywry] section
    3. ./pywry.toml (project-level)
    4. ~/.config/pywry/config.toml (user-level, overrides project)
    5. Environment variables (highest priority)
    """

    model_config = SettingsConfigDict(
        env_prefix="PYWRY__",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Nested settings
    csp: SecuritySettings = Field(default_factory=SecuritySettings)
    theme: ThemeSettings = Field(default_factory=ThemeSettings)
    timeout: TimeoutSettings = Field(default_factory=TimeoutSettings)
    asset: AssetSettings = Field(default_factory=AssetSettings)
    log: LogSettings = Field(default_factory=LogSettings)
    window: WindowSettings = Field(default_factory=WindowSettings)
    hot_reload: HotReloadSettings = Field(default_factory=HotReloadSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    deploy: DeploySettings = Field(default_factory=DeploySettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    oauth2: OAuth2Settings | None = Field(
        default=None,
        description="OAuth2 authentication settings (None to disable)",
    )

    # Tauri plugin configuration
    tauri_plugins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_TAURI_PLUGINS),
        description=(
            "Tauri plugins to initialise in the native subprocess. "
            "Each name must be one of the 19 plugins bundled in pytauri_wheel "
            "(e.g. 'dialog', 'fs', 'notification', 'http'). "
            "Set via PYWRY_TAURI_PLUGINS env var (comma-separated) or in "
            "pyproject.toml / pywry.toml under [tool.pywry]."
        ),
    )
    extra_capabilities: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description=(
            "Additional Tauri capability permission strings to grant beyond "
            "the auto-generated '<plugin>:default' entries (e.g. "
            "'shell:allow-execute', 'fs:allow-read-file'). "
            "Set via PYWRY_EXTRA_CAPABILITIES env var (comma-separated)."
        ),
    )

    @field_validator("tauri_plugins", mode="before")
    @classmethod
    def _parse_tauri_plugins(cls, v: Any) -> list[str]:
        """Accept a comma-separated string (from env var) or a list."""
        if isinstance(v, str):
            v = [p.strip() for p in v.split(",") if p.strip()]
        if not isinstance(v, list):
            msg = f"tauri_plugins must be a list or comma-separated string, got {type(v).__name__}"
            raise TypeError(msg)
        unknown = set(v) - AVAILABLE_TAURI_PLUGINS
        if unknown:
            msg = (
                f"Unknown Tauri plugin(s): {', '.join(sorted(unknown))}. "
                f"Available: {', '.join(sorted(AVAILABLE_TAURI_PLUGINS))}"
            )
            raise ValueError(msg)
        return v

    @field_validator("extra_capabilities", mode="before")
    @classmethod
    def _parse_extra_capabilities(cls, v: Any) -> list[str]:
        """Accept a comma-separated string (from env var) or a list."""
        if isinstance(v, str):
            v = [p.strip() for p in v.split(",") if p.strip()]
        if not isinstance(v, list):
            msg = f"extra_capabilities must be a list or comma-separated string, got {type(v).__name__}"
            raise TypeError(msg)
        return v

    # Tracks where each value came from (for CLI display)
    _sources: ClassVar[dict[str, str]] = {}

    def __init__(self, **data: Any) -> None:
        # Load TOML configuration first
        toml_config = _load_toml_config()

        # Merge TOML config with explicit data (explicit takes precedence)
        merged = _deep_merge(toml_config, data)

        # Auto-detect OAuth2 env vars: if PYWRY_OAUTH2__CLIENT_ID is set
        # and oauth2 wasn't explicitly provided, instantiate OAuth2Settings
        # so env-var based configuration works out of the box.
        if ("oauth2" not in merged or merged["oauth2"] is None) and os.environ.get(
            "PYWRY_OAUTH2__CLIENT_ID"
        ):
            merged["oauth2"] = OAuth2Settings()

        super().__init__(**merged)

    def to_toml(self) -> str:
        """Export settings as TOML string."""
        lines = ["# PyWry Configuration", "# Generated by: pywry config --toml", ""]

        # Top-level list fields
        tp = "[" + ", ".join(f'"{p}"' for p in self.tauri_plugins) + "]"
        lines.append(f"tauri_plugins = {tp}")
        if self.extra_capabilities:
            ec = "[" + ", ".join(f'"{c}"' for c in self.extra_capabilities) + "]"
            lines.append(f"extra_capabilities = {ec}")
        lines.append("")

        section_names = [
            "csp",
            "theme",
            "timeout",
            "asset",
            "log",
            "window",
            "hot_reload",
            "server",
            "deploy",
            "mcp",
        ]

        if self.oauth2 is not None:
            section_names.append("oauth2")

        all_data = self.model_dump(
            exclude=dict.fromkeys(section_names, _SENSITIVE_FIELDS),
        )

        for section_name in section_names:
            section_data = all_data.get(section_name, {})
            lines.append(f"[{section_name}]")
            for field_name, field_value in section_data.items():
                if isinstance(field_value, list):
                    value_str = "[" + ", ".join(f'"{v}"' for v in field_value) + "]"
                elif isinstance(field_value, bool):
                    value_str = "true" if field_value else "false"
                elif isinstance(field_value, str):
                    value_str = f'"{field_value}"'
                else:
                    value_str = str(field_value)
                lines.append(f"{field_name} = {value_str}")
            # Append redacted placeholders for any sensitive fields defined
            # on this section's model class.
            section_cls = type(getattr(self, section_name))
            lines.extend(
                f'{rn} = "{_REDACTED}"'
                for rn in sorted(_SENSITIVE_FIELDS & section_cls.model_fields.keys())
            )
            lines.append("")

        return "\n".join(lines)

    def to_env(self) -> str:
        """Export settings as shell environment variables."""
        lines = [
            "# PyWry Environment Variables",
            "# Generated by: pywry config --env",
            "",
        ]

        # Top-level list fields
        lines.append(f'export PYWRY_TAURI_PLUGINS="{",".join(self.tauri_plugins)}"')
        if self.extra_capabilities:
            lines.append(f'export PYWRY_EXTRA_CAPABILITIES="{",".join(self.extra_capabilities)}"')
        lines.append("")

        env_sections = [
            ("CSP", "csp"),
            ("THEME", "theme"),
            ("TIMEOUT", "timeout"),
            ("ASSET", "asset"),
            ("LOG", "log"),
            ("WINDOW", "window"),
            ("HOT_RELOAD", "hot_reload"),
            ("SERVER", "server"),
            ("DEPLOY", "deploy"),
            ("MCP", "mcp"),
        ]

        # Dump from top-level model to avoid tainted section instances.
        all_data = self.model_dump(
            exclude={attr: _SENSITIVE_FIELDS for _, attr in env_sections},
        )

        for env_prefix, attr_name in env_sections:
            section_data = all_data.get(attr_name, {})
            for field_name, field_value in section_data.items():
                env_name = f"PYWRY_{env_prefix}__{field_name.upper()}"
                if isinstance(field_value, list):
                    value_str = ",".join(str(v) for v in field_value)
                elif isinstance(field_value, bool):
                    value_str = "true" if field_value else "false"
                else:
                    value_str = str(field_value)
                lines.append(f'export {env_name}="{value_str}"')
            section_cls = type(getattr(self, attr_name))
            for redacted_name in sorted(_SENSITIVE_FIELDS & section_cls.model_fields.keys()):
                env_name = f"PYWRY_{env_prefix}__{redacted_name.upper()}"
                lines.append(f'export {env_name}="{_REDACTED}"')

        return "\n".join(lines)

    def show(self) -> str:
        """Format settings as a readable table."""
        lines = ["PyWry Configuration", "=" * 60, ""]

        show_sections = [
            ("Security (CSP)", "csp"),
            ("Theme", "theme"),
            ("Timeouts", "timeout"),
            ("Assets", "asset"),
            ("Logging", "log"),
            ("Window Defaults", "window"),
            ("Hot Reload", "hot_reload"),
            ("Server (Notebook/Web)", "server"),
            ("Deploy (Scalable)", "deploy"),
            ("MCP (AI Agents)", "mcp"),
        ]

        # Dump from top-level model to avoid tainted section instances.
        all_data = self.model_dump(
            exclude={attr: _SENSITIVE_FIELDS for _, attr in show_sections},
        )

        for display_name, attr_name in show_sections:
            section_data = all_data.get(attr_name, {})
            lines.append(f"\n{display_name}")
            lines.append("-" * 40)
            for field_name, field_value in section_data.items():
                # Truncate long values
                value_str = str(field_value)
                if len(value_str) > 50:
                    value_str = value_str[:47] + "..."
                lines.append(f"  {field_name:20} = {value_str}")
            section_cls = type(getattr(self, attr_name))
            lines.extend(
                f"  {rn:20} = {_REDACTED}"
                for rn in sorted(_SENSITIVE_FIELDS & section_cls.model_fields.keys())
            )

        return "\n".join(lines)


@lru_cache(maxsize=1)
def get_settings() -> PyWrySettings:
    """Get the global settings instance (cached).

    Call clear_settings() to reload configuration.
    """
    return PyWrySettings()


def clear_settings() -> None:
    """Clear the cached settings to force reload."""
    get_settings.cache_clear()


def reload_settings() -> PyWrySettings:
    """Reload settings from all sources."""
    clear_settings()
    return get_settings()
