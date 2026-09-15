"""
The permission/schema/step/timeout gate every agent tool call must pass
through. This is the concrete implementation of the PRD's core rule for
the agent layer:

    structured action -> schema validation -> permission validation ->
    tool -> deterministic router

Nothing calls a tool function in app/agent/tools.py directly -- everything
goes through AgentContext.call_tool(), so every attempted action is
logged (success, validation failure, or block) and none can silently skip
validation.
"""

from __future__ import annotations

import concurrent.futures
from typing import Any

from sqlalchemy import func, select

from app.agent.tools import TOOL_FUNCTIONS, TOOL_SCHEMAS
from app.core.config import settings
from app.db import models as m

_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-tool")

_TYPE_CHECKS = {
    "string": str,
    "number": (int, float),
    "integer": int,
}


class ProhibitedToolError(Exception):
    """Raised when the agent attempts to call a tool that isn't in the
    approved tool_schemas.json whitelist. PRD golden case 8."""


class ToolInputValidationError(Exception):
    pass


class AgentStepLimitExceeded(Exception):
    pass


class ToolTimeoutError(Exception):
    pass


def _validate_input(tool_name: str, schema: dict, kwargs: dict) -> None:
    declared = schema.get("input", {})
    unknown = set(kwargs) - set(declared)
    if unknown:
        raise ToolInputValidationError(f"{tool_name}: unexpected argument(s) {sorted(unknown)}")
    missing = set(declared) - set(kwargs)
    if missing:
        raise ToolInputValidationError(f"{tool_name}: missing required argument(s) {sorted(missing)}")
    for field_name, type_name in declared.items():
        expected = _TYPE_CHECKS.get(type_name)
        if expected and not isinstance(kwargs[field_name], expected):
            raise ToolInputValidationError(
                f"{tool_name}.{field_name}: expected {type_name}, got {type(kwargs[field_name]).__name__}"
            )


class AgentContext:
    """One instance per agent run. Tracks step count for the
    max-steps-per-run guardrail and writes the immutable agent_events
    trail for this application."""

    def __init__(self, session, application_id: str):
        self.session = session
        self.application_id = application_id
        # `step` is a monotonically increasing, per-APPLICATION sequence
        # number that survives across multiple agent runs (a run can pause
        # for documents and resume later) -- it's what makes the event log
        # reconstructable in true order. `steps_this_run` is separate: it's
        # what the "max steps per run" guardrail actually limits.
        last_step = session.execute(
            select(func.max(m.AgentEvent.step)).where(m.AgentEvent.application_id == application_id)
        ).scalar()
        self.step = last_step or 0
        self.steps_this_run = 0

    def _log(self, type_: str, detail: str, tool_name: str | None = None, permission: str | None = None, payload: dict | None = None):
        self.step += 1
        self.steps_this_run += 1
        event = m.AgentEvent(
            application_id=self.application_id,
            step=self.step,
            type=type_,
            tool_name=tool_name,
            permission=permission,
            detail=detail,
            payload=payload,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def call_tool(self, tool_name: str, **kwargs: Any) -> dict:
        if self.steps_this_run >= settings.agent_max_steps:
            self._log(
                "BLOCKED_ACTION",
                f"Agent step limit ({settings.agent_max_steps}) exceeded -- run aborted, fail-safe escalation required.",
                tool_name=tool_name,
            )
            raise AgentStepLimitExceeded(f"Exceeded {settings.agent_max_steps} steps in a single agent run")

        schema = TOOL_SCHEMAS.get(tool_name)
        if schema is None:
            self._log(
                "BLOCKED_ACTION",
                f"Prohibited tool call rejected: '{tool_name}' is not in the approved tool contract. "
                "No state was changed.",
                tool_name=tool_name,
            )
            raise ProhibitedToolError(f"Tool '{tool_name}' is not an approved agent tool")

        try:
            _validate_input(tool_name, schema, kwargs)
            if kwargs.get("application_id") != self.application_id:
                raise ToolInputValidationError(
                    f"{tool_name}: application_id {kwargs.get('application_id')!r} does not match "
                    f"this agent run's application {self.application_id!r} -- refusing to act on another application"
                )
        except ToolInputValidationError as exc:
            self._log(
                "BLOCKED_ACTION",
                f"Tool call rejected at schema validation: {exc}",
                tool_name=tool_name,
                permission=schema.get("permission"),
            )
            raise

        self._log(
            "TOOL_CALL",
            f"Calling {tool_name}({', '.join(f'{k}={v!r}' for k, v in kwargs.items())})",
            tool_name=tool_name,
            permission=schema["permission"],
            payload={"input": kwargs},
        )

        func = TOOL_FUNCTIONS[tool_name]
        future = _EXECUTOR.submit(func, self.session, self.application_id, **{k: v for k, v in kwargs.items() if k != "application_id"})
        try:
            result = future.result(timeout=settings.tool_timeout_seconds)
        except concurrent.futures.TimeoutError:
            self._log(
                "BLOCKED_ACTION",
                f"Tool '{tool_name}' exceeded the {settings.tool_timeout_seconds}s timeout and was aborted.",
                tool_name=tool_name,
                permission=schema.get("permission"),
            )
            raise ToolTimeoutError(f"Tool '{tool_name}' timed out after {settings.tool_timeout_seconds}s")

        self._log(
            "TOOL_RESULT",
            f"{tool_name} returned {result}",
            tool_name=tool_name,
            permission=schema["permission"],
            payload={"output": result},
        )
        return result

    def log_recommendation(self, summary: str, reason_codes: list[str], action: str):
        self._log("RECOMMENDATION", summary, payload={"reason_codes": reason_codes, "action": action})

    def log_evidence_analysis(self, detail: str):
        self._log("EVIDENCE_ANALYSIS", detail)

    def log_review_case_created(self, detail: str):
        self._log("REVIEW_CASE_CREATED", detail)
