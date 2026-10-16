# AI Developer Agent

A small, local-first Python developer agent for a practical assessment. Give it a natural-language development task; it asks a local LLM to analyze the request and produce a plan, executes an ordered set of approved tools, displays each tool call and result, then asks the LLM for an honest summary.

> **Free by design:** the live mode uses Ollama on your computer, so it does not need a paid API key or charge per request. Downloading and running a model still uses disk space, RAM, and electricity. This repository has no third-party Python package dependencies.

## What it can do

- Analyze a task and produce a short implementation plan.
- Use a local LLM through Ollama's `/api/chat` endpoint (default model: `qwen2.5:1.5b`).
- Call five executable tools: `list_files`, `read_file`, `search_files`, `write_file`, and `check_python_syntax`.
- Show tool names, arguments, success/failure status, and structured results in the terminal.
- Handle model connection errors, malformed model responses, bad tool arguments, missing files, and syntax errors without crashing the whole run.
- Keep file access inside a selected workspace. Protect existing files from being overwritten unless `overwrite=true` is explicitly included in a tool call.
- Check Python syntax with `ast.parse`; it **does not execute** the generated Python file.

## Requirements

- Windows 10/11, macOS, or Linux.
- Python 3.10 or newer.
- [Ollama](https://ollama.com/download) for live LLM mode.
- Enough memory/disk for the chosen local model. The default 1.5B model is a starting point for modest hardware; performance can vary by machine.

## Setup (Windows / PowerShell)

Open PowerShell in this repository folder.

1. Check Python:

   ```powershell
   python --version
   ```

2. Install Ollama from <https://ollama.com/download> and make sure it is running.

3. Download the free model (one-time download):

   ```powershell
   ollama pull qwen2.5:1.5b
   ollama list
   ```

   If the model is not listed or Ollama reports that it is not running, resolve that first. On systems where Ollama is not automatically running, start its service using the instructions for your OS.

4. (Optional) Create a virtual environment. The application uses only the Python standard library, but a venv keeps the project isolated:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   There are no packages to install from `requirements.txt`.

## Run the agent

Live mode uses the actual local model:

```powershell
python main.py --task "Create a Python module called greeting.py with a greet(name) function, then check its syntax."
```

The agent uses the `workspace/` folder by default. To choose another workspace:

```powershell
python main.py --task "Find TODO comments in the project and report the files" --workspace .\workspace
```

To use a different already-installed Ollama model or a non-default Ollama host:

```powershell
python main.py --model qwen2.5:1.5b --host http://localhost:11434 --task "Create a short README for this tool"
```

You can also run `python main.py` without `--task`; the program will prompt for a task. The optional `OLLAMA_MODEL` and `OLLAMA_HOST` environment variables set the same defaults.

### Offline smoke test (no Ollama required)

```powershell
python main.py --demo
```

This proves the tool pipeline, logging, file creation, and syntax-check path work without downloading a model. **The offline demo uses a deterministic mock client, not an LLM.** For the assessment's live-model demonstration, run the normal command after Ollama and the model are installed. Demo output is saved under `demo_workspace/` by default.

## Example task

> Create `calculator.py` with `add(a, b)` and `subtract(a, b)` functions. Then check its Python syntax.

A normal run displays:

1. The requested task and selected model.
2. An implementation plan.
3. A numbered `TOOL CALL` section for each tool, with arguments, result status, and structured output.
4. A final LLM-generated summary tied to the observed tool results.

The exact plan and output depend on the local model's response.

## Architecture

```text
Natural-language task
        |
        v
OllamaClient -- POST /api/chat --> Local Ollama model
        |                            |
        |<--- JSON plan + tool calls--|
        v
DeveloperAgent
        |
        v
WorkspaceTools (allowlisted tools; workspace path checks)
  |-- list_files
  |-- read_file
  |-- search_files
  |-- write_file
  `-- check_python_syntax (AST parse; does not execute code)
        |
        v
Visible tool log + results --> LLM summary --> Terminal
```

- `ai_dev_agent/agent.py`: Ollama HTTP client, prompting, response parsing, orchestration, and summary.
- `ai_dev_agent/tools.py`: confined file tools and syntax checker.
- `ai_dev_agent/cli.py`: command-line options and human-readable execution log.
- `ai_dev_agent/demo.py`: deterministic offline mock used only for a smoke test.
- `tests/`: automated tests that do not need a live LLM.

## Tests

Run all tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```

The 12 tests cover file creation/reading, listing/search, explicit overwrite protection, traversal/absolute-path rejection, likely secret-file blocking, Python syntax validation, unknown tools, malformed overwrite flags, and mock-LLM orchestration/error handling. They do not require Ollama or internet access.

## Safety boundaries and limitations

- The agent can only operate on files within its configured workspace; absolute paths and `..` traversal are rejected.
- Existing files are not overwritten unless the model explicitly requests `overwrite=true` with a Boolean value. Review the tool log before using generated changes.
- Common credential/key files and directories (such as `.env`, `.ssh`, `.aws`, and private-key files) are blocked or excluded from search/list results. This is a guardrail, not a substitute for keeping secrets out of project workspaces.
- It deliberately does not provide unrestricted shell access or execute generated source code. The syntax checker only parses Python syntax; it does not prove functional correctness.
- The model chooses tool calls using a JSON prompt. Small local models may occasionally return malformed JSON or choose an unsuitable tool; those errors are logged and handled, but model quality is not guaranteed.
- This is a focused assessment prototype, not a production autonomous coding system. Review changes before using them in a real project.

## GitHub submission

1. Create a new empty repository on your GitHub account, for example `ai-developer-agent`.
2. From this folder, run:

   ```powershell
   git init
   git add .
   git commit -m "Build AI Developer Agent assessment"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/ai-developer-agent.git
   git push -u origin main
   ```

3. Replace `YOUR-USERNAME` with your GitHub username and submit the actual repository URL after checking that the README, tests, and screenshots are present. A public repository URL can only be provided after you create/push it under your account.

## Evidence included

The included screenshots are labelled honestly: the offline demo shows the tool pipeline working with a deterministic mock client, not live Ollama inference.

- [Offline demo run](screenshots/01_offline_demo.png)
- [Automated unit-test results](screenshots/02_unit_tests.png)
- [Generated Python file and syntax-check result](screenshots/03_generated_file.png)

For a stronger submission, take an additional screenshot after running a real task in live mode on your machine and add it to this folder. By default, each `--demo` run saves its generated sample under a fresh subfolder in `demo_workspace/`.
