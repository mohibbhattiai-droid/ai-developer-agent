# Implementation and AI-use note

## What the project implements

This project is a Python command-line AI Developer Agent. It accepts a natural-language task, asks an LLM for a short plan and ordered tool calls, executes tools from an allowlist inside a selected workspace, prints each tool call and result, and produces a final summary.

The five tools are:
- `list_files` — list files in the workspace.
- `read_file` — read a UTF-8 text file.
- `search_files` — search supported text files.
- `write_file` — create files and update existing files only when overwrite is explicitly enabled.
- `check_python_syntax` — parse a Python file with `ast.parse` without executing it.

The tool layer restricts access to the workspace, blocks common credential/private-key paths, and returns errors for invalid calls instead of intentionally allowing arbitrary shell commands.

## My contribution

I set up the Python project and Ollama on my laptop, designed and refined prompts and tool behavior, integrated the project modules, fixed errors, ran the program and tested it locally, reviewed the code to understand how it works, and prepared the README, screenshots, and supporting documentation.

## AI tools and runtime model used

- **ChatGPT:** used as an AI development assistant to help with design, code drafting, reviewing, troubleshooting, testing ideas, and documentation. The implementation was developed with AI assistance; I reviewed the code, integrated components, and ran the project rather than claiming every line was written without assistance.
- **Ollama with `qwen2.5:1.5b`:** the intended live runtime. The application calls the local Ollama `/api/chat` endpoint. No paid model API key is required.
- **Offline demo mode:** `python main.py --demo` uses a deterministic mock client, not a real LLM. It is useful for smoke-testing tool execution and logging when the model is unavailable, but it must not be presented as evidence of live inference.

## Testing and evidence

I ran the program and tested it locally. The repository includes a saved unit-test result report listing 12 passing tests, and screenshots of the demo/test workflow. Before final submission, I will make sure the test command succeeds on my machine and include a screenshot from a successful run **without** `--demo` so the live Ollama integration is clearly demonstrated.

Automated tests use Python's standard library and do not require a paid API. The recorded results in the repository are supporting evidence; they are not a substitute for rerunning the tests when making further changes.

## Known limitations

- Results depend on the local model's quality. A small model can return malformed JSON or choose an unsuitable tool.
- Python syntax validation does not establish that a program's behavior is correct; the checker parses code but does not execute it.
- The tool layer intentionally does not offer unrestricted shell execution or execute generated source code.
- The agent plans once and then runs the tools. It does not read tool results and re-plan, so it is not a full iterative agent loop.
- There is no shell or test-execution tool, by design.
- A small model can write a final summary that overstates what happened. The program overrides the summary when a tool fails, but it cannot catch every inaccurate claim.
- The project is a focused assessment prototype, not a production autonomous software engineer. Generated changes should be reviewed before being used in a real project.
