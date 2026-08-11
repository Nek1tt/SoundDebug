"""
tests/test_dsp_post_report.py
Интеграционный тест: DSP-анализ файла → POST /reports/{job_id}.

Запуск (из корня проекта):
    # MOCK-режим (без Docker, без сети):
    python tests/test_dsp_post_report.py

    # LIVE-режим (нужен docker compose up):
    python tests/test_dsp_post_report.py --live
    GATEWAY_URL=http://localhost:8000 python tests/test_dsp_post_report.py --live

─────────────────────────────────────────────────────────────────────────────
LIVE-режим: полный flow через gateway (как делает настоящий воркер)

  Почему через gateway, а не напрямую в :8003?
    • report-service GET /reports/{id} требует Bearer JWT — без токена 401
    • report-service POST /reports/{id} проверяет что job существует в БД —
      без реального job_id будет 404
    • В продакшене DSP-воркер пишет в report-service напрямую (внутренняя сеть),
      а клиент читает через gateway с токеном. Тест воспроизводит оба пути.

  Flow в live-режиме:
    1. POST /auth/register  → новый тестовый юзер
    2. POST /auth/login     → JWT токен
    3. POST /jobs           → реальный job_id в БД (файл загружается в MinIO)
    4. POST /reports/{id}   → DSP-метрики (без токена, как воркер)
    5. GET  /reports/{id}   → читаем с токеном, проверяем совпадение
─────────────────────────────────────────────────────────────────────────────
"""

import sys
import os
import json
import time
import threading
import tempfile
import importlib.util
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

import numpy as np
import soundfile as sf

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DSP_DIR = os.path.join(ROOT, "services", "workers", "dsp_worker")
sys.path.insert(0, ROOT)

def _load_module(name: str, filepath: str):
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_analyzer_path = os.path.join(DSP_DIR, "analyzer.py")
_recs_path     = os.path.join(DSP_DIR, "recommendations.py")

for p in (_analyzer_path, _recs_path):
    if not os.path.exists(p):
        print(f"FATAL: не найден {p}")
        print("Убедись, что запускаешь из корня проекта.")
        sys.exit(1)

analyzer_mod = _load_module("analyzer",        _analyzer_path)
recs_mod     = _load_module("recommendations", _recs_path)

analyze                  = analyzer_mod.analyze
generate_recommendations = recs_mod.generate_recommendations

# ── CLI ───────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--live", action="store_true")
args, _ = parser.parse_known_args()

LIVE_MODE   = args.live
# В live-режиме работаем через gateway — единственный публичный порт
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8000")
# DSP-воркер пишет в report-service напрямую (минуя gateway и JWT)
REPORT_INTERNAL_URL = os.environ.get("REPORT_URL", "http://localhost:8003")
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "dev-internal-token")
MOCK_PORT   = 19999
MOCK_URL    = f"http://127.0.0.1:{MOCK_PORT}"

# ── Helpers ───────────────────────────────────────────────────────────────────
PASS = "✅"
FAIL = "❌"
_errors: list[str] = []

def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  {PASS} {name}")
    else:
        msg = f"  {FAIL} {name}"
        if detail:
            msg += f"  ←  {detail}"
        print(msg)
        _errors.append(name)

def section(title: str) -> None:
    print(f"\n{'─'*58}")
    print(f"  {title}")
    print(f"{'─'*58}")

# ── HTTP helpers (без внешних зависимостей) ───────────────────────────────────

def _post_json(
    url: str,
    payload: dict,
    token: str | None = None,
    service_token: str | None = None,
) -> tuple[int, dict]:
    body    = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if service_token:
        headers["X-Service-Token"] = service_token
    req = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"detail": str(e)}
    except Exception as exc:
        return 0, {"error": str(exc)}

def _get_json(url: str, token: str | None = None) -> tuple[int, dict]:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"detail": str(e)}
    except Exception as exc:
        return 0, {"error": str(exc)}

def _post_multipart(url: str, genre: str, wav_path: str,
                    token: str) -> tuple[int, dict]:
    """
    POST multipart/form-data для /jobs.
    Реализовано вручную через urllib — без requests/httpx.
    """
    import uuid as _uuid
    boundary = _uuid.uuid4().hex
    with open(wav_path, "rb") as f:
        file_data = f.read()

    filename = os.path.basename(wav_path)
    parts  = f"--{boundary}\r\n"
    parts += f'Content-Disposition: form-data; name="genre"\r\n\r\n'
    parts += f"{genre}\r\n"
    parts += f"--{boundary}\r\n"
    parts += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
    parts += "Content-Type: audio/wav\r\n\r\n"
    body = parts.encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    req = Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"detail": str(e)}
    except Exception as exc:
        return 0, {"error": str(exc)}

