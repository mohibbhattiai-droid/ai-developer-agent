# Implementation and AI-use note

## What the project implements

The project contains a Python CLI agent that sends a task to an Ollama local-model API, requests a JSON implementation plan and ordered tool calls, runs only an allowlisted set of workspace tools, prints the tool-call inputs and results, and requests a final summary. The five tools are file listing, file reading, text search, file writing with overwrite protection, and Python AST syntax validation. Error paths and workspace path restrictions are covered by automated tests.

## Development approach and tools used

- **AI assistance:** ChatGPT was used to help design, draft, review, and document the code and tests. The repository should be reviewed and run by the submitter before final submission.
- **Runtime LLM:** the real implementation uses Ollama and the locally downloaded `qwen2.5:1.5b` model by default. No paid API is required.
- **Offline test mode:** `--demo` uses a deterministic mock client so the tool pipeline can be demonstrated even on a machine without Ollama. Demo mode is not represented as a real LLM run.
- **Testing performed while packaging:** the standard-library unit tests and offline smoke test should be run with the commands in the README. The live Ollama model was not available in the packaging environment, so live-model inference has not been verified here.

## Known limitations

The output quality depends on the chosen model. JSON tool-call planning may fail for some prompts; those failures are handled with a safe workspace inspection and an error message. Python syntax validation does not test business logic or execute code. The tool layer intentionally does not run arbitrary shell commands and blocks common credential/private-key paths. The submitter should run at least one live Ollama task, inspect the results, take a fresh screenshot of that run, and add the actual GitHub repository URL before submitting.
