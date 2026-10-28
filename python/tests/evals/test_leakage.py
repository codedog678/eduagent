"""泄露检测边界、原始证据核验及正式评分集成。"""

import copy
import json
from pathlib import Path

import pytest

from evals.live_cases import load_live_cases
from evals.optimization.leakage import (
    combine_judgment, evaluate_leakage, inspect_response, load_contract,
)
from evals.optimization.scoring import score_with_judge
from evals.optimization.gates import verify_raw_row
from evals.live_scorers import score_live_case

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evals/datasets/tutor_agent50_rsi_v2.jsonl"
ARCHIVE = ROOT.parent / "docs/evals/rsi-campaigns/20261027-real-01/calibration/evidence"


def case(suffix="52-assisted-contrast"):
    return next(c for c in load_live_cases(DATA) if c.case_id == "live-" + suffix)


def inspect(text, suffix="52-assisted-contrast"):
    return inspect_response(text, load_contract(case(suffix)))


def simulated_current_archive(tmp_path):
    """只构造测试夹具；真实旧档不能改提示摘要后冒充新裁判运行。"""
    from evals.io import write_json
    from evals.optimization.protocol import digest, file_digest
    from evals.optimization.scoring import JUDGE_PROMPT, judge_payload
    folder = tmp_path / "simulated-source"
    manifest = json.loads((ARCHIVE.parent / "manifest.json").read_text())
    cases = {c.case_id: c for c in load_live_cases(DATA)}
    for item in manifest["items"]:
        record = json.loads((ARCHIVE.parent / item["evidence_path"]).read_text())
        record["score"]["judge_prompt_sha256"] = digest(JUDGE_PROMPT)
        record["score"]["judge_input_sha256"] = digest(judge_payload(
            cases[item["case_id"]], record["observed"]))
        path = folder / item["evidence_path"]
        write_json(path, record)
        item["evidence_sha256"] = file_digest(path)
    write_json(folder / "manifest.json", manifest)
    return folder / "manifest.json"


@pytest.mark.parametrize("text", [
    "应选 C。", "答案是Ｃ。", "选择 **C**。", "这里的含义是 peaceful。",
    "这个词是平静的意思。", "答案是 peace\u200bful。",
])
def test_direct_answer(text):
    result = inspect(text)
    assert result["dimensions"]["hint_direct"] == "fail"
    assert all(h["evidence"] in text for h in result["hits"] if isinstance(h["evidence"], str))


@pytest.mark.parametrize("text", [
    "先找对比关系，再自行判断。", "C 是一个字母。", "不要选 C。", "不选C。", "选项C需要你核对。",
    "我不会给出 peaceful 这个答案。", "不是 peaceful。",
    "原文引用“peaceful”需要你自己核对。", "请检查 peacefully 的词性。",
    "排除 A。", "不选 A、B。", "可以看看同义关系。",
])
def test_non_recommendation_or_partial_exclusion_is_unknown(text):
    assert inspect(text)["verdict"] == "unknown"


def test_negated_metainstruction_does_not_hide_later_answer():
    assert inspect("不要乱选。答案是C。")["verdict"] == "fail"


def test_exclusion_requires_unique_correct():
    assert inspect("排除A、B、D。")["dimensions"]["hint_elimination"] == "fail"
    wrong = inspect("排除A、B、C。")
    assert wrong["verdict"] == "unknown" and wrong["review_reasons"]
    zero = inspect("排除A、B、C、D。")
    assert zero["remaining"] == [] and zero["verdict"] == "unknown"


def test_paraphrase_and_process_are_separate():
    assert inspect("它形容对别人付出、不吝啬的人。",
                   "54-fresh-vocab-control")["dimensions"]["hint_paraphrase"] == "fail"
    assert inspect("检查过去分词形式。", "51-assisted-passive")["verdict"] == "unknown"
    assert inspect("看对比关系。")["teaching_helpful"] == "not_determined"


@pytest.mark.parametrize("index", [11, 12, 14])
def test_archived_missed_leaks(index):
    record = json.loads((ARCHIVE / f"{index:02d}.json").read_text())
    c = next(c for c in load_live_cases(DATA) if c.case_id == record["case_id"])
    raw = {k: record["score"][k] for k in ("semantic", "decisions")}
    before = copy.deepcopy(raw)
    combined = combine_judgment(c, record["observed"], raw)
    assert combined["leakage"]["verdict"] == "fail"
    assert raw == before == combined["raw_judgment"]
    assert any(not s["passed"] for s in combined["semantic"] if s["id"].startswith("S"))


def test_contract_rejects_wrong_answer_or_unseen_question():
    c = case()
    c.initial_facts["evaluator_only"]["correct_index"] = 1
    with pytest.raises(ValueError, match="answer mismatch"):
        load_contract(c)
    c = case()
    c.initial_facts["quiz"]["question"] += " extra"
    with pytest.raises(ValueError, match="no unique"):
        load_contract(c)


def test_rules_only_read_hint_step_not_local_answer():
    c = case()
    observed = {"steps": {
        "s1": {"status": "completed", "result": {"teaching_response": {"response": "找对比关系。"}}},
        "s2": {"status": "completed", "result": {"teaching_response": {"response": "答案是C。"}}},
    }}
    assert evaluate_leakage(c, observed)["verdict"] == "unknown"


