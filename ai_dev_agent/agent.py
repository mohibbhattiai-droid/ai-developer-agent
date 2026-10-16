"""LLM-powered planning and tool orchestration."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Any, Protocol

from .tools import WorkspaceTools


DEFAULT_MODEL = "qwen2.5:1.5b"
DEFAULT_HOST = "http://localhost:11434"
MAX_TOOL_CALLS = 6


class ChatClient(Protocol):
    def chat(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str: ...


class OllamaError(RuntimeError):
    """Friendly error raised when the local Ollama API cannot be used."""


class OllamaClient:
    def __init__(self, host: str = DEFAULT_HOST, model: str = DEFAULT_MODEL, timeout: int = 120):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.1},
        }
        if json_mode:
            payload["format"] = "json"
        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
            data = json.loads(raw)
            message = data.get("message", {})
            content = message.get("content")
            if not isinstance(content, str):
                raise OllamaError("Ollama returned a response without message content.")
            return content
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:800]
            if exc.code == 404:
                raise OllamaError(
                    f"Ollama returned HTTP 404. Check that model '{self.model}' is installed. "
                    f"Run: ollama pull {self.model}\nDetails: {detail}"
                ) from exc
            raise OllamaError(f"Ollama API returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise OllamaError(
                f"Could not connect to Ollama at {self.host}. Start Ollama and ensure it is listening, "
                f"then run 'ollama pull {self.model}'. Details: {exc.reason}"
            ) from exc
        except TimeoutError as exc:
            raise OllamaError(f"Ollama request timed out after {self.timeout} seconds. Try again or use a smaller model.") from exc
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise OllamaError(f"Could not decode Ollama's response: {exc}") from exc


@dataclass
class ToolEvent:
    name: str
    arguments: dict[str, Any]
    outcome: dict[str, Any]


@dataclass
class AgentResult:
    task: str
    plan: list[str]
    events: list[ToolEvent]
    summary: str
    analysis_error: str | None = None


SYSTEM_PROMPT = """You are a careful AI developer agent working inside a restricted project workspace.
Analyze the user's request, make a short implementation plan, then select and call tools by returning JSON.
Return ONLY one JSON object with exactly these keys:
{
  "plan": ["short step 1", "short step 2"],
  "tool_calls": [{"name": "tool_name", "arguments": {}}]
}
Rules:
- Choose only tools in the supplied catalogue. Tool calls are executed in order.
- Use 2 to 5 concise plan steps and no more than 6 tool calls.
- The workspace root is already selected for you. Every tool path must be relative to that root.
- For the workspace root, use path ".". For a file directly in the root, use only its filename, for example "greeting.py".
- NEVER use "..", "../workspace", an absolute path, or the workspace folder name as a prefix to access the workspace. Do not try to navigate to the workspace's parent folder.
- For a task asking to create, write, generate, or implement a file, use write_file with the complete file contents. Do not try to read or search for a file that does not exist yet.
- After creating a Python file, call check_python_syntax on that file. Use read_file or search_files only when they are useful for the actual request.
- write_file can create a new file. Existing files are protected unless overwrite=true. Use overwrite=true only when the user's task explicitly asks to update/replace an existing file.
- Never request arbitrary shell commands, network operations, or execution of source code. The available Python syntax checker parses files but does not run them.
- For write_file, include the complete intended file contents in "content". Keep implementations focused and suitable for a small assessment.
- Do not claim a tool succeeded before its result is provided.

Example:
Task: Create greeting.py with a greet(name) function that returns Hello followed by the person's name. Check its Python syntax.
Use write_file with path "greeting.py" and the complete code, then check_python_syntax with path "greeting.py". Do not use "../workspace".

