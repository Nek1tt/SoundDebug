"""
tests/test_api.py
Автоматический тест всего flow: регистрация → логин → джоб → статус → репорт.

Запуск:
  pip install requests
  python tests/test_api.py
"""
import requests
import json
import sys
import io

BASE = "http://localhost:8000"
PASS = "✅"
FAIL = "❌"

errors = []


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  {PASS} {name}")
    else:
        print(f"  {FAIL} {name}  ←  {detail}")
        errors.append(name)


def section(title: str):
    print(f"\n{'─'*50}")
    print(f"  {title}")
    print(f"{'─'*50}")


# ─────────────────────────────────────────────────────
# 1. HEALTH
# ─────────────────────────────────────────────────────
section("1. Health Check")
try:
    r = requests.get(f"{BASE}/health", timeout=5)
    data = r.json()
    check("Gateway отвечает", r.status_code == 200)
    check("Auth service: ok",   data.get("services", {}).get("auth")   == "ok")
    check("Upload service: ok", data.get("services", {}).get("upload") == "ok")
    check("Report service: ok", data.get("services", {}).get("report") == "ok")
except Exception as e:
    print(f"  {FAIL} Gateway недоступен: {e}")
    print("\nЗапусти: docker compose up -d")
    sys.exit(1)


# ─────────────────────────────────────────────────────
# 2. РЕГИСТРАЦИЯ
# ─────────────────────────────────────────────────────
section("2. Регистрация")
import time
email = f"test_{int(time.time())}@test.com"  # уникальный email каждый раз

r = requests.post(f"{BASE}/auth/register", json={"email": email, "password": "testpass123"})
check("Статус 201", r.status_code == 201, f"got {r.status_code}: {r.text}")
user_data = r.json() if r.status_code == 201 else {}
check("Возвращает id",    "id" in user_data)
check("Возвращает email", user_data.get("email") == email)
check("НЕ возвращает password", "password" not in user_data)

# Повторная регистрация того же email — должна вернуть 400
r2 = requests.post(f"{BASE}/auth/register", json={"email": email, "password": "other"})
check("Дублирующий email → 400", r2.status_code == 400, f"got {r2.status_code}")


# ─────────────────────────────────────────────────────
# 3. ЛОГИН
# ─────────────────────────────────────────────────────
section("3. Логин")
r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "testpass123"})
check("Статус 200", r.status_code == 200, f"got {r.status_code}: {r.text}")
token_data = r.json() if r.status_code == 200 else {}
check("Возвращает access_token", "access_token" in token_data)
check("token_type = bearer",     token_data.get("token_type") == "bearer")

token = token_data.get("access_token", "")
headers = {"Authorization": f"Bearer {token}"}

# Неверный пароль → 401
r_bad = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "wrongpass"})
check("Неверный пароль → 401", r_bad.status_code == 401, f"got {r_bad.status_code}")

# Без токена → 401
r_noauth = requests.get(f"{BASE}/jobs")
check("Без токена → 401", r_noauth.status_code == 401, f"got {r_noauth.status_code}")


# ─────────────────────────────────────────────────────
# 4. ДЖОБЫ
# ─────────────────────────────────────────────────────
section("4. Список джобов (пустой)")
r = requests.get(f"{BASE}/jobs", headers=headers)
check("Статус 200",        r.status_code == 200, f"got {r.status_code}: {r.text}")
check("Возвращает список", isinstance(r.json(), list))


section("5. Создание джоба")
# Создаём фейковый аудиофайл (просто байты — MinIO примет любое)
fake_audio = io.BytesIO(b"fake audio data for testing " * 100)

r = requests.post(
    f"{BASE}/jobs",
    headers=headers,
    files={"file": ("test.mp3", fake_audio, "audio/mpeg")},
    data={"genre": "lo-fi"},
)
check("Статус 201",           r.status_code == 201, f"got {r.status_code}: {r.text}")
job_data = r.json() if r.status_code == 201 else {}
check("Возвращает id",        "id" in job_data)
check("genre = lo-fi",        job_data.get("genre") == "lo-fi")
check("status = pending",     job_data.get("status") == "pending")
check("user_id совпадает",    "user_id" in job_data)

job_id = job_data.get("id")

# Неверный жанр → 400
r_bad_genre = requests.post(
    f"{BASE}/jobs",
    headers=headers,
    files={"file": ("test.mp3", io.BytesIO(b"data"), "audio/mpeg")},
    data={"genre": "jazz"},
)
check("Неверный жанр → 400", r_bad_genre.status_code == 400, f"got {r_bad_genre.status_code}")


section("6. Получение джоба")
if job_id:
    r = requests.get(f"{BASE}/jobs/{job_id}", headers=headers)
    check("Статус 200",     r.status_code == 200, f"got {r.status_code}")
    check("id совпадает",   r.json().get("id") == job_id)

    # Чужой джоб — недоступен (джоб с id=999999 не существует)
    r_other = requests.get(f"{BASE}/jobs/999999", headers=headers)
    check("Несуществующий джоб → 404", r_other.status_code == 404, f"got {r_other.status_code}")


section("7. Статус джоба (Redis)")
if job_id:
    r = requests.get(f"{BASE}/jobs/{job_id}/status", headers=headers)
    check("Статус 200",        r.status_code == 200, f"got {r.status_code}")
    status_data = r.json()
    check("Есть поле status",  "status"   in status_data)
    check("Есть поле progress","progress" in status_data)
    check("progress >= 0",     status_data.get("progress", -1) >= 0)


# ─────────────────────────────────────────────────────
# 5. РЕПОРТ
# ─────────────────────────────────────────────────────
section("8. Репорт — ещё не готов")
if job_id:
    r = requests.get(f"{BASE}/reports/{job_id}", headers=headers)
    check("404 пока нет репорта", r.status_code == 404, f"got {r.status_code}")

section("9. Создание репорта (симуляция воркера)")
if job_id:
    metrics = {"lufs": -14.2, "bpm": 128, "key": "Am", "score": 87}
    r = requests.post(f"{BASE}/reports/{job_id}", json={"metrics": metrics})
    check("Статус 201",         r.status_code == 201, f"got {r.status_code}: {r.text}")
    check("metrics совпадают",  r.json().get("metrics") == metrics)

section("10. Получение репорта")
if job_id:
    r = requests.get(f"{BASE}/reports/{job_id}", headers=headers)
    check("Статус 200",       r.status_code == 200, f"got {r.status_code}: {r.text}")
    report = r.json()
    check("Есть metrics",     "metrics" in report)
    check("job_id совпадает", report.get("job_id") == job_id)


# ─────────────────────────────────────────────────────
# ИТОГ
# ─────────────────────────────────────────────────────
print(f"\n{'═'*50}")
if not errors:
    print(f"  ✅ ВСЕ ТЕСТЫ ПРОШЛИ")
else:
    print(f"  ❌ ПРОВАЛЕНО: {len(errors)} тест(ов)")
    for e in errors:
        print(f"     • {e}")
print(f"{'═'*50}\n")

sys.exit(0 if not errors else 1)