-- garmin-analytics schema
-- All dates are ISO-8601 YYYY-MM-DD strings.
-- Nulls are expected — many metrics are device/condition dependent.

CREATE TABLE IF NOT EXISTS activities (
    activity_id                 INTEGER PRIMARY KEY,
    date                        TEXT NOT NULL,
    activity_type               TEXT,
    activity_name               TEXT,
    distance_km                 REAL,
    duration_min                REAL,
    pace_min_km                 REAL,
    avg_hr                      INTEGER,
    max_hr                      INTEGER,
    hr_z1_pct                   REAL,
    hr_z2_pct                   REAL,
    hr_z3_pct                   REAL,
    hr_z4_pct                   REAL,
    hr_z5_pct                   REAL,
    avg_cadence                 INTEGER,
    max_cadence                 INTEGER,
    vo2max                      REAL,
    aerobic_te                  REAL,
    anaerobic_te                REAL,
    avg_power                   INTEGER,
    max_power                   INTEGER,
    avg_speed_kmh               REAL,
    max_speed_kmh               REAL,
    stride_length_cm            REAL,
    ground_contact_ms           INTEGER,
    vertical_oscillation_cm     REAL,
    elevation_gain_m            REAL,
    calories                    INTEGER,
    training_load               REAL
);

CREATE TABLE IF NOT EXISTS activity_laps (
    activity_id                 INTEGER NOT NULL,
    lap_index                   INTEGER NOT NULL,
    distance_km                 REAL,
    duration_min                REAL,
    pace_min_km                 REAL,
    avg_hr                      INTEGER,
    avg_cadence                 INTEGER,
    elevation_gain_m            REAL,
    PRIMARY KEY (activity_id, lap_index)
);

CREATE TABLE IF NOT EXISTS daily_summary (
    date                        TEXT PRIMARY KEY,
    steps                       INTEGER,
    calories_total              INTEGER,
    calories_active             INTEGER,
    resting_hr                  INTEGER,
    stress_avg                  INTEGER,
    body_battery_min            INTEGER,
    body_battery_max            INTEGER,
    intensity_minutes_moderate  INTEGER,
    intensity_minutes_vigorous  INTEGER,
    floors_ascended             REAL,
    respiration_avg             REAL,
    spo2_avg                    REAL
);

CREATE TABLE IF NOT EXISTS sleep (
    date                        TEXT PRIMARY KEY,
    total_min                   INTEGER,
    deep_min                    INTEGER,
    light_min                   INTEGER,
    rem_min                     INTEGER,
    awake_min                   INTEGER,
    sleep_score                 INTEGER,
    avg_overnight_hr            REAL,
    avg_hrv                     REAL
);

CREATE TABLE IF NOT EXISTS hrv (
    date                        TEXT PRIMARY KEY,
    last_night_avg              REAL,
    weekly_avg                  REAL,
    status                      TEXT
);

CREATE TABLE IF NOT EXISTS training (
    date                            TEXT PRIMARY KEY,
    vo2max                          REAL,
    training_status                 TEXT,
    acute_load                      REAL,
    chronic_load                    REAL,
    training_readiness_score        INTEGER,
    training_readiness_description  TEXT
);

CREATE TABLE IF NOT EXISTS personal_records (
    record_id                   INTEGER PRIMARY KEY,
    type_id                     INTEGER,
    type_key                    TEXT,
    activity_id                 INTEGER,
    value                       REAL,
    date                        TEXT
);

CREATE TABLE IF NOT EXISTS sync_log (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at_utc                  TEXT NOT NULL,
    range_start                 TEXT,
    range_end                   TEXT,
    rows_activities             INTEGER,
    rows_laps                   INTEGER,
    rows_daily                  INTEGER,
    rows_sleep                  INTEGER,
    rows_hrv                    INTEGER,
    rows_training               INTEGER,
    source                      TEXT DEFAULT 'garminconnect'
);
