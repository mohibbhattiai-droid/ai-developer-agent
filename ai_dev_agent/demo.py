"""Deterministic offline client for smoke-testing the full tool pipeline."""
from __future__ import annotations

import json


class DemoLLMClient:
    """A local stub, not a real LLM. Live inference uses OllamaClient."""

    def __init__(self):
        self.calls = 0

    def chat(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
        self.calls += 1
        if self.calls == 1:
            response = {
                "plan": [
                    "Inspect the demo workspace.",
                    "Create a small calculator module with add and subtract functions.",
                    "Parse the new Python file to verify syntax without executing it.",
                ],
                "tool_calls": [
                    {"name": "list_files", "arguments": {"path": "."}},
                    {
                        "name": "write_file",
                        "arguments": {
                            "path": "calculator.py",
                            "overwrite": False,
                            "content": '"""Tiny calculator helpers created by the AI Developer Agent demo."""\n\n\ndef add(a: float, b: float) -> float:\n    """Return the sum of two numbers."""\n    return a + b\n\n\ndef subtract(a: float, b: float) -> float:\n    """Return the difference between two numbers."""\n    return a - b\n',
                        },
                    },
                    {"name": "check_python_syntax", "arguments": {"path": "calculator.py"}},
                ],
            }
            return json.dumps(response)
        return (
            "Demo completed successfully. The calculator.py file was created in the isolated demo "
            "workspace, and the Python syntax checker passed. This offline smoke test uses a "
            "deterministic mock LLM; run without --demo to use the live local Ollama model."
        )