If the task is explanatory and no change is required, use list_files as a harmless workspace inspection, then explain in the final summary.
"""


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("The model response did not contain a JSON object.")
        value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("The model response must be a JSON object.")
    return value


def _plan_issues(task: str, calls: list[dict[str, Any]]) -> list[str]:
    """Detect common small-model planning mistakes before any tools are run."""
    issues: list[str] = []
    for index, call in enumerate(calls, start=1):
        arguments = call.get("arguments", {})
        if not isinstance(arguments, dict):
            issues.append(f"Tool call {index} arguments must be a JSON object.")
            continue
        path = arguments.get("path")
        if isinstance(path, str):
            normalized = path.replace("\\\\", "/")
            windows_path = PureWindowsPath(path)
            if (
                ".." in normalized.split("/")
                or path.startswith(("/", "\\\\"))
                or windows_path.is_absolute()
                or bool(windows_path.drive)
            ):
                issues.append(
                    f"Tool call {index} ({call.get('name', 'unknown')}) has an unsafe path {path!r}; "
                    "paths must be relative to the already-selected workspace root."
                )

    task_lower = task.casefold()
    action = re.search(r"\\b(create|write|generate|implement|build|make|add|update|modify|edit)\\b", task_lower)
    artifact = re.search(r"\\b(file|module|script|function|class|code|\\.py|\\.md|\\.txt|\\.json)\\b", task_lower)
    needs_file_write = bool(action and artifact)
    if needs_file_write and not any(call.get("name") == "write_file" for call in calls):
        issues.append(
            "The task asks to create or change an artifact, but the plan contains no write_file call. "
            "Include write_file with the complete content, then validate the file if applicable."
        )
    return issues


class DeveloperAgent:
    def __init__(self, llm: ChatClient, tools: WorkspaceTools):
        self.llm = llm
        self.tools = tools

    def run(self, task: str) -> AgentResult:
        task = task.strip()
        if not task:
            raise ValueError("Task must not be empty.")
        if len(task) > 4000:
            raise ValueError("Task must be 4,000 characters or fewer.")

        user_prompt = (
            f"USER TASK:\n{task}\n\n"
            f"WORKSPACE (absolute path, for context only): {self.tools.workspace}\n"
            f"AVAILABLE TOOLS:\n{json.dumps(self.tools.descriptions, ensure_ascii=False, indent=2)}\n\n"
            "Return the required JSON plan and ordered tool calls."
        )
        plan: list[str] = []
        calls: list[dict[str, Any]] = []
        analysis_error: str | None = None
        try:
            raw = self.llm.chat(
                [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}],
                json_mode=True,
            )
            parsed = _parse_json_object(raw)
            raw_plan = parsed.get("plan", [])
            if isinstance(raw_plan, list):
                plan = [str(item).strip()[:300] for item in raw_plan if str(item).strip()][:6]
            raw_calls = parsed.get("tool_calls", [])
            if isinstance(raw_calls, list):
                calls = [item for item in raw_calls if isinstance(item, dict)][:MAX_TOOL_CALLS]
            if not plan:
                plan = ["Inspect the workspace", "Perform the requested task using the available safe tools", "Review tool results"]

            # Small local models sometimes propose parent-directory paths or omit the
            # actual write step. Ask once for a corrected plan before executing anything.
            issues = _plan_issues(task, calls)
            if issues:
                repair_prompt = (
                    "The previous proposed plan is invalid or incomplete. Correct it before any tools run.\n"
                    f"USER TASK:\\n{task}\\n\\n"
                    f"PREVIOUS PLAN AND TOOL CALLS:\\n{json.dumps({'plan': plan, 'tool_calls': calls}, ensure_ascii=False)}\\n\\n"
                    f"PROBLEMS TO FIX:\\n- " + "\\n- ".join(issues) + "\\n\\n"
                    "Return only the required JSON object. Do not use parent paths. The workspace root is already selected: "
                    "use '.' for the root and filenames such as 'greeting.py' for files in it. "
                    "For a file-creation task, use write_file with complete content and then check_python_syntax for Python."
                )
                repaired_raw = self.llm.chat(
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": repair_prompt},
                    ],
                    json_mode=True,
                )
                repaired = _parse_json_object(repaired_raw)
                repaired_plan = repaired.get("plan", [])
                repaired_calls = repaired.get("tool_calls", [])
                if isinstance(repaired_plan, list):
                    candidate_plan = [str(item).strip()[:300] for item in repaired_plan if str(item).strip()][:6]
                else:
                    candidate_plan = []
                if isinstance(repaired_calls, list):
                    candidate_calls = [item for item in repaired_calls if isinstance(item, dict)][:MAX_TOOL_CALLS]
                else:
                    candidate_calls = []
                remaining_issues = _plan_issues(task, candidate_calls)
                if remaining_issues:
                    raise ValueError(
                        "The model's corrected plan is still invalid: " + "; ".join(remaining_issues)
                    )
                if not candidate_calls:
                    raise ValueError("The model's corrected plan contained no tool calls.")
                plan = candidate_plan or plan
                calls = candidate_calls
        except Exception as exc:
            analysis_error = f"Planning failed: {exc}"
            plan = ["Inspect the workspace safely", "Report the planning issue without making file changes"]
            calls = [{"name": "list_files", "arguments": {"path": "."}}]

        events: list[ToolEvent] = []
        if not calls:
            calls = [{"name": "list_files", "arguments": {"path": "."}}]

        for item in calls:
            name = item.get("name", "")
            arguments = item.get("arguments", {})
            if not isinstance(name, str):
                name = str(name)
            if not isinstance(arguments, dict):
                arguments = {}
            outcome = self.tools.execute(name, arguments)
            events.append(ToolEvent(name=name, arguments=arguments, outcome=outcome))

        summary_prompt = {
            "task": task,
            "plan": plan,
            "tool_events": [
                {"tool": event.name, "arguments": event.arguments, "outcome": event.outcome}
                for event in events
            ],
            "planning_error": analysis_error,
        }
        if analysis_error:
            summary = (
                f"{analysis_error}\n"
                "No LLM-generated implementation plan or code changes were made. "
                "A safe workspace listing was run so the app could report a controlled error. "
                "Check the Ollama service and model, then retry."
            )
        else:
            try:
                summary = self.llm.chat([
                    {"role": "system", "content": (
                        "Summarize this developer-agent run in plain text. Be concise and honest. "
                        "Mention successful changes, failed tools, and whether validation passed. "
                        "Never claim a failure was a success. Do not suggest that source code was executed."
                    )},
                    {"role": "user", "content": json.dumps(summary_prompt, ensure_ascii=False)},
                ]).strip()
                if not summary:
                    raise ValueError("Empty summary")
            except Exception as exc:
                successes = sum(1 for event in events if event.outcome.get("ok"))
                failures = len(events) - successes
                summary = f"Finished {len(events)} tool call(s): {successes} succeeded, {failures} failed. Summary generation was unavailable ({exc})."
        return AgentResult(task=task, plan=plan, events=events, summary=summary, analysis_error=analysis_error)
