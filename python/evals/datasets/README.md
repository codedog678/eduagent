# Evaluation data

`builtin.jsonl` contains 20 small regression cases authored for EduAgent and
distributed under the repository's MIT license. They test deterministic
contracts and scorer behavior; they do not establish general tutoring
effectiveness.

External datasets are not included in the package or repository. The
`eduagent-eval fetch mrbench` command downloads the pinned MRBench V1 revision
to a user cache and writes converted data beside the cached source.

MRBench is licensed under CC BY-SA 4.0 and is derived from MathDial and Bridge:

- https://github.com/kaushal0494/UnifyingAITutorEvaluation
- https://aclanthology.org/2025.naacl-long.57/

Converted MRBench files retain source IDs, split, revision, and license
metadata. They must not be treated as MIT-licensed project data.
