-- =============================================================
-- Инициализация схемы базы данных
-- Запускается автоматически при первом старте контейнера postgres
-- =============================================================

-- ──────────────────────────────────────────────────────────────
-- USER — учётные записи пользователей
-- Добавлено поле password (хранится bcrypt-хеш)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS "user" (
    id       SERIAL PRIMARY KEY,
    email    VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL   -- bcrypt hash
);

-- ──────────────────────────────────────────────────────────────
-- JOB — задание на анализ аудио
-- user_id — FK на user, genre — жанр для сравнения
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS job (
    id      SERIAL PRIMARY KEY,
    user_id INTEGER      NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    genre   VARCHAR(50)  NOT NULL,
    status  VARCHAR(20)  NOT NULL DEFAULT 'pending'
);

-- ──────────────────────────────────────────────────────────────
-- REPORT — результат анализа джоба
-- job_id — FK (PK) → один джоб = один репорт
-- metrics — JSON с результатами DSP-анализа
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS report (
    job_id  INTEGER PRIMARY KEY REFERENCES job(id) ON DELETE CASCADE,
    id      SERIAL  NOT NULL,
    metrics JSON    NOT NULL DEFAULT '{}'
);

-- ──────────────────────────────────────────────────────────────
-- JOB_STATUS_CACHE — Redis-зеркало статуса (в БД для истории)
-- Актуальные данные хранятся в Redis, сюда пишется итог
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS job_status_cache (
    cache_key VARCHAR(100) PRIMARY KEY,
    status    VARCHAR(20)  NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- JOB_PROGRESS_CACHE — прогресс обработки (0–100)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS job_progress_cache (
    cache_key VARCHAR(100) PRIMARY KEY,
    progress  INTEGER NOT NULL DEFAULT 0
);
