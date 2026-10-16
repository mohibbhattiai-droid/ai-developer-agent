## Repository and assessment submission

**Public repository:** <https://github.com/mohibbhattiai-droid/ai-developer-agent>

This repository is already created and published. Reviewers can clone it with:

```powershell
git clone https://github.com/mohibbhattiai-droid/ai-developer-agent.git
cd ai-developer-agent
python --version
```

Follow the setup and live-run instructions above. To run the automated tests:

```powershell
python -m unittest discover -s tests -v
```

For the practical assessment, submit the repository URL above, this README, `IMPLEMENTATION_NOTE.md`, and genuine evidence of a working run. No OSYSTIC/client code or confidential material is included intentionally.

The current primary screenshots document the offline mock demo, the recorded unit-test output, and the generated Python file/syntax check. The offline demo is useful for verifying the tool pipeline, but it does **not** prove live Ollama inference. Before submitting, capture a screenshot from a successful run **without** `--demo`, with the local model shown and tool calls/results visible. Never label mock-demo output as a live-model run.

---

## Evidence included

The included screenshots are labelled honestly: the offline demo shows the tool pipeline working with a deterministic mock client, not live Ollama inference.

- [Offline demo run](screenshots/01_offline_demo.png)
- [Automated unit-test results](screenshots/02_unit_tests.png)
- [Generated Python file and syntax-check result](screenshots/03_generated_file.png)

For a stronger submission, take an additional screenshot after running a real task in live mode on your machine and add it to this folder. By default, each `--demo` run saves its generated sample under a fresh subfolder in `demo_workspace/`.
