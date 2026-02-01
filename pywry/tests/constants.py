"""Shared test constants and configuration.

Centralizes timeouts, retry counts, and other test configuration values
to ensure consistency across the test suite.
"""

# =============================================================================
# Timeout Constants (seconds)
# =============================================================================

# Default timeout for window operations
DEFAULT_TIMEOUT: float = 10.0

# Short timeout for quick operations
SHORT_TIMEOUT: float = 5.0

# Extended timeout for slow operations (e.g., first window creation)
EXTENDED_TIMEOUT: float = 30.0

# Timeout for WebSocket connections
WEBSOCKET_TIMEOUT: float = 5.0

# Timeout for HTTP requests
HTTP_TIMEOUT: float = 5.0

# Brief delay for cleanup between tests
CLEANUP_DELAY: float = 0.5

# Delay for subprocess termination (Windows WebView2 needs longer to fully cleanup)
SUBPROCESS_TERMINATION_DELAY: float = 1.5


# =============================================================================
# Retry Configuration
# =============================================================================

# Number of retries for flaky operations (e.g., subprocess failures)
DEFAULT_RETRIES: int = 3

# Delay between retry attempts
RETRY_DELAY: float = 1.0

# Retries for JavaScript result waiting
JS_RESULT_RETRIES: int = 3


# =============================================================================
# Server Configuration
# =============================================================================

# Default port for test server
DEFAULT_TEST_PORT: int = 8765

# Port range start for unique port allocation
PORT_RANGE_START: int = 10000

# Port range offset for finding free ports
PORT_RANGE_OFFSET: int = 100


# =============================================================================
# Redis Test Configuration
# =============================================================================

# Default Redis TTL for test sessions
REDIS_TEST_TTL: int = 60

# Redis container image
REDIS_IMAGE: str = "redis:7"

# Redis alpine image for lighter tests
REDIS_ALPINE_IMAGE: str = "redis:7-alpine"


# =============================================================================
# Test Data Limits
# =============================================================================

# Maximum rows for test DataFrames
MAX_TEST_ROWS: int = 100

# Maximum columns for test DataFrames
MAX_TEST_COLUMNS: int = 10
