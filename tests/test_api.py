"""Real public end-to-end smoke test for a running MVP stack."""

from __future__ import annotations

import io
import math
import os
import struct
import sys
import time
import wave

import requests

BASE = os.environ.get("SOUNDDEBUG_API_URL", "http://localhost:8080/api").rstrip("/")


def wav_fixture(seconds: int = 5, rate: int = 44100) -> io.BytesIO:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(2)
        target.setframerate(rate)
        frames = bytearray()
        for index in range(seconds * rate):
            value = int(0.2 * 32767 * math.sin(2 * math.pi * 440 * index / rate))
            frames.extend(struct.pack("<hh", value, value))
        target.writeframes(frames)
    output.seek(0)
    return output


def require(response: requests.Response, expected: int) -> dict:
    if response.status_code != expected:
        raise AssertionError(f"{response.request.method} {response.url}: {response.status_code} {response.text}")
    return response.json()


def main() -> int:
    health = require(requests.get(f"{BASE}/health", timeout=10), 200)
    print("health:", health["status"])

    email = f"e2e-{int(time.time())}@example.com"
    password = "sounddebug-e2e-password"
    require(requests.post(f"{BASE}/auth/register", json={"email": email, "password": password}, timeout=10), 201)
    login = require(requests.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=10), 200)
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    job = require(
        requests.post(
            f"{BASE}/jobs",
            headers=headers,
            data={"genre": "electronic", "audio_ml_analysis": "false"},
            files={"file": ("fixture.wav", wav_fixture(), "audio/wav")},
            timeout=30,
        ),
        201,
    )
    print("job:", job["id"])

    deadline = time.time() + 240
    pending_since = time.time()
    while time.time() < deadline:
        state = require(requests.get(f"{BASE}/jobs/{job['id']}/status", headers=headers, timeout=10), 200)
        print(f"status: {state['status']} {state['progress']}%")
        if state["status"] != "pending" or state["progress"] != 0:
            pending_since = time.time()
        elif time.time() - pending_since >= 30:
            raise AssertionError(
                "job stayed pending at 0% for 30 seconds; the DSP worker is not "
                "consuming the 'dsp' queue. Run: docker compose logs --tail 200 dsp-worker"
            )
        if state["status"] == "failed":
            raise AssertionError("worker marked the job as failed")
        if state["status"] == "done":
            break
        time.sleep(2)
    else:
        raise AssertionError("analysis timed out")

    report = require(requests.get(f"{BASE}/reports/{job['id']}", headers=headers, timeout=10), 200)
    for key in ("loudness", "tonal", "stereo", "rhythm", "recommendations", "additional_findings", "technical_details"):
        if key not in report["metrics"]:
            raise AssertionError(f"report has no {key}")
    metrics = report["metrics"]
    if metrics.get("report_version") != "p0-trustworthy-diagnostics-1":
        raise AssertionError(f"unexpected report version: {metrics.get('report_version')}")
    if len(metrics["recommendations"]) > 3:
        raise AssertionError("P0 main screen contract allows at most three recommendations")
    for finding in metrics["recommendations"] + metrics["additional_findings"]:
        if finding.get("classification") not in {"FACT", "REFERENCE_DIFFERENCE", "HYPOTHESIS"}:
            raise AssertionError(f"invalid finding class: {finding}")
    shares = metrics["tonal"].get("band_energy_pct", {})
    if not shares or abs(sum(shares.values()) - 100.0) > 0.1:
        raise AssertionError(f"invalid tonal power shares: {shares}")

    require(
        requests.post(
            f"{BASE}/reports/{job['id']}/feedback",
            headers=headers,
            json={"rating": 5, "comment": "automated e2e"},
            timeout=10,
        ),
        201,
    )
    delete_response = requests.delete(f"{BASE}/jobs/{job['id']}", headers=headers, timeout=10)
    if delete_response.status_code != 204:
        raise AssertionError(f"delete failed: {delete_response.status_code} {delete_response.text}")
    print("E2E PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"E2E FAIL: {exc}", file=sys.stderr)
        raise
