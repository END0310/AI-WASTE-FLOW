from app.ai.errors import ProviderRateLimited, ProviderUnavailable
from app.core.config import settings
from tests.conftest import snapshot, valid_output

URL = "/api/v1/optimization/runs/{}/analysis"


def test_health(client):
    assert client.get("/health").json()["status"] == "healthy"


def test_happy_path_persists_and_returns_spec_shape(client, use_fake, seed_run):
    fake = use_fake([valid_output()])
    run_id = seed_run()
    res = client.post(URL.format(run_id), json={"analysis_type": "full"})
    assert res.status_code == 200, res.text
    body = res.json()
    for k in ("analysis_id", "run_id", "status", "provider", "model", "prompt_version", "result", "created_at"):
        assert k in body
    assert body["status"] == "completed" and body["result"]["summary"]
    # instructions and data are sent as separate parts (Spec 5.3)
    assert len(fake.calls[0]) == 2 and fake.calls[0][1].startswith("DATA")

    detail = client.get(f"/api/v1/ai/analyses/{body['analysis_id']}?include_input=true").json()
    assert detail["validation_status"] == "valid"
    assert "GEMINI" not in str(detail["input_payload"]).upper()   # no secrets persisted


def test_invalid_output_gets_one_corrective_retry(client, use_fake, seed_run):
    bad = valid_output()
    bad["recommendations"][0]["evidence"] = ["made_up:key"]
    fake = use_fake([bad, valid_output()])
    res = client.post(URL.format(seed_run()))
    assert res.status_code == 200
    assert len(fake.calls) == 2 and "rejected" in fake.calls[1][-1]


def test_invalid_twice_is_rejected_and_never_shown(client, use_fake, seed_run):
    bad = valid_output()
    bad["summary"] = "Hemat Rp70.000 dibanding baseline."
    use_fake([bad, bad])
    res = client.post(URL.format(seed_run()))
    assert res.status_code == 502
    err = res.json()["error"]
    assert err["code"] == "AI_OUTPUT_INVALID" and err["layer"] == "OutputValidation"
    detail = client.get(f"/api/v1/ai/analyses/{err['analysis_id']}").json()
    assert detail["validation_status"] == "invalid" and detail["result"] is None


def test_infeasible_run_never_calls_gemini(client, use_fake, seed_run):
    fake = use_fake([])
    s = snapshot(solver={"status": "Infeasible", "name": "PuLP", "version": "2.8"})
    res = client.post(URL.format(seed_run(s)))
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "RUN_NOT_ELIGIBLE"
    assert "infeasible" in res.json()["error"]["message"].lower()
    assert fake.calls == []
    assert client.get("/api/v1/ai/history").json()["total"] == 0


def test_period_mismatch_never_calls_gemini(client, use_fake, seed_run):
    fake = use_fake([])
    res = client.post(URL.format(seed_run(snapshot(is_period_mismatched=True))))
    assert res.status_code == 422 and res.json()["error"]["code"] == "PAYLOAD_NOT_READY"
    assert fake.calls == []


def test_unknown_run(client, use_fake):
    use_fake([])
    assert client.post(URL.format("nope")).status_code == 404


def test_provider_outage_is_safe_and_recorded(client, use_fake, seed_run):
    use_fake([ProviderUnavailable("Gemini sedang tidak tersedia (503)")])
    run_id = seed_run()
    res = client.post(URL.format(run_id))
    assert res.status_code == 503 and res.json()["error"]["retryable"] is True
    assert res.headers.get("Retry-After")
    hist = client.get(f"/api/v1/ai/history?run_id={run_id}&validation_status=failed").json()
    assert hist["total"] == 1 and hist["items"][0]["error_code"] == "AI_UNAVAILABLE"
    # optimization run is still readable
    assert client.get(f"/api/v1/optimization/runs/{run_id}").status_code == 200


def test_rate_limit(client, use_fake, seed_run):
    use_fake([ProviderRateLimited("quota")])
    assert client.post(URL.format(seed_run())).status_code == 429


def test_missing_key_without_mock_is_not_faked(client, seed_run, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(settings, "AI_ALLOW_MOCK", False)
    res = client.post(URL.format(seed_run()))
    assert res.status_code == 503 and res.json()["error"]["code"] == "AI_NOT_CONFIGURED"


def test_mock_provider_is_explicit_and_valid(client, seed_run, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(settings, "AI_ALLOW_MOCK", True)
    res = client.post(URL.format(seed_run(snapshot(data_source="synthetic"))))
    assert res.status_code == 200, res.text
    assert res.json()["provider"] == "mock"
    assert any("sintetis" in l for l in res.json()["result"]["limitations"])


def test_duplicate_request_cooldown(client, use_fake, seed_run, monkeypatch):
    use_fake([valid_output(), valid_output()])
    run_id = seed_run()
    first = client.post(URL.format(run_id)).json()
    monkeypatch.setattr(settings, "AI_ANALYSIS_COOLDOWN_SECONDS", 60)
    res = client.post(URL.format(run_id))
    assert res.status_code == 429
    assert res.json()["error"]["analysis_id"] == first["analysis_id"]


def test_history_filters(client, use_fake, seed_run):
    use_fake([valid_output(), ProviderUnavailable("x")])
    a, b = seed_run(), seed_run()
    client.post(URL.format(a))
    client.post(URL.format(b))
    assert client.get("/api/v1/ai/history").json()["total"] == 2
    assert client.get("/api/v1/ai/history?validation_status=valid").json()["items"][0]["run_id"] == a
    assert client.get("/api/v1/ai/history?date_from=2999-01-01T00:00:00").json()["total"] == 0
