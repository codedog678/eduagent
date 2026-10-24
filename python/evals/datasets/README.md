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

External datasets are not included in the package or repository. The
`eduagent-eval fetch mrbench` command downloads the pinned MRBench V1 revision
to a user cache and writes converted data beside the cached source.

MRBench is licensed under CC BY-SA 4.0 and is derived from MathDial and Bridge:

- https://github.com/kaushal0494/UnifyingAITutorEvaluation
- https://aclanthology.org/2025.naacl-long.57/

Converted MRBench files retain source IDs, split, revision, and license
metadata. They must not be treated as MIT-licensed project data.
