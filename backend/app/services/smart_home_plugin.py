"""Abstract base class for smart home integrations.

All smart home plugins (Home Assistant, Hubitat, Matter, etc.)
must implement this interface. The plugin system handles device
discovery, state sync, and command execution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class SmartHomePlugin(ABC):
    """Abstract base class for smart home integrations.

    Each integration (Home Assistant, Hubitat, etc.) implements
    this interface to register devices, sync state, and execute commands.

    Usage:
        class HomeAssistantPlugin(SmartHomePlugin):
            @property
            def name(self) -> str:
                return "home_assistant"

            async def discover_devices(self, config: dict) -> list[dict]:
                ...

            async def sync_state(self, device_id: str) -> dict:
                ...

            async def execute_command(self, device_id: str, command: str, params: dict) -> dict:
                ...
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique integration name (e.g. 'home_assistant', 'hubitat')."""
        ...

    @abstractmethod
    async def discover_devices(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Discover devices from the integration.

        Returns a list of device dicts with:
        - external_id: str (unique ID from the integration)
        - device_type: str (one of DeviceType enum values)
        - name: str
        - room: str | None
        - manufacturer: str | None
        - model: str | None
        - state: dict (current device state)
        """
        ...

    @abstractmethod
    async def sync_state(self, external_id: str) -> dict[str, Any]:
        """Fetch the current state of a device from the integration.

        Returns the device state dict (e.g. {"on": true, "brightness": 80}).
        """
        ...

    @abstractmethod
    async def execute_command(
        self,
        external_id: str,
        command: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a command on a device.

        Args:
            external_id: The device's ID in the integration.
            command: The command to execute (e.g. 'turn_on', 'set_brightness').
            params: Command parameters.

        Returns:
            Dict with 'success' bool and optional 'state' dict.
        """
        ...

    async def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate the integration configuration.

        Returns a dict with 'valid' bool and optional 'error' message.
        Override to add integration-specific validation.
        """
        required = self.required_config_keys()
        missing = [k for k in required if k not in config]
        if missing:
            return {
                "valid": False,
                "error": f"Missing required config keys: {', '.join(missing)}",
            }
        return {"valid": True}

    def required_config_keys(self) -> list[str]:
        """Return a list of required configuration keys.

        Override to specify integration-specific config requirements.
        """
        return []

    def device_type_map(self) -> dict[str, str]:
        """Map integration-specific device types to Jarvis DeviceType values.

        Override to handle type mapping. Returns {integration_type: jarvis_type}.
        """
        return {}


# Registry of available plugins
_plugins: dict[str, SmartHomePlugin] = {}


def register_plugin(plugin: SmartHomePlugin) -> None:
    """Register a smart home plugin."""
    _plugins[plugin.name] = plugin
    logger.info("Smart home plugin registered", name=plugin.name)


def get_plugin(name: str) -> SmartHomePlugin | None:
    """Get a registered plugin by name."""
    return _plugins.get(name)


def get_all_plugins() -> list[SmartHomePlugin]:
    """Get all registered plugins."""
    return list(_plugins.values())


def get_plugin_names() -> list[str]:
    """Get names of all registered plugins."""
    return list(_plugins.keys())