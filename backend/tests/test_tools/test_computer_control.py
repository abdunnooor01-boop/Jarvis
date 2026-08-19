"""Tests for computer control tools (clipboard, terminal, mouse, keyboard, etc.)."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.clipboard import ClipboardTool
from app.tools.terminal import TerminalTool
from app.tools.screenshot import ScreenshotTool
from app.tools.screen_read import ScreenReadTool
from app.tools.mouse import MouseTool
from app.tools.keyboard import KeyboardTool
from app.tools.app_launch import AppLaunchTool
from app.tools.browser import BrowserTool


# Mouse/keyboard/screenshot tools drive a real X display via pyautogui; they
# cannot run on a headless host (no DISPLAY) — skip them there instead of
# failing with KeyError('DISPLAY').
requires_display = pytest.mark.skipif(
    os.environ.get("DISPLAY") is None,
    reason="requires an X display (headless environment has none)",
)

# ------------------------------------------------------------------ #
#  ClipboardTool
# ------------------------------------------------------------------ #

class TestClipboardTool:
    """Tests for ClipboardTool."""

    def test_name_and_description(self) -> None:
        tool = ClipboardTool()
        assert tool.name == "clipboard"
        assert tool.description

    def test_to_openai_definition(self) -> None:
        tool = ClipboardTool()
        defn = tool.to_openai_definition()
        assert defn["type"] == "function"

    @pytest.mark.asyncio
    async def test_read(self) -> None:
        tool = ClipboardTool()
        with patch("pyperclip.paste", return_value="clipboard text"):
            result = await tool.execute(operation="read")
        assert result["content"] == "clipboard text"

    @pytest.mark.asyncio
    async def test_write(self) -> None:
        tool = ClipboardTool()
        with patch("pyperclip.copy") as mock_copy:
            result = await tool.execute(operation="write", text="hello")
        assert result["status"] == "written"
        mock_copy.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_write_no_text(self) -> None:
        tool = ClipboardTool()
        result = await tool.execute(operation="write")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_unknown_operation(self) -> None:
        tool = ClipboardTool()
        result = await tool.execute(operation="unknown")
        assert "error" in result


# ------------------------------------------------------------------ #
#  TerminalTool
# ------------------------------------------------------------------ #

class TestTerminalTool:
    """Tests for TerminalTool."""

    def test_name_and_description(self) -> None:
        tool = TerminalTool()
        assert tool.name == "terminal"

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        tool = TerminalTool()
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"hello world", b"")
        )
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_shell", return_value=mock_process):
            result = await tool.execute(operation="execute", command="echo hello")

        assert result["stdout"] == "hello world"
        assert result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_execute_empty_command(self) -> None:
        tool = TerminalTool()
        result = await tool.execute(operation="execute", command="")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_execute_dangerous_blocked(self) -> None:
        tool = TerminalTool()
        result = await tool.execute(operation="execute", command="rm -rf /")
        assert "error" in result
        assert "blocked" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_sudo_blocked(self) -> None:
        tool = TerminalTool()
        result = await tool.execute(operation="execute", command="sudo apt-get install")
        assert "error" in result
        assert "blocked" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_timeout(self) -> None:
        tool = TerminalTool()
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()

        with patch("asyncio.create_subprocess_shell", return_value=mock_process):
            result = await tool.execute(operation="execute", command="sleep 100", timeout=1)

        assert "error" in result
        assert "timed out" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_background(self) -> None:
        tool = TerminalTool()
        mock_process = MagicMock()
        mock_process.pid = 12345

        with patch("asyncio.create_subprocess_shell", return_value=mock_process):
            result = await tool.execute(operation="execute_background", command="sleep 10")

        assert result["pid"] == 12345
        assert result["status"] == "started"

    @pytest.mark.asyncio
    async def test_kill_process(self) -> None:
        tool = TerminalTool()
        with patch("os.kill") as mock_kill:
            result = await tool.execute(operation="kill", pid=12345)
        assert result["status"] == "terminated"
        mock_kill.assert_called_once()


# ------------------------------------------------------------------ #
#  ScreenshotTool
# ------------------------------------------------------------------ #

@requires_display
class TestScreenshotTool:
    """Tests for ScreenshotTool."""

    def test_name_and_description(self) -> None:
        tool = ScreenshotTool()
        assert tool.name == "screenshot"

    @pytest.mark.asyncio
    async def test_capture_full(self) -> None:
        tool = ScreenshotTool()
        # Mock mss
        mock_sct = MagicMock()
        mock_monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}
        mock_sct.monitors = [mock_monitor]
        mock_img = MagicMock()
        mock_img.rgb = b"fake_rgb"
        mock_img.size = (1920, 1080)
        mock_sct.grab = MagicMock(return_value=mock_img)

        with patch("mss.mss", return_value=mock_sct):
            with patch("mss.tools.to_png", return_value=b"png_data"):
                result = await tool.execute(operation="capture")

        assert result["width"] == 1920
        assert result["height"] == 1080
        assert result["format"] == "png"

    @pytest.mark.asyncio
    async def test_capture_region_invalid(self) -> None:
        tool = ScreenshotTool()
        result = await tool.execute(operation="capture_region", width=0, height=0)
        assert "error" in result


# ------------------------------------------------------------------ #
#  ScreenReadTool
# ------------------------------------------------------------------ #

class TestScreenReadTool:
    """Tests for ScreenReadTool."""

    def test_name_and_description(self) -> None:
        tool = ScreenReadTool()
        assert tool.name == "screen_read"

    @pytest.mark.asyncio
    async def test_read_text(self) -> None:
        tool = ScreenReadTool()
        mock_img = MagicMock()

        with patch.object(tool, "_capture_full", return_value=mock_img):
            with patch("pytesseract.image_to_string", return_value="Hello World\nLine 2"):
                result = await tool.execute(operation="read_text")

        assert "text" in result
        assert result["line_count"] == 2

    @pytest.mark.asyncio
    async def test_find_text_found(self) -> None:
        tool = ScreenReadTool()
        mock_img = MagicMock()

        with patch.object(tool, "_capture_full", return_value=mock_img):
            with patch("pytesseract.image_to_string", return_value="Hello World"):
                with patch("pytesseract.image_to_data") as mock_data:
                    mock_data.return_value = {
                        "text": ["Hello", "World"],
                        "left": [10, 50],
                        "top": [20, 20],
                        "width": [40, 50],
                        "height": [15, 15],
                    }
                    result = await tool.execute(operation="find_text", text="Hello")

        assert result["found"] is True
        assert result["count"] >= 1

    @pytest.mark.asyncio
    async def test_find_text_no_query(self) -> None:
        tool = ScreenReadTool()
        result = await tool.execute(operation="find_text")
        assert "error" in result


# ------------------------------------------------------------------ #
#  MouseTool
# ------------------------------------------------------------------ #

@requires_display
class TestMouseTool:
    """Tests for MouseTool."""

    def test_name_and_description(self) -> None:
        tool = MouseTool()
        assert tool.name == "mouse"

    @pytest.mark.asyncio
    async def test_move(self) -> None:
        tool = MouseTool()
        with patch("pyautogui.moveTo") as mock_move:
            result = await tool.execute(operation="move", x=100, y=200)
        assert result["status"] == "moved"
        mock_move.assert_called_once_with(100, 200)

    @pytest.mark.asyncio
    async def test_click(self) -> None:
        tool = MouseTool()
        with patch("pyautogui.click") as mock_click:
            result = await tool.execute(operation="click", x=100, y=200)
        assert result["status"] == "clicked"

    @pytest.mark.asyncio
    async def test_double_click(self) -> None:
        tool = MouseTool()
        with patch("pyautogui.doubleClick") as mock_dc:
            result = await tool.execute(operation="double_click", x=100, y=200)
        assert result["status"] == "double_clicked"

    @pytest.mark.asyncio
    async def test_scroll(self) -> None:
        tool = MouseTool()
        with patch("pyautogui.scroll") as mock_scroll:
            result = await tool.execute(operation="scroll", amount=5)
        assert result["status"] == "scrolled"

    @pytest.mark.asyncio
    async def test_get_position(self) -> None:
        tool = MouseTool()
        mock_pos = MagicMock()
        mock_pos.x = 500
        mock_pos.y = 300
        with patch("pyautogui.position", return_value=mock_pos):
            result = await tool.execute(operation="get_position")
        assert result["x"] == 500
        assert result["y"] == 300


# ------------------------------------------------------------------ #
#  KeyboardTool
# ------------------------------------------------------------------ #

@requires_display
class TestKeyboardTool:
    """Tests for KeyboardTool."""

    def test_name_and_description(self) -> None:
        tool = KeyboardTool()
        assert tool.name == "keyboard"

    @pytest.mark.asyncio
    async def test_type_text(self) -> None:
        tool = KeyboardTool()
        with patch("pyautogui.write") as mock_write:
            result = await tool.execute(operation="type", text="hello")
        assert result["status"] == "typed"
        assert result["length"] == 5
        mock_write.assert_called_once_with("hello", interval=0.01)

    @pytest.mark.asyncio
    async def test_type_empty(self) -> None:
        tool = KeyboardTool()
        result = await tool.execute(operation="type")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_hotkey(self) -> None:
        tool = KeyboardTool()
        with patch("pyautogui.hotkey") as mock_hotkey:
            result = await tool.execute(operation="hotkey", keys=["ctrl", "c"])
        assert result["status"] == "hotkey_pressed"
        mock_hotkey.assert_called_once_with("ctrl", "c")

    @pytest.mark.asyncio
    async def test_press(self) -> None:
        tool = KeyboardTool()
        with patch("pyautogui.press") as mock_press:
            result = await tool.execute(operation="press", key="enter")
        assert result["status"] == "key_pressed"
        mock_press.assert_called_once_with("enter")


# ------------------------------------------------------------------ #
#  AppLaunchTool
# ------------------------------------------------------------------ #

class TestAppLaunchTool:
    """Tests for AppLaunchTool."""

    def test_name_and_description(self) -> None:
        tool = AppLaunchTool()
        assert tool.name == "app_launch"

    @pytest.mark.asyncio
    async def test_open_app_no_name(self) -> None:
        tool = AppLaunchTool()
        result = await tool.execute(operation="open_app")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_list_running(self) -> None:
        tool = AppLaunchTool()
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(b"bash\npython3\nchrome\n", b"")
        )
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await tool.execute(operation="list_running")

        assert result["count"] >= 3
        assert "bash" in result["processes"]


# ------------------------------------------------------------------ #
#  BrowserTool
# ------------------------------------------------------------------ #

class TestBrowserTool:
    """Tests for BrowserTool."""

    def test_name_and_description(self) -> None:
        tool = BrowserTool()
        assert tool.name == "browser"

    @pytest.mark.asyncio
    async def test_open_url_no_url(self) -> None:
        tool = BrowserTool()
        result = await tool.execute(operation="open_url")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_open_url_fallback_webbrowser(self) -> None:
        tool = BrowserTool()
        with patch("webbrowser.open", return_value=True) as mock_web:
            with patch("playwright.async_api.async_playwright", side_effect=ImportError("No playwright")):
                result = await tool.execute(operation="open_url", url="https://example.com")
        assert result["status"] == "opened"
        assert result["method"] == "webbrowser"
        mock_web.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_open_url_adds_scheme(self) -> None:
        tool = BrowserTool()
        with patch("webbrowser.open", return_value=True) as mock_web:
            with patch("playwright.async_api.async_playwright", side_effect=ImportError("No playwright")):
                result = await tool.execute(operation="open_url", url="example.com")
        assert result["status"] == "opened"
        # Check that https:// was prepended
        called_url = mock_web.call_args[0][0]
        assert called_url.startswith("https://")

    @pytest.mark.asyncio
    async def test_search(self) -> None:
        tool = BrowserTool()
        with patch("webbrowser.open", return_value=True) as mock_web:
            with patch("playwright.async_api.async_playwright", side_effect=ImportError("No playwright")):
                result = await tool.execute(operation="search", query="test query")
        assert result["status"] == "opened"
        called_url = mock_web.call_args[0][0]
        assert "google.com/search" in called_url
        assert "test+query" in called_url or "test%20query" in called_url