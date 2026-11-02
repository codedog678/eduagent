"""父侧核验留档 Trace 实际响应正文及已查看图像；不冒称重新执行浏览器。"""

import importlib.util
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

spec = importlib.util.spec_from_file_location("history", "/tmp/m3-historical-evidence-preflight.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
c, ROOT, PRIMARY = h.c, h.ROOT, h.PRIMARY
A = ROOT / "docs/superpowers/reports/task9-leaf-authenticity-fix-evidence"
OUT = Path("/tmp/m3-task9-leaf-authenticity-parent-browser-verification.json")
HEAD = "9fcd6b62c95fa50e39c1ee264dcefc5574e0f50f"


def main():
    assert not OUT.exists()
    before = h.snapshot(ROOT), h.snapshot(PRIMARY)
    assert before[0]["head"] == HEAD
    audit = json.loads((A / "final-verification.json").read_bytes())
    traces = {}
    asset_responses = 0
    for name, declaration in audit["traces"].items():
        data = (A / name).read_bytes()
        assert c.sha(data) == declaration["sha256"], name
        matches, members = [], {}
        with zipfile.ZipFile(A / name) as archive:
            assert archive.testzip() is None, name
            for member in archive.infolist():
                c.safe_relative(member.filename)
                if member.is_dir():
                    continue
                body = archive.read(member)
                result = dict(bytes=len(body), sha256=c.sha(body))
                if member.filename.endswith((".trace", ".network")):
                    events = [json.loads(line) for line in body.splitlines() if line.strip()]
                    result["events"] = len(events)
                    if member.filename.endswith(".network") and "production" in name:
                        for event in events:
                            snapshot = event.get("snapshot", {})
                            request = snapshot.get("request", {})
                            response = snapshot.get("response", {})
                            if not request:
                                continue
                            assert request["method"] == "GET", name
                            url = request.get("url", "")
                            content = response.get("content", {})
                            resource = content.get("_file") or content.get("_sha1")
                            if "/assets/" not in url or not resource:
                                continue
                            resource = resource if resource.startswith("resources/") else "resources/" + resource
                            relative = c.safe_relative(urlparse(url).path.lstrip("/"))
                            actual = archive.read(resource)
                            assert response["status"] == 200, (name, url)
                            assert actual == (A / "frontend/dist" / relative).read_bytes(), (name, url)
                            matches.append(dict(url=url, bytes=len(actual), sha256=c.sha(actual), resource=resource))
                members[member.filename] = result
        assert members == declaration["members"], name
        assert matches == declaration["dist_asset_matches"], name
        asset_responses += len(matches)
        traces[name] = dict(members=len(members), production_asset_responses=len(matches))
    assert len(traces) == 84
    assert sum(t["members"] for t in traces.values()) == 2982
    assert asset_responses == 104
    productions = {}
    expected_gates = {
        "leaf_active_bad": set(),
        "leaf_active_valid": {"canary_health", "shadow_health"},
        "leaf_local_bad": {"shadow_health"},
        "leaf_local_valid": {"canary_health", "shadow_health"},
        "leaf_shadow_valid": {"shadow_health"},
    }
    for name, declaration in audit["production"].items():
        raw = json.loads((A / name).read_bytes())
        label, viewport = name.removeprefix("production-").removesuffix(".json").rsplit("-", 1)
        trace_names = [t for t in traces if t.startswith(label + "-output/") and viewport in t]
        assert len(trace_names) == 1, name
        assert raw["errors"] == declaration["errors"] == []
        assert raw["overflow"] == declaration["overflow"] <= 1
        assert len(raw["requests"]) == declaration["browser_gets"] == 6
        assert all(request["method"] == "GET" for request in raw["requests"])
        assert raw["scenario"] == declaration["scenario"]
        assert raw["viewport"] == declaration["viewport"]
        assert raw["scrollBefore"] == declaration["scroll_before"]
        assert raw["scrollAfter"] == declaration["scroll_after"]
        assert raw["assetEvidence"] == declaration["assets"]
        assert declaration["explicit_gets"] == 1 + len(raw["assetEvidence"]) == 4
        assert raw["requestContext"] == dict(detailGet=200, assetGets=3)
        with zipfile.ZipFile(A / trace_names[0]) as trace:
            assets = {}
            detail_responses = []
            for entry in trace.namelist():
                if not entry.endswith(".network"):
                    continue
                for line in trace.read(entry).splitlines():
                    event = json.loads(line)
                    snapshot = event.get("snapshot", {})
                    request = snapshot.get("request", {})
                    response = snapshot.get("response", {})
                    url = request.get("url", "")
                    resource = response.get("content", {}).get("_file") or response.get("content", {}).get("_sha1")
                    if not resource:
                        continue
                    resource = resource if resource.startswith("resources/") else "resources/" + resource
                    body = trace.read(resource)
                    if url in raw["hashes"]:
                        assert request["method"] == "GET" and response["status"] == 200
                        assets[url] = c.sha(body)
                    if url.endswith("/" + raw["body"]["deployment_id"]):
                        assert request["method"] == "GET" and response["status"] == 200
                        detail_responses.append(json.loads(body))
            assert assets == raw["hashes"], name
            assert raw["body"] in detail_responses, name
        for item in raw["assetEvidence"]:
            relative = c.safe_relative(urlparse(item["url"]).path.lstrip("/"))
            actual = (A / "frontend/dist" / relative).read_bytes()
            assert item["sha256"] == assets[item["url"]] == c.sha(actual)
            assert item["bytes"] == len(actual) and item["status"] == 200
        scroll_movement = False
        if viewport == "mobile":
            first, last = raw["scrollBefore"][0], raw["scrollAfter"][0]
            assert first["fullWidth"] > first["width"]
            assert 0 <= first["left"] <= first["fullWidth"] - first["width"]
            scroll_movement = last["left"] > first["left"]
            # current 无 gate table，捕获的是未执行横滚的 metrics table；
            # 保留这个边界，不用结构宽度代替实际滚动。其余场景观察到增量。
            if raw["scenario"] != "current":
                assert scroll_movement, name
        if raw["scenario"] in expected_gates:
            receipts = raw["body"]["gate_receipts"]
            source_gates = {r["gate_type"] for r in receipts if r["health_source"] is not None}
            assert source_gates == expected_gates[raw["scenario"]], name
        productions[name] = dict(trace=trace_names[0], browser_gets=6, explicit_gets=4,
                                 asset_bodies=len(assets), scenario=raw["scenario"],
                                 viewport=viewport, exact_detail_json_in_trace=True,
                                 actual_scroll_movement=scroll_movement if viewport == "mobile" else None)
    assert len(productions) == 26
    visuals = [
        ("screenshots/detail-final-production-v2-leaf_active_bad-desktop.png",
         "坏 Active 的两健康门禁 unknown 且无认证来源，审批及资格历史仍显示。"),
        ("screenshots/detail-final-production-v2-leaf_active_valid-mobile-left.png",
         "合法 Active 保留两条已消费前序来源及非本部署新观测提示；截图表格局部受横滚裁切。"),
        ("screenshots/detail-final-production-v2-leaf_local_bad-mobile-left.png",
         "坏 local Canary 不认证，独立合法 Shadow 保留；最新窗口摘要仍作为历史诊断显示。"),
        ("screenshots/policy-trace-mobile.png",
         "前端 Trace fixture 的固定部署、candidate/rehearsal 和 span 可读；此图不是生产 PG Trace 实证。"),
    ]
    assert (h.snapshot(ROOT), h.snapshot(PRIMARY)) == before
    result = dict(
        checked_at=datetime.now(UTC).isoformat(),
        role="parent archived Trace response and actual visual verification; not fresh browser execution/acceptance",
        head=HEAD, trace_files=84, trace_members_checked=2982, exact_asset_response_bodies=104,
        production_viewport_records=26, valid_final_viewport_records=24,
        preserved_invalid_scenario_records=2, browser_gets=156, explicit_context_gets=104,
        distinct_asset_bodies_matched_to_per_viewport_record=78,
        global_http_total="unknown", productions=productions,
        parent_actual_view_image_inspections=[
            dict(path=path, sha256=c.sha((A / path).read_bytes()), observation=observation)
            for path, observation in visuals
        ],
        parent_view_image_count=4, primary_review_head_index_venv_cache_unchanged=True,
        model_requests=0, new_model_cost_usd="0",
        mobile_scroll_movement_records=sum(p["actual_scroll_movement"] is True for p in productions.values()),
        mobile_current_metrics_scroll="not performed in this capture; do not claim per-scenario scroll proof",
        auxiliary_invalid_attempt=dict(
            shell_id="9b02c11e211b30f1f7165c421d1adaf5", exit=1,
            reason="parent assumed mobile scroll begins at zero for all captures; actual legal views began at 39/193 and current metrics capture did not scroll",
            product_failure=False,
        ),
    )
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("productions", "parent_actual_view_image_inspections")}, indent=2))


if __name__ == "__main__":
    main()
