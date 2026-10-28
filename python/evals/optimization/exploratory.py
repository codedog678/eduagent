"""探索性候选搜索与描述性配对比较；未知不补零，结果不能授予晋级资格。"""

import json
from pathlib import Path
from types import SimpleNamespace

from core.policy_store import atomic_json, digest
from evals.optimization.budget import OptimizationStopped
from evals.optimization.protocol import policy_artifact, validate_candidate, private_literals


def check_exploratory_calibration(report):
    # 这是试跑数据质量下限，不是校准或发布成功声明。
    counts = report["counts"]
    if (report.get("agreement") is None or report["agreement"] < .85
            or sum(counts.values()) < 12 or any(v < 1 for v in counts.values())):
        raise ValueError("insufficient observed calibration evidence for exploratory trial")
    return {"admitted": True, "promotion_eligible": False,
            "policy": ">=85% agreement, >=12 valid observations, all calibration groups observed"}


def known(row):
    return (row is not None and row.get("scoring_status") == "completed"
            and type(row.get("score", {}).get("task_success")) is bool)


def describe_comparison(baseline, candidate, expected):
    """两侧共同已知结果单列；全样本区间防止候选增加未知而虚增成功率。"""
    expected = set(expected)
    if not expected:
        raise ValueError("empty exploratory comparison")

    def keyed(rows):
        result = {}
        for row in rows:
            key = (row["repeat"], row["case_id"])
            if key in result or key not in expected:
                raise ValueError("duplicate or unexpected exploratory pair")
            result[key] = row
        return result

    bmap, cmap = keyed(baseline), keyed(candidate)
    wins, losses, ties, unknown = [], [], [], []
    paired_b, paired_c = [], []
    automatic_regressions = []
    for key in sorted(expected):
        b, c = bmap.get(key), cmap.get(key)
        item = {"repeat": key[0], "case_id": key[1]}
        if b and c and b["score"]["automatic_passed"] and not c["score"]["automatic_passed"]:
            automatic_regressions.append(item)
        if not (known(b) and known(c)):
            unknown.append({**item, "baseline_status": b.get("scoring_status") if b else "missing",
                            "candidate_status": c.get("scoring_status") if c else "missing"})
            continue
        paired_b.append(b)
        paired_c.append(c)
        bs, cs = b["score"]["task_success"], c["score"]["task_success"]
        (wins if cs and not bs else losses if bs and not cs else ties).append(item)

    def stats(rows, denominator):
        valid = [r for r in rows if known(r)]
        passed = sum(r["score"]["task_success"] for r in valid)
        unresolved = denominator - len(valid)
        return {"known": len(valid), "unknown": unresolved, "successes": passed,
                "known_success_rate": passed / len(valid) if valid else None,
                "all_cases_success_rate_bounds": [passed / denominator,
                                                  (passed + unresolved) / denominator],
                "mean_decision_rate": (sum(r["score"]["decision_rate"] for r in valid) / len(valid)
                                       if valid else None)}

    total, complete = len(expected), len(paired_b)
    net = len(wins) - len(losses)
    interval = [(net - len(unknown)) / total, (net + len(unknown)) / total]
    decision_delta = (sum(c["score"]["decision_rate"] - b["score"]["decision_rate"]
                          for b, c in zip(paired_b, paired_c)) / complete if complete else None)
    return {"total_pairs": total, "complete_pairs": complete, "unknown_pairs": unknown,
            "wins": wins, "losses": losses, "ties": ties,
            "baseline": stats(baseline, total), "candidate": stats(candidate, total),
            "paired_baseline": stats(paired_b, complete) if complete else None,
            "paired_candidate": stats(paired_c, complete) if complete else None,
            "net_wins": net, "success_rate_delta_bounds": interval,
            "paired_decision_rate_delta": decision_delta,
            "automatic_regressions": automatic_regressions,
            "signal": ("improvement_observed" if net > 0 else "regression_observed"
                       if net < 0 else "tool_decision_improvement_observed"
                       if decision_delta is not None and decision_delta > 0 else "no_success_rate_change"),
            "improvement_robust_to_unknown": interval[0] > 0,
            "promotion_eligible": False,
            "interpretation": "Exploratory development comparison; no significance or release claim."}


