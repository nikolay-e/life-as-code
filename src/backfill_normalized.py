import sys

from sqlalchemy import text

from database import get_db_session_context
from logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger("backfill_normalized")

BACKFILL_QUERIES = [
    (
        "whoop → hrv",
        """
        INSERT INTO hrv (user_id, date, source, hrv_avg, created_at, updated_at)
        SELECT user_id, date, 'whoop', hrv_rmssd, created_at, NOW()
        FROM whoop_recovery
        WHERE hrv_rmssd IS NOT NULL
        ON CONFLICT (user_id, date, source) DO UPDATE SET
            hrv_avg = EXCLUDED.hrv_avg,
            updated_at = NOW()
        """,
    ),
    (
        "whoop → heart_rate",
        """
        INSERT INTO heart_rate (user_id, date, source, resting_hr, created_at, updated_at)
        SELECT user_id, date, 'whoop', resting_heart_rate, created_at, NOW()
        FROM whoop_recovery
        WHERE resting_heart_rate IS NOT NULL
        ON CONFLICT (user_id, date, source) DO UPDATE SET
            resting_hr = EXCLUDED.resting_hr,
            updated_at = NOW()
        """,
    ),
    (
        "whoop → sleep",
        """
        INSERT INTO sleep (user_id, date, source, total_sleep_minutes, deep_minutes,
                          light_minutes, rem_minutes, awake_minutes, respiratory_rate,
                          sleep_start_time, sleep_end_time,
                          created_at, updated_at)
        SELECT user_id, date, 'whoop', total_sleep_duration_minutes, deep_sleep_minutes,
               light_sleep_minutes, rem_sleep_minutes, awake_minutes, respiratory_rate,
               sleep_start_time, sleep_end_time,
               created_at, NOW()
        FROM whoop_sleep
        WHERE total_sleep_duration_minutes IS NOT NULL
        ON CONFLICT (user_id, date, source) DO UPDATE SET
            total_sleep_minutes = EXCLUDED.total_sleep_minutes,
            deep_minutes = EXCLUDED.deep_minutes,
            light_minutes = EXCLUDED.light_minutes,
            rem_minutes = EXCLUDED.rem_minutes,
            awake_minutes = EXCLUDED.awake_minutes,
            respiratory_rate = EXCLUDED.respiratory_rate,
            sleep_start_time = EXCLUDED.sleep_start_time,
            sleep_end_time = EXCLUDED.sleep_end_time,
            updated_at = NOW()
        """,
    ),
    (
        "eight_sleep → hrv",
        """
        INSERT INTO hrv (user_id, date, source, hrv_avg, created_at, updated_at)
        SELECT user_id, date, 'eight_sleep', hrv, created_at, NOW()
        FROM eight_sleep_sessions
        WHERE hrv IS NOT NULL
        ON CONFLICT (user_id, date, source) DO UPDATE SET
            hrv_avg = EXCLUDED.hrv_avg,
            updated_at = NOW()
        """,
    ),
    (
        "eight_sleep → heart_rate",
        """
        INSERT INTO heart_rate (user_id, date, source, resting_hr, created_at, updated_at)
        SELECT user_id, date, 'eight_sleep', heart_rate::integer, created_at, NOW()
        FROM eight_sleep_sessions
        WHERE heart_rate IS NOT NULL
        ON CONFLICT (user_id, date, source) DO UPDATE SET
            resting_hr = EXCLUDED.resting_hr,
            updated_at = NOW()
        """,
    ),
    (
        "eight_sleep → sleep",
        """
        INSERT INTO sleep (user_id, date, source, total_sleep_minutes, deep_minutes,
                          light_minutes, rem_minutes, respiratory_rate, sleep_score,
                          sleep_start_time, sleep_end_time,
                          created_at, updated_at)
        SELECT user_id, date, 'eight_sleep',
               ROUND(sleep_duration_seconds / 60.0, 1),
               ROUND(deep_duration_seconds / 60.0, 1),
               ROUND(light_duration_seconds / 60.0, 1),
               ROUND(rem_duration_seconds / 60.0, 1),
               respiratory_rate,
               score,
               sleep_start_time, sleep_end_time,
               created_at, NOW()
        FROM eight_sleep_sessions
        WHERE sleep_duration_seconds IS NOT NULL
        ON CONFLICT (user_id, date, source) DO UPDATE SET
            total_sleep_minutes = EXCLUDED.total_sleep_minutes,
            deep_minutes = EXCLUDED.deep_minutes,
            light_minutes = EXCLUDED.light_minutes,
            rem_minutes = EXCLUDED.rem_minutes,
            respiratory_rate = EXCLUDED.respiratory_rate,
            sleep_score = EXCLUDED.sleep_score,
            sleep_start_time = EXCLUDED.sleep_start_time,
            sleep_end_time = EXCLUDED.sleep_end_time,
            updated_at = NOW()
        """,
    ),
]

VERIFICATION_QUERIES = [
    (
        "hrv",
        "SELECT source, count(*), min(date)::text, max(date)::text FROM hrv GROUP BY source ORDER BY source",
    ),
    (
        "heart_rate",
        "SELECT source, count(*), min(date)::text, max(date)::text FROM heart_rate GROUP BY source ORDER BY source",
    ),
    (
        "sleep",
        "SELECT source, count(*), min(date)::text, max(date)::text FROM sleep GROUP BY source ORDER BY source",
    ),
]


def run_backfill():
    with get_db_session_context() as db:
        for label, query in BACKFILL_QUERIES:
            result = db.execute(text(query))
            logger.info("backfill_step", step=label, rows=result.rowcount)
        db.commit()
        logger.info("backfill_committed")

    with get_db_session_context() as db:
        for table, query in VERIFICATION_QUERIES:
            rows = db.execute(text(query)).fetchall()
            for row in rows:
                logger.info(
                    "backfill_verification",
                    table=table,
                    source=row[0],
                    count=row[1],
                    min_date=row[2],
                    max_date=row[3],
                )


if __name__ == "__main__":
    logger.info("backfill_started")
    try:
        run_backfill()
        logger.info("backfill_complete")
    except Exception:
        logger.exception("backfill_failed")
        sys.exit(1)
