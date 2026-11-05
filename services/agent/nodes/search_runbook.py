"""LLM-driven, two-step runbook retrieval.

Step 1 gives the model a compact catalog of runbook titles and section
headings. Step 2 lets it call `read_runbook_sections` to fetch only the
sections it chooses. This keeps the prompt small and makes the selection
auditable: deterministic code bounds and ranks the catalog, the model decides
which content is worth reading.
"""

import json
from typing import Any, Dict, List, Set, Tuple

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from services.agent.llm import StepKey, get_llm
from services.agent.nodes.trace_step import traced_step
from services.agent.prompts.runbooks import (
    build_runbook_selection_system_prompt,
    build_runbook_selection_user_prompt,
)
from services.agent.state import AgentState
from services.agent.tools.runbooks import (
    MAX_TOTAL_CHARS,
    fetch_runbook_sections,
    format_runbook_catalog,
    load_runbook_catalog,
)

_MAX_TOOL_ROUNDS = 3
_MAX_TOOL_CALLS = 4
_FETCH_TOOL = "read_runbook_sections"


@tool("read_runbook_sections")
async def read_runbook_sections_tool(
    runbook_id: str,
    section_indexes: list[int],
) -> str:
    """Read specific sections listed in the runbook catalog. Pass the
    runbook_id and one to three section indexes shown in the catalog."""
    result = await fetch_runbook_sections(runbook_id, section_indexes)
    return json.dumps(result, default=str)


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def _incident_query(state: AgentState) -> str:
    """Build a small free-text query from the incident's own facts."""
    return " ".join(
        part
        for part in (
            state.get("incident_title"),
            state.get("summary"),
        )
        if part
    )


def _add_missing(missing: List[str], message: str) -> None:
    if message not in missing:
        missing.append(message)


def _failure(error: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "output": "",
        "error": error,
        "truncated": False,
    }


async def _execute_tool(
    name: str,
    args: Dict[str, Any],
    remaining_chars: int,
) -> Dict[str, Any]:
    """Run one runbook tool with the remaining context budget."""
    if name != _FETCH_TOOL:
        return _failure(f"Unknown runbook tool: {name}")

    raw_indexes = args.get("section_indexes")
    if not isinstance(raw_indexes, list):
        return _failure("section_indexes must be a list of integers.")
    if remaining_chars <= 0:
        return _failure("The runbook retrieval budget is exhausted.")

    try:
        return await fetch_runbook_sections(
            str(args.get("runbook_id") or ""),
            raw_indexes,
            max_total_chars=remaining_chars,
        )
    except Exception as exc:
        return _failure(f"Tool call failed: {exc}")


def _merge_sections(
    fetched: Dict[str, Dict[str, Any]],
    seen: Set[Tuple[str, int]],
    result: Dict[str, Any],
    remaining_chars: int,
) -> int:
    """Merge fetched sections into the final summary, skipping duplicates.

    Returns the number of content characters added.
    """
    if not result.get("ok"):
        return 0

    runbook_id = str(result.get("runbook_id") or "")
    title = result.get("title") or "Untitled runbook"
    service = result.get("service")
    added_chars = 0

    for section in result.get("sections") or []:
        index = int(section.get("index", -1))
        key = (runbook_id, index)
        if index < 0 or key in seen:
            continue

        heading = str(section.get("heading") or "Untitled section")
        content = str(section.get("content") or "")
        cost = len(heading) + len(content)
        if added_chars + cost > remaining_chars:
            break

        entry = fetched.setdefault(
            runbook_id,
            {"title": title, "service": service, "sections": []},
        )
        entry["sections"].append(
            {"index": index, "heading": heading, "content": content}
        )
        seen.add(key)
        added_chars += cost

    return added_chars


def _format_fetched(fetched: Dict[str, Dict[str, Any]]) -> str:
    blocks: List[str] = []

    for entry in fetched.values():
        service = entry.get("service") or "unspecified service"
        blocks.append(f"## Runbook: {entry['title']} (service: {service})")
        for section in entry["sections"]:
            blocks.append(f"### {section['heading']}\n{section['content']}")

    return "\n\n".join(blocks).strip()


