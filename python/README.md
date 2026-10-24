# EduAgent Harness

This package contains the EduAgent backend, its reliable execution harness,
and offline and real-model evaluation tools.

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

The separate live command consumes model credits and requires DeepSeek Flash
with thinking disabled:

```bash
eduagent-eval run-live --dataset evals/datasets/tutor_live12_review.jsonl \
  --output eval-results/tutor-live12.json --max-requests 42 --max-cny 3
```

Reports distinguish automatic contracts from pending semantic and quality
review. Scripted fictional learners do not measure real learning gains.
