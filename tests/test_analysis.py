import time


def test_create_run_and_fetch(client):
    create_response = client.post(
        "/api/v1/analysis/runs",
        json={"ticker": "WMT", "time_range": "earnings_window"},
    )
    assert create_response.status_code == 202
    run = create_response.json()
    run_id = run["id"]

    # eager celery may still need a short moment for commits in local process
    time.sleep(0.2)

    run_response = client.get(f"/api/v1/analysis/runs/{run_id}")
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["ticker"] == "WMT"

    events_response = client.get(f"/api/v1/analysis/runs/{run_id}/events")
    assert events_response.status_code == 200
    assert len(events_response.json()) >= 1

    report_response = client.get(f"/api/v1/analysis/runs/{run_id}/report")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["ticker"] == "WMT"
    assert report["stance"] in {"bullish", "neutral", "bearish"}