# ── WAV generator ─────────────────────────────────────────────────────────────

def _make_wav(duration: float = 12.0, sr: int = 44100, clipping: bool = False) -> str:
    n = int(sr * duration)
    t = np.linspace(0, duration, n, dtype=np.float32)
    rng = np.random.default_rng(42)
    y = (
        0.35 * np.sin(2 * np.pi * 440 * t)
        + 0.20 * np.sin(2 * np.pi * 880 * t)
        + 0.04 * rng.standard_normal(n).astype(np.float32)
    )
    if clipping:
        mid = n // 2
        y[mid : mid + 30] = 1.05
    y_r = y + 0.05 * np.random.default_rng(7).standard_normal(n).astype(np.float32)
    data = np.stack([y, y_r], axis=1)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, data, sr)
    tmp.close()
    return tmp.name

# ── Mock report-service ───────────────────────────────────────────────────────

_mock_store: dict[int, dict] = {}

class _MockHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def _send_json(self, code: int, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _job_id(self) -> int | None:
        parts = self.path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "reports":
            try:
                return int(parts[1])
            except ValueError:
                pass
        return None

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
            return
        job_id = self._job_id()
        if job_id is None:
            self._send_json(404, {"detail": "not found"})
            return
        if job_id not in _mock_store:
            self._send_json(404, {"detail": "Report not ready yet"})
            return
        self._send_json(200, {"job_id": job_id, "metrics": _mock_store[job_id]})

    def do_POST(self):
        job_id = self._job_id()
        if job_id is None:
            self._send_json(404, {"detail": "not found"})
            return
        length  = int(self.headers.get("Content-Length", 0))
        body    = json.loads(self.rfile.read(length))
        _mock_store[job_id] = body.get("metrics", {})
        self._send_json(201, {"job_id": job_id, "metrics": _mock_store[job_id]})

def _start_mock() -> HTTPServer:
    server = HTTPServer(("127.0.0.1", MOCK_PORT), _MockHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    for _ in range(20):
        try:
            urlopen(f"{MOCK_URL}/health", timeout=1)
            break
        except URLError:
            time.sleep(0.1)
    return server

# ─────────────────────────────────────────────────────────────────────────────
# LIVE FLOW: register → login → create job → post report → get report
# ─────────────────────────────────────────────────────────────────────────────

def run_live(wav_normal: str, wav_problem: str, metrics: dict,
             recs: list, payload: dict) -> None:

    section("L1. Проверяем доступность gateway и сервисов")
    st, health = _get_json(f"{GATEWAY_URL}/health")
    check(f"Gateway /health → 200 (got {st})", st == 200, str(health))
    if st != 200:
        print("\n  ⚠  Gateway недоступен. Убедись что запущен docker compose up.")
        print("     Запусти тест без --live для MOCK-режима.\n")
        return
    for svc in ("auth", "upload", "report"):
        ok = health.get("services", {}).get(svc) == "ok"
        check(f"  Сервис '{svc}' — ok", ok,
              f"got: {health.get('services', {}).get(svc)}")

    section("L2. Регистрация тестового пользователя")
    ts = int(time.time())
    email    = f"dsp_test_{ts}@example.com" # <--- Меняем на example.com
    password = "testpass_dsp_123"

    st, reg = _post_json(f"{GATEWAY_URL}/auth/register",
                         {"email": email, "password": password})
    check(f"POST /auth/register → 201 (got {st})", st == 201, str(reg))
    check("Ответ содержит id",    "id"    in reg, str(reg))
    check("Ответ содержит email", "email" in reg, str(reg))

    section("L3. Логин → получаем JWT")
    st, login = _post_json(f"{GATEWAY_URL}/auth/login",
                           {"email": email, "password": password})
    check(f"POST /auth/login → 200 (got {st})", st == 200, str(login))
    token = login.get("access_token", "")
    check("access_token получен", bool(token), str(login))
    if not token:
        print("  ⚠  Без токена продолжение невозможно.")
        return

    section("L4. Создание джоба (загружаем WAV в MinIO)")
    st, job = _post_multipart(
        f"{GATEWAY_URL}/jobs", "modern-pop", wav_normal, token
    )
    check(f"POST /jobs → 201 (got {st})", st == 201, str(job))
    job_id = job.get("id")
    check("Ответ содержит id",        job_id is not None, str(job))
    check("status == 'pending'",      job.get("status") == "pending", str(job))
    check("genre == 'modern-pop'",    job.get("genre")  == "modern-pop", str(job))
    if not job_id:
        print("  ⚠  Без job_id продолжение невозможно.")
        return

    print(f"\n      → job_id = {job_id}")

    section(f"L5. POST /reports/{job_id} — DSP-воркер пишет напрямую (без JWT)")
    # Именно так работает реальный dsp_worker: он обращается к report-service
    # напрямую по внутренней сети (REPORT_INTERNAL_URL), без токена.
    post_url = f"{REPORT_INTERNAL_URL}/reports/{job_id}"
    st, resp = _post_json(post_url, payload, service_token=INTERNAL_SERVICE_TOKEN)
    check(f"POST → 200 или 201 (got {st})", st in (200, 201),
          f"url={post_url} | {resp}")
    check("Ответ содержит job_id",    resp.get("job_id") == job_id, str(resp))
    check("Ответ содержит metrics",   "metrics" in resp, str(resp))
    if "metrics" in resp:
        check("metrics.loudness присутствует",
              "loudness" in resp["metrics"])
        check("metrics.recommendations присутствует",
              "recommendations" in resp["metrics"])

    section(f"L6. GET /reports/{job_id} — клиент читает через gateway (с JWT)")
    st, report = _get_json(f"{GATEWAY_URL}/reports/{job_id}", token=token)
    check(f"GET → 200 (got {st})", st == 200, str(report))
    if st == 200:
        check("job_id совпадает",
              report.get("job_id") == job_id, str(report))
        returned_lufs = report.get("metrics", {}).get("loudness", {}).get("lufs")
        expected_lufs = metrics.get("loudness", {}).get("lufs")
        check(f"LUFS совпадает ({expected_lufs} == {returned_lufs})",
              returned_lufs == expected_lufs,
              f"expected={expected_lufs}, got={returned_lufs}")
        check("recommendations в репорте",
              "recommendations" in report.get("metrics", {}))

    section(f"L7. Повторный POST — проблемный трек с клиппингом")
    try:
        m2   = analyze(wav_problem)
        r2   = generate_recommendations(m2, "techno")
        p2   = {"metrics": {**m2, "genre": "techno", "recommendations": r2}}
        st2, resp2 = _post_json(
            f"{REPORT_INTERNAL_URL}/reports/{job_id}",
            p2,
            service_token=INTERNAL_SERVICE_TOKEN,
        )
        check(f"Повторный POST → 200/201 (got {st2})", st2 in (200, 201), str(resp2))
        clip = resp2.get("metrics", {}).get("loudness", {}).get("clipping_count", 0)
        check("clipping_count > 0 в обновлённом репорте", clip > 0, f"got {clip}")
        high = [x for x in r2 if x["severity"] == "high"]
        check("Есть рекомендация severity=high", len(high) >= 1,
              str([x["id"] for x in r2]))
    except Exception as exc:
        check("Повторный POST — не упал", False, str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# ОБЩИЕ СЕКЦИИ (работают в обоих режимах)
# ─────────────────────────────────────────────────────────────────────────────

def run_common_dsp(wav_normal: str, wav_problem: str) -> tuple[dict, list, dict]:
    """Секции 1–2: анализ + сборка payload. Возвращает metrics, recs, payload."""

    section("1. DSP-анализ файла")
    metrics = {}
    try:
        metrics = analyze(wav_normal)
        check("analyze() не упал",                True)
        check("Возвращает dict",                  isinstance(metrics, dict))
        for key in ("loudness", "tonal", "stereo", "rhythm", "meta"):
            check(f"Содержит '{key}'",            key in metrics)
        lufs = metrics["loudness"].get("lufs")
        tp   = metrics["loudness"].get("true_peak_db")
        check(f"LUFS рассчитан ({lufs} LUFS)",    lufs is not None and isinstance(lufs, float))
        check(f"True Peak рассчитан ({tp} dBFS)", tp   is not None)
    except Exception as exc:
        check("analyze() не упал", False, str(exc))

    section("2. Сборка payload для report-service")
    genre = "modern-pop"
    recs  = generate_recommendations(metrics, genre) if metrics else []

    full_report = {**metrics, "genre": genre, "recommendations": recs}
    payload     = {"metrics": full_report}

    check("payload содержит ключ 'metrics'",       "metrics" in payload)
    check("metrics.loudness присутствует",         "loudness" in payload["metrics"])
    check("metrics.recommendations — список",      isinstance(recs, list))
    if recs:
        r0 = recs[0]
        for key in ("id", "category", "title", "severity", "description", "advice"):
            check(f"recommendations[0].{key} присутствует", key in r0)

    try:
        json_str = json.dumps(payload)
        check("payload сериализуется в JSON",      True)
        check("JSON не пустой",                    len(json_str) > 100)
    except (TypeError, ValueError) as e:
        check("payload сериализуется в JSON",      False, str(e))

    return metrics, recs, payload


def run_mock(wav_normal: str, wav_problem: str,
             metrics: dict, recs: list, payload: dict,
             mock_url: str, test_job_id: int) -> None:

    section(f"3. POST /reports/{test_job_id} — создание репорта [MOCK]")
    post_url = f"{mock_url}/reports/{test_job_id}"
    st, resp = _post_json(post_url, payload)
    check(f"HTTP статус 201 (got {st})",          st == 201, str(resp))
    check("Ответ содержит 'job_id'",              "job_id" in resp, str(resp))
    check(f"job_id == {test_job_id}",             resp.get("job_id") == test_job_id)
    check("Ответ содержит 'metrics'",             "metrics" in resp)
    if "metrics" in resp:
        check("metrics.loudness присутствует",    "loudness" in resp["metrics"])
        check("metrics.recommendations присутствует", "recommendations" in resp["metrics"])

    section(f"4. GET /reports/{test_job_id} — чтение [MOCK]")
    st, report = _get_json(f"{mock_url}/reports/{test_job_id}")
    check(f"GET статус 200 (got {st})",           st == 200, str(report))
    if st == 200:
        check("job_id совпадает",                 report.get("job_id") == test_job_id)
        ret_lufs = report.get("metrics", {}).get("loudness", {}).get("lufs")
        exp_lufs = metrics.get("loudness", {}).get("lufs")
        check(f"LUFS совпадает ({exp_lufs} == {ret_lufs})", ret_lufs == exp_lufs)

    section(f"5. Повторный POST — проблемный трек [MOCK]")
    try:
        m2  = analyze(wav_problem)
        r2  = generate_recommendations(m2, "techno")
        p2  = {"metrics": {**m2, "genre": "techno", "recommendations": r2}}
        check("Клиппинг обнаружен в метриках",
              m2["loudness"]["clipping_count"] > 0,
              f"count={m2['loudness']['clipping_count']}")
        high = [x for x in r2 if x["severity"] == "high"]
        check("Есть рекомендация severity=high",  len(high) >= 1)
        st2, resp2 = _post_json(f"{mock_url}/reports/{test_job_id}", p2)
        check(f"Повторный POST → 201 (got {st2})", st2 == 201, str(resp2))
        clip = resp2.get("metrics", {}).get("loudness", {}).get("clipping_count", 0)
        check("clipping_count > 0 в обновлённом репорте", clip > 0, f"got {clip}")
    except Exception as exc:
        check("Повторный POST — не упал", False, str(exc))

    section("6. Контракт payload (API contract MVP)")
    m = payload["metrics"]
    check("lufs присутствует",              "lufs" in m.get("loudness", {}))
    check("true_peak_db присутствует",      "true_peak_db" in m.get("loudness", {}))
    check("stereo_width присутствует",      "stereo_width" in m.get("stereo", {}))
    check("band_energy_db присутствует",    "band_energy_db" in m.get("tonal", {}))
    check("spectral_centroid_hz присутствует", "spectral_centroid_hz" in m.get("tonal", {}))
    if recs:
        r = recs[0]
        for key in ("id", "category", "title", "severity", "description", "advice"):
            check(f"rec.{key} присутствует", key in r)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

wav_normal  = _make_wav(duration=12.0, clipping=False)
wav_problem = _make_wav(duration=12.0, clipping=True)

try:
    metrics, recs, payload = run_common_dsp(wav_normal, wav_problem)

    if LIVE_MODE:
        # Проверяем доступность gateway — если нет, падаем в mock
        try:
            urlopen(f"{GATEWAY_URL}/health", timeout=3)
            mode_label = f"LIVE ({GATEWAY_URL})"
            print(f"\n  Режим: {mode_label}")
            print(f"  Gateway:         {GATEWAY_URL}")
            print(f"  Report internal: {REPORT_INTERNAL_URL}")
            run_live(wav_normal, wav_problem, metrics, recs, payload)
        except URLError:
            print(f"\n  ⚠  Gateway недоступен ({GATEWAY_URL}). Переключаемся на MOCK.")
            srv = _start_mock()
            mode_label = "MOCK (gateway недоступен)"
            run_mock(wav_normal, wav_problem, metrics, recs, payload, MOCK_URL, 99901)
            srv.shutdown()
    else:
        mode_label = "MOCK"
        print(f"\n  Режим: {mode_label}")
        srv = _start_mock()
        run_mock(wav_normal, wav_problem, metrics, recs, payload, MOCK_URL, 99901)
        srv.shutdown()

finally:
    os.unlink(wav_normal)
    os.unlink(wav_problem)

print(f"\n{'═'*58}")
if not _errors:
    print(f"  ✅ ВСЕ ТЕСТЫ ПРОШЛИ  [{mode_label}]")
else:
    print(f"  ❌ ПРОВАЛЕНО: {len(_errors)} тест(ов)  [{mode_label}]")
    for e in _errors:
        print(f"     • {e}")
print(f"{'═'*58}\n")

sys.exit(0 if not _errors else 1)
