# Evaluation data

`builtin.jsonl` contains 20 small regression cases authored for EduAgent and
distributed under the repository's MIT license. They test deterministic
contracts and scorer behavior; they do not establish general tutoring
effectiveness.

`tutor_live12_review.jsonl` contains 12 fictional, fixed-script English tutor
scenarios authored for EduAgent under MIT. It uses the independent
`eduagent.tutor-live-review.v1` schema and the `run-live` command. Eight cases
evaluate Agent behavior and evidence contracts; four are auxiliary teaching
cases. The file retains its draft review marker; actual authorization and
execution metadata are recorded separately in live reports. Answer keys,
future scripted inputs and scoring criteria are evaluator-only. This dataset
does not establish real learner gains.

`tutor_agent50_review.jsonl` expands the Agent primary development suite to
50 cases: the eight original primary cases remain byte-for-byte unchanged,
and 42 authored variants supply explicit contract templates, capability,
difficulty, and per-turn tool decision criteria. The original four teaching
auxiliary cases remain separate. Variants change facts, goals, history,
retrieval quotes, permission claims, and quiz answers. This is not a holdout.

Validate fixtures and execution contracts without a provider using
`eduagent-eval validate-live --dataset evals/datasets/tutor_agent50_review.jsonl`.
The evaluator-informed script is not a model and supplies no model success
or semantic scores. This expansion has not run the live model suite. A live
run plans 64 converse steps, up to 192 requests; the 42-request batch cap
remains, and repeated `--case-id` selects bounded subsets. The design,
readable cases, generator, and frozen manifest are in `docs/evals/`.

External datasets are not included in the package or repository. The
`eduagent-eval fetch mrbench` command downloads the pinned MRBench V1 revision
to a user cache and writes converted data beside the cached source.

MRBench is licensed under CC BY-SA 4.0 and is derived from MathDial and Bridge:

- https://github.com/kaushal0494/UnifyingAITutorEvaluation
- https://aclanthology.org/2025.naacl-long.57/

Converted MRBench files retain source IDs, split, revision, and license
metadata. They must not be treated as MIT-licensed project data.
