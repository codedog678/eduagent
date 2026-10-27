"""冻结的三次配对门槛，拒绝缺失、重复和能力覆盖变化。"""

from evals.optimization.scoring import summarize


def verify_raw_row(row, case):
    import json
    from evals.live_scorers import score_live_case
    from evals.optimization.scoring import JUDGE_PROMPT, validate_judgment
    from evals.optimization.protocol import digest
    automatic = score_live_case(case, row["observed"])
    if automatic != row["automatic"]:
        raise ValueError("automatic score does not match raw evidence")
    score = row["score"]
    if automatic["execution_outcome"] != "completed":
        if score["task_success"] or score["score"] != 0 or score["automatic_passed"]:
            raise ValueError("incomplete execution cannot pass")
        return
    if score["judge_prompt_sha256"] != digest(JUDGE_PROMPT):
        raise ValueError("judge protocol changed")
    judgment = validate_judgment(json.dumps({key: score[key] for key in ("semantic", "decisions")}),
                                 case, row["observed"])
    passed = automatic["automatic_passed"] and all(c.passed for c in judgment.semantic)
    decisions = [d.required_tools_present and all(c.selection_correct and c.arguments_correct
                                                 for c in d.calls) for d in judgment.decisions]
    rate = sum(decisions) / len(decisions) if decisions else 0
    if (score["task_success"] != passed or score["automatic_passed"] != automatic["automatic_passed"]
            or score["decision_rate"] != rate or score["score"] != (.8 + .2 * rate if passed else 0)):
        raise ValueError("judge score does not match raw evidence")


def acceptance(baseline_rows, candidate_rows, *, holdout=False,
               targets=("full_history_retrieval", "grounded_history")):
    def keyed(rows):
        keys = [(r["repeat"], r["case_id"]) for r in rows]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate paired coverage")
        return dict(zip(keys, rows))
    bmap, cmap = keyed(baseline_rows), keyed(candidate_rows)
    if not bmap or bmap.keys() != cmap.keys():
        raise ValueError("paired comparison coverage mismatch")
    ids = {cid for _, cid in bmap}
    if set(bmap) != {(repeat, cid) for repeat in range(3) for cid in ids}:
        raise ValueError("exactly three complete paired repeats required")
    baseline_rows, candidate_rows = ([m[k] for k in sorted(bmap)] for m in (bmap, cmap))
    if any(b["capability"] != c["capability"] for b, c in zip(baseline_rows, candidate_rows)):
        raise ValueError("capability coverage mismatch")
    for row in baseline_rows + candidate_rows:
        if row.get("scoring_status", "completed") != "completed":
            raise ValueError("incomplete pair cannot be scored")
    baseline, candidate = summarize(baseline_rows), summarize(candidate_rows)
    regressions = [{"repeat": b["repeat"], "case_id": b["case_id"]}
                   for b, c in zip(baseline_rows, candidate_rows)
                   if b["score"]["automatic_passed"] and not c["score"]["automatic_passed"]]
    group_regressions = [
        name for name, score in baseline["by_capability"].items()
        if candidate["by_capability"][name]["task_success_rate"] < score["task_success_rate"]]

    def improves(b, c):
        return (c["task_success_rate"] > b["task_success_rate"] or not holdout
                and c["task_success_rate"] == b["task_success_rate"]
                and c["mean_decision_rate"] > b["mean_decision_rate"])
    repeats = []
    for repeat in range(3):
        b = summarize([r for r in baseline_rows if r["repeat"] == repeat])
        c = summarize([r for r in candidate_rows if r["repeat"] == repeat])
        repeats.append({"repeat": repeat, "baseline": b, "candidate": c, "improved": improves(b, c)})
    target_improved = any(
        name in baseline["by_capability"] and
        candidate["by_capability"][name]["task_success_rate"] >
        baseline["by_capability"][name]["task_success_rate"] for name in targets)
    passed = (improves(baseline, candidate) and sum(r["improved"] for r in repeats) >= 2
              and not regressions and not group_regressions and (not holdout or target_improved))
    return {"passed": passed, "baseline": baseline, "candidate": candidate,
            "automatic_regressions": regressions, "capability_regressions": group_regressions,
            "repeat_results": repeats, "target_improved": target_improved,
            "policy": "three paired repeats; >=2 improvements; zero hard/capability regressions",
            "interpretation": "Engineering gate, not statistical significance or learning gains"}