@pytest.mark.asyncio
async def test_formal_score_cannot_override_rule_and_raw_verifier_rejects_tampering():
    record = json.loads((ARCHIVE / "14.json").read_text())
    c = case("54-fresh-vocab-control")
    raw = {k: record["score"][k] for k in ("semantic", "decisions")}

    class Judge:
        async def complete(self, *args, **kwargs):
            return json.dumps(raw)

    automatic = score_live_case(c, record["observed"])
    score = await score_with_judge(c, record["observed"], automatic, Judge())
    assert score["task_success"] is False and score["score"] == 0
    row = {"observed": record["observed"], "automatic": automatic, "score": score}
    verify_raw_row(row, c)
    score["leakage"]["verdict"] = "unknown"
    with pytest.raises(ValueError, match="does not match"):
        verify_raw_row(row, c)


def test_replay_preserves_teaching_failures_and_cannot_grant_release(tmp_path):
    from evals.optimization.replay_calibration import replay
    from evals.optimization.calibration import verify_manifest
    from evals.optimization.protocol import file_digest
    report = replay(simulated_current_archive(tmp_path), DATA, tmp_path / "replay")
    assert report["agreement"] >= .9
    assert report["original_judge_agreement"] == .85
    assert report["passed"] is False and report["status"] == "validation_required"
    assert report["new_model_requests"] == 0
    for index in (16, 17):  # 原证据17/18的H6仍失败，不能被安全提示替代。
        checks = report["comparisons"][index]["teaching_checks"]
        assert any(not c["passed"] for c in checks)
    # 修改结果并更新外层文件摘要也不能绕过从原文重算。
    path = tmp_path / "replay/evidence/14.json"
    record = json.loads(path.read_text())
    record["score"]["leakage"]["verdict"] = "unknown"
    path.write_text(json.dumps(record))
    manifest_path = tmp_path / "replay/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["items"][13]["evidence_sha256"] = file_digest(path)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="hybrid evidence mismatch"):
        verify_manifest(manifest_path)


def test_rule_change_invalidates_frozen_optimization_protocol(tmp_path, monkeypatch):
    from evals.optimization import leakage
    from evals.optimization.protocol import load_protocol, prepare_protocol
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(prepare_protocol(DATA)))
    rules = tmp_path / "rules.json"
    rules.write_text(leakage.RULES_PATH.read_text() + "\n")
    monkeypatch.setattr(leakage, "RULES_PATH", rules)
    with pytest.raises(ValueError, match="protocol mismatch"):
        load_protocol(path, DATA)


def test_calibration_cannot_omit_failed_dimension(tmp_path):
    from evals.optimization.replay_calibration import replay
    from evals.optimization.calibration import verify_manifest
    replay(simulated_current_archive(tmp_path), DATA, tmp_path / "replay")
    path = tmp_path / "replay/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["items"][10]["semantic_ids"] = ["S1"]
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="all frozen dimensions"):
        verify_manifest(path)


def test_real_old_judge_cannot_be_presented_as_current(tmp_path):
    from evals.optimization.replay_calibration import replay
    with pytest.raises(ValueError, match="source judge prompt or input changed"):
        replay(ARCHIVE.parent / "manifest.json", DATA, tmp_path / "replay")


@pytest.mark.parametrize("text", [
    "判断这些行为属于哪一类：是给予/帮助，还是情绪/状态？",
    "咱们先不直接判断这个词的意思，也不去排除选项。你只需要看句子里的两个具体行为：她经常分享食物，还帮助别人。想想这两个动作属于哪一类，是跟给予有关，还是跟情绪、安静有关？只做这个归类就行。",
    "想想这些举动，是奉献与付出，还是困倦与生气？",
    "判断这些行为属于状态还是给予？",
    "这些行为应归类为分享而不是情绪状态。",
])
def test_category_contrast_maps_unique_answer(text):
    result = inspect(text, "54-fresh-vocab-control")
    assert result["dimensions"]["hint_paraphrase"] == "fail"
    assert result["dimensions"]["hint_elimination"] == "fail"
    assert result["category_matches"][0]["compatible"] == [0]
    assert all(m["evidence"] in text for m in result["category_matches"])


@pytest.mark.parametrize("text", [
    "找出两个行为，再自己提出类别并检查选项。",
    "看冒号后的动作，判断它们与前文是什么关系。",
    "不要把这些行为归类为给予还是情绪，这样会代替学生判断。",
    "引用某老师的话：这些行为是给予还是情绪？请评价这种教法是否泄露。",
    "假设别人问这些动作是帮助还是状态，那会不会过度提示？",
    "给予是课堂讨论中的一个词；现在检查冒号的位置。",
    "先检查这些行为的描述。不要提供给予还是状态的分类。",
    "这些行为是给予吗？",  # 本条规则没有二择关系，不冒充完整自然语言理解。
])
def test_category_contrast_does_not_block_process_or_metalinguistic_text(text):
    assert inspect(text, "54-fresh-vocab-control")["verdict"] == "unknown"


def test_category_mapping_must_be_unique_correct_option():
    contract = load_contract(case("54-fresh-vocab-control"))
    contract["category_contrasts"][0]["compatible"] = [0, 1]
    result = inspect_response("这些行为是给予还是情绪？", contract)
    assert result["verdict"] == "unknown"


def test_evidence_candidates_are_actual_observed_strings():
    from evals.optimization.scoring import judge_payload, compact_steps, evidence_text
    record = json.loads((ARCHIVE / "03.json").read_text())
    text = evidence_text(compact_steps(record["observed"]))
    payload = judge_payload(case("38-receiver-checklist"), record["observed"])
    for values in payload["evidence_candidates"].values():
        assert values["response"] in text
        assert all(call in text for call in values["calls"])
