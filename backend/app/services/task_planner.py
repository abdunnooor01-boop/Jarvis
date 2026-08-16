"""Task planning service — breaks high-level goals into discrete tool steps using LLM."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.models.task_plan import TaskPlan
from app.models.task_step import TaskStep
from app.services.tool_executor import ToolExecutor

logger = get_logger(__name__)

# System prompt for the planning LLM
_PLANNING_SYSTEM_PROMPT = """You are Jarvis's task planning system. Your job is to break down a user's high-level goal into a sequence of discrete, executable steps.

For each step, you must specify:
1. A clear description of what to do
2. The tool to use (from the available tools list)
3. The parameters to pass to the tool

Available tools and their descriptions are provided below. Only use tools from this list.

Return your response as a JSON object with this structure:
{
  "steps": [
    {
      "description": "Clear description of this step",
      "tool_name": "name_of_the_tool",
      "tool_params": {
        "param1": "value1",
        ...
      }
    }
  ]
}

Rules:
- Each step must use a tool from the available tools list
- Steps should be ordered and sequential
- Break complex goals into the smallest reasonable steps
- If a tool requires specific parameters, include them
- Do NOT include steps that don't map to a tool
- Keep descriptions concise but clear
- Maximum of 10 steps per plan"""


class TaskPlanner:
    """LLM-based planner that converts user goals into executable step plans.

    Uses OpenAI chat completion to break down goals and maps each step
    to a registered tool from ToolExecutor.
    """

    def __init__(self) -> None:
        self._client: Any = None

    async def _get_client(self) -> Any:
        """Lazy-initialize the OpenAI client."""
        if self._client is None:
            import openai

            self._client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    async def generate_plan(
        self,
        goal: str,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> TaskPlan:
        """Generate a task plan from a user goal.

        Uses LLM to break the goal into steps, creates a TaskPlan
        and TaskSteps in the database, and returns the plan.
        """
        # Get available tools
        tools_info = self._get_available_tools()

        # Try LLM-based planning
        steps_data = await self._plan_with_llm(goal, tools_info)

        # If LLM failed or returned no steps, use fallback
        if not steps_data:
            steps_data = self._fallback_plan(goal, tools_info)

        # Create the plan
        plan = TaskPlan(
            id=uuid.uuid4(),
            user_id=user_id,
            goal=goal,
            status="pending",
        )
        db.add(plan)
        await db.flush()

        # Create the steps
        for i, step in enumerate(steps_data):
            tool_name = step.get("tool_name", "")
            # Validate tool exists
            if not self._is_tool_available(tool_name, tools_info):
                logger.warning(
                    "Step references unknown tool, using fallback",
                    tool_name=tool_name,
                    goal=goal[:50],
                )
                tool_name = "unknown"
                step["tool_params"] = {}

            db_step = TaskStep(
                id=uuid.uuid4(),
                plan_id=plan.id,
                step_number=i + 1,
                description=step.get("description", f"Step {i + 1}"),
                tool_name=tool_name,
                tool_params=step.get("tool_params", {}),
                status="pending",
                retry_count=0,
            )
            db.add(db_step)

        await db.commit()
        await db.refresh(plan)
        return plan

    def _get_available_tools(self) -> list[dict[str, Any]]:
        """Get the list of available tools with their descriptions."""
        executor = ToolExecutor(skip_plugins=True)
        return executor.get_tool_definitions()

    def _is_tool_available(self, tool_name: str, tools: list[dict[str, Any]]) -> bool:
        """Check if a tool name exists in the available tools list."""
        for tool in tools:
            if tool.get("function", {}).get("name") == tool_name:
                return True
        return False

    async def _plan_with_llm(
        self,
        goal: str,
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]] | None:
        """Use OpenAI to break the goal into steps."""
        if not settings.openai_api_key:
            logger.info("No OpenAI API key configured — skipping LLM planning")
            return None

        try:
            client = await self._get_client()

            # Build tool descriptions for the LLM
            tool_descriptions = "\n\n".join(
                [
                    f"Tool: {t.get('function', {}).get('name', 'unknown')}\n"
                    f"Description: {t.get('function', {}).get('description', '')}\n"
                    f"Parameters: {json.dumps(t.get('function', {}).get('parameters', {}))}"
                    for t in tools
                ]
            )

            user_prompt = (
                f"User goal: {goal}\n\n"
                f"Available tools:\n{tool_descriptions}\n\n"
                "Break this goal down into steps using the available tools. "
                "Return only valid JSON."
            )

            response = await client.chat.completions.create(
                model=settings.openai_model or "gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _PLANNING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=2048,
            )

            content = response.choices[0].message.content or "{}"
            data = json.loads(content)

            steps = data.get("steps", [])
            if not steps:
                logger.warning("LLM returned empty steps list", goal=goal[:50])
                return None

            # Validate each step has required fields
            validated_steps = []
            for step in steps:
                if step.get("tool_name") and step.get("description"):
                    validated_steps.append(step)
                else:
                    logger.warning(
                        "LLM step missing required fields",
                        step=step,
                    )

            if not validated_steps:
                return None

            logger.info(
                "LLM plan generated",
                goal=goal[:50],
                num_steps=len(validated_steps),
            )
            return validated_steps

        except Exception as e:
            logger.error(
                "LLM planning failed, using fallback",
                error=str(e),
                goal=goal[:50],
            )
            return None

    def _fallback_plan(
        self,
        goal: str,
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate a simple single-step fallback plan when LLM is unavailable.

        Attempts to find the most relevant tool based on keyword matching.
        Falls back to a generic chat step if no tool matches.
        """
        goal_lower = goal.lower()

        # Try to find the best matching tool
        best_tool = None
        best_score = 0

        for tool_def in tools:
            func_def = tool_def.get("function", {})
            name = func_def.get("name", "")
            desc = func_def.get("description", "").lower()

            # Simple keyword scoring
            score = 0
            for keyword in goal_lower.split():
                if keyword in desc or keyword in name.lower():
                    score += 1

            if score > best_score:
                best_score = score
                best_tool = tool_def

        if best_tool and best_score > 0:
            func_def = best_tool.get("function", {})
            tool_name = func_def.get("name", "unknown")
            logger.info(
                "Fallback plan selected tool by keyword matching",
                tool_name=tool_name,
                score=best_score,
            )

            return [
                {
                    "description": f"Execute task: {goal[:200]}",
                    "tool_name": tool_name,
                    "tool_params": {"query": goal},
                }
            ]

        # Ultimate fallback — return a step describing what needs to be done
        logger.info("Fallback plan — no matching tool found, using generic step")
        return [
            {
                "description": f"Process user request: {goal[:200]}",
                "tool_name": "unknown",
                "tool_params": {},
            }
        ]


# Singleton
_task_planner: TaskPlanner | None = None


def get_task_planner() -> TaskPlanner:
    """Get or create the task planner singleton."""
    global _task_planner
    if _task_planner is None:
        _task_planner = TaskPlanner()
    return _task_planner