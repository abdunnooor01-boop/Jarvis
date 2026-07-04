"""Security utilities: headers, input sanitization, environment validation."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# Security Headers
# =============================================================================

SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self' ws: wss:; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "base-uri 'self'; "
        "object-src 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": (
        "camera=(), microphone=(), geolocation=(), "
        "fullscreen=(self), payment=(), usb=(), "
        "magnetometer=(), accelerometer=(), gyroscope=()"
    ),
}


async def add_security_headers(request: Any, call_next: Any) -> Any:
    """ASGI middleware that adds security headers to every response."""
    response = await call_next(request)
    for header_name, header_value in SECURITY_HEADERS.items():
        response.headers[header_name] = header_value
    return response


# =============================================================================
# Input Sanitization
# =============================================================================

# Common prompt injection patterns to strip
PROMPT_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+prompts", re.IGNORECASE),
    re.compile(r"you\s+are\s+(now|not)\s+", re.IGNORECASE),
    re.compile(r"you\s+are\s+a\s+free\s+", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"do\s+not\s+follow\s+", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)", re.IGNORECASE),
    re.compile(r"new\s+instructions?", re.IGNORECASE),
    re.compile(r"override\s+(instructions|prompt)", re.IGNORECASE),
]

MAX_PROMPT_LENGTH = 32_000  # Maximum length of a user message

# Control characters to strip (except common whitespace)
CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def sanitize_prompt(text: str) -> str:
    """Sanitize a user prompt to prevent prompt injection.

    - Strips/neutralizes system prompt override attempts
    - Removes control characters
    - Trims to max length
    - Removes excessive whitespace
    """
    if not isinstance(text, str):
        return ""

    # Remove control characters
    text = CONTROL_CHARS_PATTERN.sub("", text)

    # Strip excessive whitespace (more than 3 consecutive newlines -> 2, more than 2 spaces -> 1)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = re.sub(r" {3,}", "  ", text)

    # Neutralize prompt injection patterns by inserting zero-width space
    for pattern in PROMPT_INJECTION_PATTERNS:
        text = pattern.sub(lambda m: _neutralize_match(m.group(0)), text)

    # Trim to max length
    if len(text) > MAX_PROMPT_LENGTH:
        text = text[:MAX_PROMPT_LENGTH]

    return text.strip()


def _neutralize_match(match: str) -> str:
    """Neutralize a prompt injection match by inserting zero-width spaces."""
    # Insert zero-width space after first word to break the pattern
    words = match.split(" ", 1)
    if len(words) > 1:
        return words[0] + "\u200b" + " " + words[1]
    return match


def sanitize_filename(name: str) -> str:
    """Sanitize a filename to prevent path traversal.

    - Removes path separators (/, \\)
    - Removes null bytes
    - Removes '..' references
    - Replaces unsafe characters
    - Limits length
    """
    if not isinstance(name, str):
        return ""

    # Remove null bytes
    name = name.replace("\x00", "")

    # Remove path separators
    name = name.replace("/", "").replace("\\", "")

    # Remove parent directory references
    name = name.replace("..", "")

    # Replace other unsafe characters with underscore
    unsafe_chars = '<>:"|?*'
    for char in unsafe_chars:
        name = name.replace(char, "_")

    # Trim and limit length
    name = name.strip().strip(". ")
    if not name:
        name = "unnamed"

    return name[:255]


def validate_tool_input(params: dict[str, Any], schema: dict[str, Any]) -> bool:
    """Validate tool parameters against a known schema.

    Args:
        params: The parameters to validate.
        schema: A JSON Schema-like dict defining allowed types and structure.

    Returns:
        True if valid, False otherwise.
    """
    if not isinstance(params, dict) or not isinstance(schema, dict):
        return False

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    # Check all required params are present
    for req in required:
        if req not in params:
            return False

    # Validate each parameter against its schema
    for key, value in params.items():
        if key not in properties:
            continue  # Extra params are allowed (caught by tool implementation)

        prop_schema = properties[key]
        param_type = prop_schema.get("type", "string")

        # Check type
        if param_type == "string" and not isinstance(value, str):
            return False
        if param_type == "integer" and not isinstance(value, int):
            return False
        if param_type == "number" and not isinstance(value, (int, float)):
            return False
        if param_type == "boolean" and not isinstance(value, bool):
            return False
        if param_type == "array" and not isinstance(value, list):
            return False
        if param_type == "object" and not isinstance(value, dict):
            return False

        # Check enum values
        enum_values = prop_schema.get("enum")
        if enum_values is not None and value not in enum_values:
            return False

        # Check min/max length for strings
        if isinstance(value, str):
            max_length = prop_schema.get("maxLength")
            if max_length is not None and len(value) > max_length:
                return False
            min_length = prop_schema.get("minLength")
            if min_length is not None and len(value) < min_length:
                return False

    return True


# =============================================================================
# Environment Validation
# =============================================================================

# Known default/weak JWT secrets that should trigger warnings
WEAK_JWT_SECRETS: set[str] = {
    "change-me-in-production",
    "secret",
    "changeme",
    "default",
    "my-secret-key",
    "jwt_secret",
}


def validate_environment() -> list[str]:
    """Validate the runtime environment for security concerns.

    Returns a list of warning messages. Empty list means all checks passed.
    """
    warnings: list[str] = []

    # Check JWT secret
    secret = settings.jwt_secret_key.lower().strip()
    if secret in WEAK_JWT_SECRETS or len(settings.jwt_secret_key) < 32:
        warnings.append(
            "WARNING: JWT_SECRET_KEY is weak or default. "
            "Set a strong, unique secret in production (min 32 chars)."
        )

    # Check debug mode
    if settings.debug and settings.environment == "production":
        warnings.append(
            "WARNING: DEBUG mode is enabled while ENVIRONMENT=production. "
            "This exposes sensitive debug information. Disable debug mode."
        )

    # Check CORS origins
    if "*" in settings.cors_origins and settings.environment == "production":
        warnings.append(
            "WARNING: CORS_ORIGINS contains '*' in production. "
            "This allows any origin to access the API. Restrict to specific origins."
        )

    # Check if running as root
    if os.geteuid() == 0:  # noqa: S109  (intentionally checking root)
        warnings.append(
            "WARNING: Application is running as root. "
            "Run as a non-privileged user to reduce security risks."
        )

    # Check if running on HTTP in production
    if settings.environment == "production":
        # We can't easily detect the protocol, but we can warn
        pass

    return warnings


def validate_and_warn() -> None:
    """Run environment validation and log all warnings on startup."""
    warnings = validate_environment()
    for warning in warnings:
        logger.warning("Security environment check", message=warning)


# =============================================================================
# Request Validation Utilities
# =============================================================================

# Maximum request body size (10 MB)
MAX_REQUEST_BODY_SIZE = 10 * 1024 * 1024

# Allowed content types for API requests
ALLOWED_CONTENT_TYPES: set[str] = {
    "application/json",
    "application/x-www-form-urlencoded",
    "multipart/form-data",
    "text/plain",
}

# Path traversal patterns
PATH_TRAVERSAL_PATTERN = re.compile(r"(\.\./|\.\.\\)|~")


def is_path_traversal(path: str) -> bool:
    """Check if a path string contains traversal attempts."""
    return bool(PATH_TRAVERSAL_PATTERN.search(path))


def resolve_safe_path(base_dir: Path, user_path: str) -> Path | None:
    """Safely resolve a user-provided path against a base directory.

    Returns the resolved path if it's within the base directory, None otherwise.
    """
    if is_path_traversal(user_path):
        return None

    full_path = (base_dir / user_path).resolve()

    try:
        full_path.relative_to(base_dir.resolve())
        return full_path
    except ValueError:
        return None


def is_allowed_content_type(content_type: str | None) -> bool:
    """Check if the content type is allowed."""
    if content_type is None:
        return False
    # Strip parameters (e.g., "application/json; charset=utf-8" -> "application/json")
    base_type = content_type.split(";")[0].strip().lower()
    return base_type in ALLOWED_CONTENT_TYPES
