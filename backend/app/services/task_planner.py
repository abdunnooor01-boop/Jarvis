"""Task Planner — breaks down user goals into executable step plans using the LLM."""

from __future__ import annotations

import json
from typing import Any

from app.core.logging import get_logger
from app.services.llm import get_llm_service
from app.services.tool_executor import ToolExecutor

logger = get_logger(__name__)


class TaskPlanner:
    """Decomposes a user goal into a structured step-by-step plan.

    Uses the LLM to reason about the goal and generate a sequence of tool
    calls that will accomplish it.
    """

    def __init__(self) -> None:
        self._llm = get_llm_service()
        self._tool_executor = ToolExecutor()

    async def plan(self, goal: str) -> list[dict[str, Any]]:
        """Generate a step-by-step plan for a given goal.

        Args:
            goal: The user's goal or request.

        Returns:
            A list of step dicts, each with:
                - tool_name: str
                - tool_params: dict
                - description: str
        """
        tool_defs = self._tool_executor.get_tool_definitions()
        tool_descriptions = "\n".join(
            f"- {t['function']['name']}: {t['function']['description']}"
            for t in tool_defs
        )

        prompt = (
            "You are a task planning AI. Break down the user's goal into "
            "a sequence of tool calls that will accomplish it.\n\n"
            f"Available tools:\n{tool_descriptions}\n\n"
            "Rules:\n"
            "1. Return ONLY valid JSON — no markdown, no explanation.\n"
            "2. The response must be a JSON array of step objects.\n"
            "3. Each step must have: tool_name (str), tool_params (object), "
            "description (str).\n"
            "4. tool_params must be valid for the tool's parameter schema.\n"
            "5. Break complex goals into small, focused steps.\n"
            "6. If the goal is simple (e.g. 'say hello'), return a single step.\n"
            "7. Do not include steps that don't use available tools.\n\n"
            f"User goal: {goal}\n\n"
            "JSON response:"
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a precise task planner. "
                    "Always respond with valid JSON arrays."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        # Use a non-streaming call to get the full plan
        try:
            response_text = ""
            async for chunk in self._llm.stream_chat(
                messages=messages,
                tools=None,  # No tool calling — we want the LLM to reason, not act
            ):
                if chunk["type"] == "content":
                    response_text += chunk["content"]

            steps = self._parse_plan_response(response_text)

            if not steps:
                logger.warning("Task planner returned empty plan", goal=goal[:100])
                return []

            # Validate each step has the required fields
            validated_steps = []
            for _i, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue
                tool_name = step.get("tool_name", "")
                tool_params = step.get("tool_params", {})
                description = step.get("description", "")

                if not tool_name or not description:
                    continue

                # Ensure tool_params is a dict
                if not isinstance(tool_params, dict):
                    tool_params = {}

                validated_steps.append({
                    "tool_name": tool_name,
                    "tool_params": tool_params,
                    "description": description,
                })

            logger.info(
                "Plan generated",
                goal=goal[:100],
                step_count=len(validated_steps),
            )
            return validated_steps

        except Exception as e:
            logger.error("Task planning failed", goal=goal[:100], error=str(e))
            return []

    def _parse_plan_response(self, text: str) -> list[dict[str, Any]]:
        """Parse JSON from LLM response, handling markdown and extra text."""
        text = text.strip()

        # Remove markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            if len(lines) > 2:
                text = "\n".join(lines[1:-1]).strip()

        # Try direct JSON parse
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
            return []
        except json.JSONDecodeError:
            pass

        # Try to find a JSON array in the text
        import re

        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(0))
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

        # Try to find a JSON object that might contain steps
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(0))
                if isinstance(result, dict):
                    steps = result.get("steps", result.get("plan", []))
                    if isinstance(steps, list):
                        return steps
            except json.JSONDecodeError:
                pass

        return []
