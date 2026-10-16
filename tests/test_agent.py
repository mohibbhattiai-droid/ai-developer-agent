import json
import tempfile
import unittest
from pathlib import Path

from ai_dev_agent.agent import DeveloperAgent
from ai_dev_agent.tools import WorkspaceTools


class FakeLLM:
    def __init__(self):
        self.turn = 0

    def chat(self, messages, *, json_mode=False):
        self.turn += 1
        if self.turn == 1:
            return json.dumps({
                "plan": ["Create a Python helper", "Validate its syntax"],
                "tool_calls": [
                    {"name": "write_file", "arguments": {"path": "helper.py", "content": "def double(n):\n    return n * 2\n"}},
                    {"name": "check_python_syntax", "arguments": {"path": "helper.py"}},
                ],
            })
        return "Created helper.py and syntax validation passed."


class FailingLLM:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, *, json_mode=False):
        self.calls += 1
        raise RuntimeError("model is unavailable")


class DeveloperAgentTests(unittest.TestCase):
    def test_agent_executes_tools_and_summarizes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            agent = DeveloperAgent(FakeLLM(), WorkspaceTools(root))
            result = agent.run("Create a helper and validate it")
            self.assertEqual(len(result.events), 2)
            self.assertTrue(all(event.outcome["ok"] for event in result.events))
            self.assertTrue(result.events[1].outcome["result"]["valid"])
            self.assertIn("passed", result.summary)
            self.assertTrue((root / "helper.py").exists())

    def test_model_failure_is_reported_and_workspace_is_not_modified(self):
        with tempfile.TemporaryDirectory() as temp:
            llm = FailingLLM()
            agent = DeveloperAgent(llm, WorkspaceTools(temp))
            result = agent.run("Create a new file")
            self.assertIsNotNone(result.analysis_error)
            self.assertEqual(len(result.events), 1)
            self.assertEqual(result.events[0].name, "list_files")
            self.assertFalse((Path(temp) / "new_file.py").exists())
            self.assertEqual(llm.calls, 1)
            self.assertIn("planning failed", result.summary.lower())

    def test_empty_task_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            agent = DeveloperAgent(FakeLLM(), WorkspaceTools(temp))
            with self.assertRaises(ValueError):
                agent.run("   ")


if __name__ == "__main__":
    unittest.main()
