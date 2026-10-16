"""Command-line entry point for the AI Developer Agent."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from .agent import DEFAULT_HOST, DEFAULT_MODEL, DeveloperAgent, OllamaClient, OllamaError
from .demo import DemoLLMClient
from .tools import WorkspaceTools


def _pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _safe_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Avoid dumping entire generated files into the console tool-call log."""
    visible = dict(arguments)
    if isinstance(visible.get("content"), str):
        content = visible.pop("content")
        visible["content"] = f"<file content: {len(content)} characters; omitted from log>"
    return visible


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A local-first AI developer agent with workspace-safe tools.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--task", help="Natural-language development task. If omitted, you'll be prompted.")
    parser.add_argument("--workspace", help="Project directory the agent is allowed to access.")
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL), help="Installed Ollama model name.")
    parser.add_argument("--host", default=os.environ.get("OLLAMA_HOST", DEFAULT_HOST), help="Ollama API base URL.")
    parser.add_argument("--demo", action="store_true", help="Run a deterministic offline smoke test (does not use a real LLM).")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    task = args.task
    demo_task = "Create a small calculator module and check its Python syntax."
    if args.demo and task and task.strip() != demo_task:
        print("ERROR: --demo runs a fixed offline smoke test. Remove --task, or use live mode for custom tasks.", file=sys.stderr)
        return 2
    if args.demo:
        task = demo_task
    if not task:
        try:
            task = input("Describe the development task: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nNo task supplied. Exiting.")
            return 2
    if not task.strip():
        print("ERROR: Please provide a non-empty task with --task or at the prompt.")
        return 2

    if args.workspace:
        workspace = args.workspace
    elif args.demo:
        # Use a fresh run folder, so repeated demos remain safe without overwriting prior output.
        demo_root = Path("demo_workspace")
        demo_root.mkdir(parents=True, exist_ok=True)
        workspace = tempfile.mkdtemp(prefix="run-", dir=demo_root)
    else:
        workspace = "workspace"

    try:
        tools = WorkspaceTools(workspace)
        if args.demo:
            print("AI DEVELOPER AGENT — OFFLINE DEMO MODE")
            print("Note: this uses a deterministic mock LLM for smoke testing; live mode uses Ollama.\n")
            llm = DemoLLMClient()
        else:
            llm = OllamaClient(host=args.host, model=args.model)
            print("AI DEVELOPER AGENT — LIVE LOCAL LLM MODE")
            print(f"Model: {args.model} | Ollama: {args.host}")
        print(f"Workspace: {tools.workspace}")
        print(f"Task: {task}\n")

        result = DeveloperAgent(llm, tools).run(task)
        print("IMPLEMENTATION PLAN")
        for index, step in enumerate(result.plan, start=1):
            print(f"  {index}. {step}")
        print("\nTOOL EXECUTION LOG")
        for index, event in enumerate(result.events, start=1):
            print(f"\n[{index}] TOOL CALL: {event.name}")
            print(f"    Arguments: {_pretty(_safe_arguments(event.arguments))}")
            if event.outcome.get("ok"):
                print("    RESULT: SUCCESS")
                print("    Output:")
                print("\n".join("      " + line for line in _pretty(event.outcome.get("result")).splitlines()))
            else:
                print("    RESULT: ERROR")
                print(f"    Error: {event.outcome.get('error', 'Unknown tool error')}")
        print("\nFINAL SUMMARY")
        print(result.summary)
        failures = sum(1 for event in result.events if not event.outcome.get("ok"))
        if result.analysis_error:
            print("\nThe agent could not complete LLM planning. Resolve the issue above and retry.")
            return 1
        if failures:
            print(f"\nCompleted with {failures} failed tool call(s). Review the log above.")
            return 1
        return 0
    except (OllamaError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
