import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


DRIVER_PATH = Path(__file__).parents[2] / "tools" / "run_policy_rehearsal.py"
SPEC = importlib.util.spec_from_file_location("run_policy_rehearsal", DRIVER_PATH)
driver = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(driver)


def campaign(tmp_path, *, simulation=False, mode="qualification", state="eligible"):
    root = tmp_path / "campaign"
    root.mkdir()
    (root / "campaign.json").write_text(
        json.dumps(
            {
                "config": {"simulation": simulation, "mode": mode},
                "protocol": {"schema": "eduagent.gepa.v3"},
                "state": state,
            }
        ),
        encoding="utf-8",
    )
    return root


def evidence(requests):
    return {
        "rehearsal_id": "test",
        "data_role": "controlled_rehearsal",
        "release_eligible": False,
        "actual_counts": {
            "requests": requests,
            "failed": 0,
            "interrupted": 0,
        },
        "source_revision": "a" * 64,
        "runtime_hash": "b" * 64,
        "protocol_hash": "c" * 64,
        "threshold_hashes": ["d" * 64],
        "provider_model_identity": ["fixture/provider"],
        "requested_counts": {"healthy": requests, "failure": 0},
        "cost": {"estimated_peak_cny": 0},
    }


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"simulation": True}, "campaign_simulation_not_release_eligible"),
        (
            {"mode": "exploratory"},
            "campaign_exploratory_not_release_eligible",
        ),
        ({"state": "holdout_passed"}, "campaign_not_eligible"),
    ],
)
def test_preflight_rejects_before_campaign_open(tmp_path, updates, code):
    root = campaign(tmp_path, **updates)
    calls = []

    def forbidden_loader(_root):
        calls.append(_root)
        raise AssertionError("Campaign.open must not run")

    with pytest.raises(driver.RehearsalRejected) as error:
        driver.preflight_campaign(root, campaign_loader=forbidden_loader)

    assert error.value.code == code
    assert calls == []


def test_preflight_requires_formal_qualification(tmp_path):
    root = campaign(tmp_path)

    class InvalidCampaign:
        def qualification_material(self):
            raise ValueError("missing eligible receipt")

    with pytest.raises(driver.RehearsalRejected) as error:
        driver.preflight_campaign(
            root,
            campaign_loader=lambda _root: InvalidCampaign(),
        )

    assert error.value.code == "campaign_qualification_invalid"
    assert "missing eligible receipt" not in error.value.detail


def test_promotion_cli_never_places_ops_token_in_subprocess_argv(tmp_path):
    observed = {}

    def runner(argv, **kwargs):
        observed["argv"] = argv
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout='{"state":"registered"}',
            stderr="",
        )

    cli = driver.PromotionCLI(python_dir=tmp_path, runner=runner)
    assert cli.run("show-head", "--environment", "rehearsal") == {
        "state": "registered"
    }
    assert "ops-secret-value" not in observed["argv"]
    assert observed["kwargs"]["capture_output"] is True


def test_ops_token_must_use_environment_or_stdin(monkeypatch):
    monkeypatch.setenv("REHEARSAL_OPS_TOKEN", "ops-secret-value")
    assert (
        driver.resolve_ops_token("env:REHEARSAL_OPS_TOKEN")
        == "ops-secret-value"
    )
    with pytest.raises(driver.RehearsalRejected) as error:
        driver.resolve_ops_token("ops-secret-value")
    assert error.value.code == "ops_token_transport_unsafe"


def test_rehearsal_token_is_used_once_and_not_returned(monkeypatch):
    class CLI:
        def run(self, *_args):
            return {
                "token": "sensitive-token-value",
                "expected_cohort": "candidate",
            }

    class API:
        submitted = []

        def submit(self, **kwargs):
            self.submitted.append(kwargs)
            return {"run_id": "run-1", "policy_binding": {"cohort": "candidate"}}

        def run_status(self, _run_id):
            return {"status": "completed", "usage": {"model_calls": 0}}

        def ops(self, _path):
            return {
                "usage": {"model_calls": 0, "estimated_cost_usd": "0"},
                "latency_ms": 1,
            }

    api = API()
    row = driver._issue_and_submit(
        cli=CLI(),
        api=api,
        rehearsal_id="test",
        learner_id="learner",
        request_id="request",
        fault_profile="none",
    )

    assert api.submitted == [
        {
            "token": "sensitive-token-value",
            "learner_id": "learner",
            "request_id": "request",
        }
    ]
    assert "sensitive-token-value" not in json.dumps(row)


def test_artifacts_are_atomic_and_secret_scanned(tmp_path):
    output = tmp_path / "evidence"
    with pytest.raises(driver.RehearsalRejected) as error:
        driver.publish_artifacts(
            output,
            evidence=evidence(0),
            requests=[{"unsafe": "ops-secret-value"}],
            deployments=[],
            health_windows=[],
            audits=[],
            metrics="",
            forbidden=["ops-secret-value"],
        )

    assert error.value.code == "artifact_secret_scan_failed"
    assert not output.exists()


@pytest.mark.parametrize(
    "sensitive",
    [
        '{"nonce":"raw-nonce"}',
        '{"token":"raw-token"}',
        "Authorization: Bearer raw-token",
        "X-EduAgent-Rehearsal: raw-token",
    ],
)
def test_artifacts_reject_sensitive_token_shapes(tmp_path, sensitive):
    output = tmp_path / "evidence"

    with pytest.raises(driver.RehearsalRejected) as error:
        driver.publish_artifacts(
            output,
            evidence=evidence(0),
            requests=[{"unsafe": sensitive}],
            deployments=[],
            health_windows=[],
            audits=[],
            metrics="",
            forbidden=[],
        )

    assert error.value.code == "artifact_secret_scan_failed"
    assert not output.exists()


def test_published_artifact_contract_contains_all_seven_files(tmp_path):
    output = tmp_path / "evidence"
    driver.publish_artifacts(
        output,
        evidence=evidence(1),
        requests=[{"run_id": "run-1"}],
        deployments=[],
        health_windows=[],
        audits=[],
        metrics="# HELP example fixture\n",
        forbidden=["ops-secret-value"],
    )

    assert {path.name for path in output.iterdir()} == set(
        driver.ARTIFACT_NAMES
    )
    summary = (output / "summary.md").read_text(encoding="utf-8")
    assert "controlled rehearsal traffic" in summary
    assert "Operational guardrails do not establish" in summary
