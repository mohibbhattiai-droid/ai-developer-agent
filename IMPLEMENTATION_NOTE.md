# Implementation and AI-use note

## What I implemented

This is a Python command-line AI Developer Agent. It accepts a natural-language task, asks a local LLM for a short implementation plan and ordered tool calls, executes approved tools in a bounded workspace, prints the results, and summarizes the run.

The five tools are `list_files`, `read_file`, `search_files`, `write_file`, and `check_python_syntax`. The tool layer blocks unsafe paths and likely secret files, refuses unapproved overwrites, and returns controlled errors. The syntax checker parses source with `ast.parse`; it does not execute generated code.

## My contribution

I set up the Python project and local Ollama environment, refined the prompts and tool behavior, integrated the modules, troubleshot errors, ran and reviewed the program, and prepared the documentation and testing evidence. I reviewed the code and used the AI assistance described below; I am not claiming that every line was written without assistance.

## AI tools and runtime

- **ChatGPT:** assisted with design, code drafting, code review, troubleshooting, test ideas, and documentation.
- **Ollama + `qwen2.5:1.5b`:** the intended live model, accessed through the local `/api/chat` endpoint. No paid API key is required.
- **Offline demo:** `python main.py --demo` uses a deterministic mock client, not an LLM. It verifies the tool pipeline only.

## Verification and evidence

The GitHub Actions workflow ran on Python 3.10, 3.11, and 3.12. All three jobs passed, including **13 unit tests and the offline demo smoke test** in each job. [View the CI run](https://github.com/mohibbhattiai-droid/ai-developer-agent/actions/runs/38979797775). The report is saved in [`examples/test_results.txt`](examples/test_results.txt).

[`screenshots/live_ollama_run.png`](screenshots/live_ollama_run.png) shows a real live Ollama run from before the latest overwrite-intent safety guard. It illustrates the live interaction, but should be recaptured from the final revision for perfectly current visual evidence. Do not present the offline mock demo as real LLM inference.

## Limitations

- Small models can produce weak plans, malformed responses, or unsuitable code.
- Planning is single-pass; the agent does not inspect tool results and re-plan.
- Syntax checking does not establish correctness, and generated code is not executed.
- Arbitrary shell commands and test execution by the agent are intentionally unsupported.
- This is an assessment prototype, not a production autonomous coding system.