def run_exploration(campaign, service, *, adapter_factory):
    if campaign.config.get("mode") != "exploratory":
        raise ValueError("explicit exploratory mode required")
    if campaign.data["state"] == "exploration_completed":
        return "exploration_completed"
    if campaign.data["state"] not in {"prepared", "exploring", "preflight_passed"}:
        raise ValueError("invalid exploratory state")
    generations = campaign.config.get("exploration_generations", 2)
    repeats = campaign.config.get("exploration_repeats", 2)
    if generations not in (1, 2) or repeats not in (1, 2):
        raise ValueError("exploration supports one or two generations/repeats")
    protocol, cases = campaign._inputs()
    train = [cases[cid] for cid in protocol["reflection_train_ids"]]
    dev = [cases[cid] for cid in protocol["dev_validation_ids"]]
    forbidden = private_literals(list(cases.values()))
    folder = campaign.root / "exploration"
    initial = campaign.data["parent"]["components"]
    campaign.transition("exploring", {"prepared", "preflight_passed", "exploring"})
    candidates = []
    # 一个运行周期共用事件循环与LLM客户端，避免关闭循环后重用HTTP连接。
    adapter = adapter_factory(list(cases.values()), protocol["reflection_train_ids"],
                              campaign.budget, folder / "executions", service=service)
    adapter.__enter__()
    adapter.tolerate_judge_failure = True

    def evaluate(group, selected, policy):
        rows = []
        for case in selected:
            cache = folder / "groups" / group / f"{digest(case.case_id)}.json"
            binding = digest({"campaign": campaign.binding, "group": group,
                              "case_id": case.case_id, "policy": policy})
            if cache.exists():
                saved = json.loads(cache.read_text())
                if saved["binding"] != binding or digest(saved["row"]) != saved["row_sha256"]:
                    raise ValueError("exploratory cached observation changed")
                row = saved["row"]
            else:
                row = adapter.evaluate_rows([case], policy)[0]
                atomic_json(cache, {"binding": binding, "row": row, "row_sha256": digest(row)})
            rows.append(row)
        return rows

    def propose(index, parent, train_rows):
        path = folder / "proposals" / f"generation-{index}.json"
        valid = sorted((r for r in train_rows if known(r)),
                       key=lambda r: (r["score"]["score"], r["case_id"]))
        chosen = valid[:campaign.config["minibatch"]]
        if not chosen:
            raise OptimizationStopped("no known training observations for reflection")
        input_binding = digest({"campaign": campaign.binding, "parent": parent,
                                "training_rows": chosen})
        if path.exists():
            saved = json.loads(path.read_text())
            if saved["input_binding"] != input_binding:
                raise ValueError("exploration proposal input changed")
            validate_candidate(saved["candidate"], forbidden)
            return saved["candidate"]
        feedback = adapter.make_reflective_dataset(
            parent, SimpleNamespace(trajectories=chosen), ["retrieval_rules"])
        result = adapter.propose_new_texts(parent, feedback, ["retrieval_rules"])
        validate_candidate(result, forbidden)
        atomic_json(path, {"input_binding": input_binding, "candidate": result,
                           "policy": policy_artifact(result), "parent_sha256": digest(parent),
                           "generation": index, "training_case_ids": [r["case_id"] for r in chosen],
                           "promotion_eligible": False})
        return result

    try:
        previous, train_rows = initial, evaluate("train-baseline", train, initial)
        for index in range(1, generations + 1):
            proposal = propose(index, previous, train_rows)
            candidates.append(proposal)
            train_rows = evaluate(f"train-candidate-{index}", train, proposal)
            previous = proposal
        # 生成两代都只使用训练资料；此后一次性比较，验证结果不反馈到提案。
        policies = {"baseline": initial, **{f"candidate-{i}": p for i, p in enumerate(candidates, 1)}}
        rows = {label: [] for label in policies}
        order = list(policies)
        for repeat in range(repeats):
            for index, case in enumerate(dev):
                # 同例相邻评估；交替顺序，缓存按重复隔离，不把首次观测当重复。
                labels = order if (repeat + index) % 2 == 0 else list(reversed(order))
                for label in labels:
                    result = evaluate(f"dev-{repeat}-{label}", [case], policies[label])[0]
                    rows[label].append({**result, "repeat": repeat, "comparison_label": label})
        expected = {(repeat, case.case_id) for repeat in range(repeats) for case in dev}
        comparisons = {}
        for label in policies:
            if label == "baseline":
                continue
            result = describe_comparison(rows["baseline"], rows[label], expected)
            result["repeats"] = [
                describe_comparison([r for r in rows["baseline"] if r["repeat"] == repeat],
                                    [r for r in rows[label] if r["repeat"] == repeat],
                                    {(repeat, c.case_id) for c in dev})
                for repeat in range(repeats)]
            capabilities = sorted({r["capability"] for r in rows["baseline"]})
            result["by_capability"] = {
                cap: describe_comparison([r for r in rows["baseline"] if r["capability"] == cap],
                                         [r for r in rows[label] if r["capability"] == cap],
                                         {(r["repeat"], r["case_id"]) for r in rows["baseline"]
                                          if r["capability"] == cap})
                for cap in capabilities}
            comparisons[label] = result
        # 只给出值得人工复核的候选，不调用正式choose_candidate/acceptance/register。
        ranked = sorted(comparisons, key=lambda label: (
            comparisons[label]["net_wins"], comparisons[label]["paired_decision_rate_delta"] or 0,
            comparisons[label]["complete_pairs"]), reverse=True)
        best = comparisons[ranked[0]]
        recommendation = ranked[0] if (best["net_wins"] > 0 or best["net_wins"] == 0
                                       and (best["paired_decision_rate_delta"] or 0) > 0) else None
        report = {"mode": "exploratory", "algorithm": "bounded_training_reflection",
                  "simulation": campaign.config["simulation"],
                  "binding": campaign.binding, "source_revision": campaign.config["source_revision"],
                  "calibration_sha256": campaign.config.get("calibration_sha256"),
                  "policies": policies, "rows": rows, "comparisons": comparisons,
                  "candidate_for_review": recommendation, "promotion_eligible": False,
                  "training_ids": protocol["reflection_train_ids"],
                  "development_ids": protocol["dev_validation_ids"],
                  "budget": campaign.budget.summary()}
        atomic_json(folder / "report.json", report)
        campaign.data["exploration_report_sha256"] = digest(report)
        campaign.transition("exploration_completed", {"exploring"}, candidate_for_review=recommendation)
    finally:
        adapter.__exit__(None, None, None)
        atomic_json(campaign.root / "budget.json", campaign.budget.summary())
        atomic_json(campaign.root / "request-ledger.json", {"requests": campaign.budget.ledger})
    return campaign.data["state"]
