"""Create all tables in NeonDB."""
import asyncio
import asyncpg
from config import DATABASE_URL

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(150),
    role          VARCHAR(20) NOT NULL CHECK (role IN ('data_analyst','observer','engineer','supervisor')),
    telegram_chat_id BIGINT,
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stations (
    id       SERIAL PRIMARY KEY,
    code     VARCHAR(20) UNIQUE NOT NULL,
    name     VARCHAR(150) NOT NULL,
    lat      DOUBLE PRECISION NOT NULL,
    lon      DOUBLE PRECISION NOT NULL,
    region   VARCHAR(100),
    status   VARCHAR(20) DEFAULT 'normal' CHECK (status IN ('normal','warning','critical','offline')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS readings (
    id          SERIAL PRIMARY KEY,
    station_id  INTEGER REFERENCES stations(id),
    observed_at TIMESTAMPTZ NOT NULL,
    sst         REAL,
    temp_air    REAL,
    wave_height REAL,
    wave_period REAL,
    wind_speed  REAL,
    wind_dir    SMALLINT,
    pressure    REAL,
    visibility  REAL,
    humidity    REAL,
    status      VARCHAR(20) DEFAULT 'normal'
);
CREATE INDEX IF NOT EXISTS idx_readings_st_time ON readings(station_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS gfs_forecasts (
    id               SERIAL PRIMARY KEY,
    station_id       INTEGER REFERENCES stations(id),
    issued_at        TIMESTAMPTZ NOT NULL,
    forecast_hour    SMALLINT NOT NULL,
    sst_gfs          REAL,
    sst_corrected    REAL,
    wind_speed_gfs   REAL,
    wind_speed_corr  REAL,
    wave_height_gfs  REAL,
    wave_height_corr REAL,
    correction_meta  JSONB
);
CREATE INDEX IF NOT EXISTS idx_gfs_station ON gfs_forecasts(station_id, issued_at DESC);

CREATE TABLE IF NOT EXISTS personnel (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id),
    station_id INTEGER REFERENCES stations(id),
    position   VARCHAR(100),
    phone      VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS assignments (
    id           SERIAL PRIMARY KEY,
    personnel_id INTEGER REFERENCES personnel(id),
    station_id   INTEGER REFERENCES stations(id),
    shift_start  TIMESTAMPTZ NOT NULL,
    shift_end    TIMESTAMPTZ NOT NULL,
    role_on_duty VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS requests (
    id          SERIAL PRIMARY KEY,
    station_id  INTEGER REFERENCES stations(id),
    created_by  INTEGER REFERENCES users(id),
    assigned_to INTEGER REFERENCES users(id),
    title       VARCHAR(255) NOT NULL,
    description TEXT,
    req_type    VARCHAR(30) CHECK (req_type IN ('supply','maintenance','leave','equipment')),
    status      VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending','in_progress','signed','rejected','completed')),
    priority    VARCHAR(10) DEFAULT 'normal',
    created_at  TIMESTAMPTZ DEFAULT now(),
    signed_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS equipment_checks (
    id         SERIAL PRIMARY KEY,
    station_id INTEGER REFERENCES stations(id),
    checked_by INTEGER REFERENCES users(id),
    equipment  VARCHAR(150) NOT NULL,
    result     VARCHAR(20) CHECK (result IN ('pass','warning','fail')),
    notes      TEXT,
    checked_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS calendar_events (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    description TEXT,
    event_type  VARCHAR(30) CHECK (event_type IN ('equipment_check','shift_change','maintenance','meeting','inspection','other')),
    station_id  INTEGER REFERENCES stations(id),
    created_by  INTEGER REFERENCES users(id),
    starts_at   TIMESTAMPTZ NOT NULL,
    ends_at     TIMESTAMPTZ NOT NULL,
    all_day     BOOLEAN DEFAULT false,
    color       VARCHAR(7)
);

CREATE TABLE IF NOT EXISTS agent_activity (
    id          SERIAL PRIMARY KEY,
    agent_name  VARCHAR(100) NOT NULL,
    event_type  VARCHAR(30) NOT NULL,
    severity    VARCHAR(10) DEFAULT 'info' CHECK (severity IN ('info','warning','critical')),
    title       VARCHAR(255) NOT NULL,
    body        TEXT,
    metadata    JSONB,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_time ON agent_activity(created_at DESC);

CREATE TABLE IF NOT EXISTS notifications (
    id       SERIAL PRIMARY KEY,
    user_id  INTEGER REFERENCES users(id),
    channel  VARCHAR(20) CHECK (channel IN ('telegram','web')),
    message  TEXT NOT NULL,
    sent_at  TIMESTAMPTZ DEFAULT now(),
    delivered BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    priority VARCHAR(5) DEFAULT 'P2' CHECK (priority IN ('P1','P2','P3')),
    estimated_minutes INT,
    due_date TIMESTAMPTZ,
    station_id INT REFERENCES stations(id),
    assigned_to INT REFERENCES users(id),
    completed BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS focus_blocks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    color VARCHAR(7) DEFAULT '#3b82f6',
    user_id INT REFERENCES users(id),
    day_of_week SMALLINT,
    recurring BOOLEAN DEFAULT false
);
"""

async def main():
    print("Connecting to NeonDB...")
    conn = await asyncpg.connect(DATABASE_URL)
    print("Creating tables...")
    await conn.execute(SCHEMA)
    print("All tables created successfully!")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
