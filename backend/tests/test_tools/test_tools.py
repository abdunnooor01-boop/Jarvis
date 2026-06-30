"""Tests for the tool system."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.tools.file_ops import FileOpsTool
from app.tools.web_search import WebSearchTool


class TestBaseTool:
    """Tests for the base tool class."""

    def test_to_openai_definition(self) -> None:
        """Test that the OpenAI tool definition format is correct."""
        tool = WebSearchTool()
        definition = tool.to_openai_definition()

        assert definition["type"] == "function"
        assert definition["function"]["name"] == "web_search"
        assert "description" in definition["function"]
        assert "parameters" in definition["function"]


class TestFileOpsTool:
    """Tests for the file operations tool."""

    @pytest.mark.asyncio
    async def test_write_and_read_file(self) -> None:
        """Test writing to and reading from a file."""
        tool = FileOpsTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "test.txt"

            # Write
            write_result = await tool.execute(
                operation="write",
                path=str(test_path),
                content="Hello, World!",
            )
            assert write_result["status"] == "ok"
            assert write_result["written"] == 13

            # Read
            read_result = await tool.execute(
                operation="read",
                path=str(test_path),
            )
            assert read_result["content"] == "Hello, World!"

    @pytest.mark.asyncio
    async def test_list_directory(self) -> None:
        """Test listing directory contents."""
        tool = FileOpsTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some files
            d = Path(tmpdir)
            (d / "a.txt").write_text("a")
            (d / "b.txt").write_text("b")

            result = await tool.execute(operation="list", path=str(d))
            assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_delete_file(self) -> None:
        """Test deleting a file."""
        tool = FileOpsTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = Path(tmpdir) / "delete_me.txt"
            test_path.write_text("to be deleted")

            result = await tool.execute(operation="delete", path=str(test_path))
            assert result["status"] == "deleted"
            assert not test_path.exists()

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self) -> None:
        """Test reading a non-existent file returns an error."""
        tool = FileOpsTool()
        result = await tool.execute(
            operation="read",
            path="/nonexistent/path/file.txt",
        )
        assert "error" in result


class TestWebSearchTool:
    """Tests for the web search tool."""

    @pytest.mark.asyncio
    async def test_mock_results_no_api_key(self) -> None:
        """Test that web search returns mock results when no API key is configured."""
        tool = WebSearchTool()
        result = await tool.execute(query="test query")

        assert "results" in result
        assert len(result["results"]) > 0