@traced_step("search_runbook")
async def search_runbook(state: AgentState) -> Dict[str, Any]:
    """Let the model choose which runbook sections to load."""
    missing = list(state.get("missing_evidence") or [])
    incident_type = state.get("incident_type")
    incident_type_value = getattr(
        incident_type,
        "value",
        str(incident_type or "other"),
    )

    try:
        catalog = await load_runbook_catalog(
            service=state.get("deployment_name"),
            incident_type=incident_type_value,
            query=_incident_query(state),
        )
    except Exception as exc:
        _add_missing(missing, f"Runbook catalog lookup failed: {exc}")
        return {
            "runbooks_summary": "",
            "missing_evidence": missing,
        }

    if not catalog:
        # Nothing to choose from; skip the model call entirely.
        return {
            "runbooks_summary": "",
            "missing_evidence": missing,
        }

    try:
        llm = get_llm(StepKey.RUNBOOKS)
    except Exception as exc:
        _add_missing(missing, f"Runbook selection model unavailable: {exc}")
        return {
            "runbooks_summary": "",
            "missing_evidence": missing,
        }

    messages = [
        SystemMessage(
            content=build_runbook_selection_system_prompt(_MAX_TOOL_CALLS)
        ),
        HumanMessage(
            content=build_runbook_selection_user_prompt(
                incident_title=(
                    state.get("incident_title") or "Untitled incident"
                ),
                incident_type=incident_type_value,
                severity=_text(state.get("severity"), "unknown"),
                summary=state.get("summary") or "",
                description=state.get("description") or "",
                namespace=state.get("namespace"),
                pod_name=state.get("pod_name"),
                deployment_name=state.get("deployment_name"),
                container_name=state.get("container_name"),
                catalog=format_runbook_catalog(catalog),
            )
        ),
    ]
    try:
        model = llm.bind_tools([read_runbook_sections_tool])
    except Exception as exc:
        _add_missing(missing, f"Runbook selection model unavailable: {exc}")
        return {
            "runbooks_summary": "",
            "missing_evidence": missing,
        }

    fetched: Dict[str, Dict[str, Any]] = {}
    seen: Set[Tuple[str, int]] = set()
    total_chars = 0
    tool_calls = 0
    budget_hit = False

    try:
        for _round in range(_MAX_TOOL_ROUNDS):
            response = await model.ainvoke(messages)
            messages.append(response)

            calls = getattr(response, "tool_calls", None) or []
            if not calls:
                break

            for call in calls:
                if not isinstance(call, dict):
                    continue
                if tool_calls >= _MAX_TOOL_CALLS:
                    _add_missing(
                        missing,
                        f"Runbook selection stopped after "
                        f"{_MAX_TOOL_CALLS} tool calls.",
                    )
                    budget_hit = True
                    break

                name = str(call.get("name") or "")
                raw_args = call.get("args") or {}
                args = raw_args if isinstance(raw_args, dict) else {}
                remaining = max(0, MAX_TOTAL_CHARS - total_chars)

                result = await _execute_tool(name, args, remaining)
                tool_calls += 1

                if result.get("ok"):
                    total_chars += _merge_sections(
                        fetched,
                        seen,
                        result,
                        remaining,
                    )
                    if result.get("truncated"):
                        _add_missing(
                            missing,
                            "Some runbook sections were truncated to fit the "
                            "retrieval budget.",
                        )
                else:
                    _add_missing(
                        missing,
                        "Runbook section read failed: "
                        f"{result.get('error') or 'unknown error'}",
                    )

                messages.append(
                    ToolMessage(
                        content=json.dumps(result, default=str),
                        tool_call_id=str(
                            call.get("id") or f"call-{tool_calls}"
                        ),
                    )
                )

            if budget_hit:
                break
        else:
            _add_missing(
                missing,
                f"Runbook selection stopped after {_MAX_TOOL_ROUNDS} "
                "model turns.",
            )
    except Exception as exc:
        _add_missing(missing, f"Runbook selection failed: {exc}")

    return {
        "runbooks_summary": _format_fetched(fetched),
        "missing_evidence": missing,
    }
