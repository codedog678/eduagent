# EduAgent Harness

This package contains the EduAgent backend, its reliable execution harness,
and offline evaluation tools.

Install the backend and development dependencies from the repository root:

```bash
python -m pip install -e "./python[dev]"
```

Run the API:

```bash
python -m api.main
```

The evaluation CLI is available after installation:

```bash
eduagent-eval validate
eduagent-eval run --suite builtin
```

Remote model credentials are optional. Without them, the application and
evaluation suite use deterministic local or scripted paths.
