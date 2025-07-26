import logging, os
from celery import shared_task
from sqlalchemy import (
    create_engine, MetaData, Table, select, func,
    inspect, delete
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from ...utils.sse import announce  # ← only import THIS


# ──────────────────────────────────────────────────────────────────────────────
# Helper: push every log‑line as an SSE message
# ──────────────────────────────────────────────────────────────────────────────
class SSELogHandler(logging.Handler):
    """Logging handler that streams every record as a Server‑Sent Event."""

    def __init__(self, table_name: str):
        super().__init__()
        self.table_name = table_name
        self.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )

    def emit(self, record):
        try:
            announce(
                {
                    "kind": "log",  # <── tag as log frame
                    "table": self.table_name,
                    "level": record.levelname.lower(),
                    "message": self.format(record),
                }
            )
        except Exception:
            # never let logging failure crash the task
            self.handleError(record)


# ──────────────────────────────────────────────────────────────────────────────
# The Celery task
# ──────────────────────────────────────────────────────────────────────────────
@shared_task(bind=True, name="sync_table_task")
def sync_table_task(
    self,
    table_name: str,
    modified_col: str = "server_modified_date",
) -> None:
    """Synchronise a source → target table, streaming progress + logs via SSE."""

    logger = logging.getLogger(f"sync.{table_name}.{self.request.id}")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(SSELogHandler(table_name))
    logger.propagate = False
    # initial heartbeat — lets the UI show the task immediately
    logger.info("Starting sync: table=%r  modified_col=%r", table_name, modified_col)
    announce({"kind": "progress", "table": table_name, "processed": 0, "total": 0})

    # ── 1) Engines ───────────────────────────────────────────────────────────
    src_engine = create_engine(os.environ["SOURCE_DB_URI"])
    tgt_engine = create_engine(os.environ["TARGET_DB_URI"])
    logger.debug("DSNs → src=%s  tgt=%s", src_engine.url, tgt_engine.url)

    # ── 2) Reflect source ────────────────────────────────────────────────────
    src_meta = MetaData()
    src_table = Table(table_name, src_meta, autoload_with=src_engine)
    logger.info("Source columns: %s", [c.name for c in src_table.columns])

    # ── 3) Ensure target exists ──────────────────────────────────────────────
    tgt_meta = MetaData()
    if not inspect(tgt_engine).has_table(table_name):
        logger.info("Creating target table %r…", table_name)
        tgt_table = Table(table_name, tgt_meta)
        for col in src_table.columns:
            tgt_table.append_column(col.copy())
        tgt_meta.create_all(tgt_engine)
        logger.info("Table %r created.", table_name)

    tgt_table = Table(table_name, tgt_meta, autoload_with=tgt_engine)
    logger.info("Target table %r exists; proceeding to sync.", table_name)

    # ── 4) PK detection ──────────────────────────────────────────────────────
    pk_cols = list(src_table.primary_key.columns)
    if not pk_cols:
        logger.warning("No PK on %r; doing full reload.", table_name)

        # ➊ Truncate target
        with tgt_engine.begin() as tgt_conn:
            deleted = tgt_conn.execute(delete(tgt_table)).rowcount
        logger.info("Cleared %d rows from %r", deleted, table_name)
        announce({"kind": "progress", "table": table_name, "processed": 0, "total": 0})

        # ➋ Pull all rows from source
        with src_engine.connect() as src_conn:
            total = src_conn.execute(select(func.count()).select_from(src_table)).scalar() or 0
            announce({"kind": "progress", "table": table_name, "processed": 0, "total": total})

            rows = src_conn.execute(select(src_table)).mappings().all()
        logger.info("Fetched %d rows from %r", len(rows), table_name)

        # ➌ Bulk‑insert
        if rows:
            with tgt_engine.begin() as tgt_conn:
                tgt_conn.execute(pg_insert(tgt_table), rows)
            logger.info("Reloaded %d rows into %r", len(rows), table_name)
            announce({
                "kind": "progress",
                "table": table_name,
                "processed": len(rows),
                "total": total,
            })
        else:
            logger.info("No rows found in source %r; nothing to load.", table_name)
        return

    # ── 5) Chunked upsert (PK present) ───────────────────────────────────────
    with src_engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(src_table)).scalar() or 0
    announce({"kind": "progress", "table": table_name, "processed": 0, "total": total})

    pk_col = pk_cols[0]
    chunk_sz = int(os.getenv("CHUNK_SIZE", 10_000))
    processed = 0
    last_id = 0
    has_mod = modified_col in src_table.c

    while True:
        with src_engine.connect() as conn:
            chunk = (
                conn.execute(
                    select(src_table)
                    .where(pk_col > last_id)
                    .order_by(pk_col)
                    .limit(chunk_sz)
                )
                .mappings()
                .all()
            )

        if not chunk:
            break

        last_id = chunk[-1][pk_col.name]
        stmt = pg_insert(tgt_table).values(chunk)
        update_cols = {
            c.name: getattr(stmt.excluded, c.name)
            for c in tgt_table.columns
            if c.name != pk_col.name
        }

        if has_mod:
            stmt = stmt.on_conflict_do_update(
                index_elements=[pk_col.name],
                set_=update_cols,
                where=(getattr(stmt.excluded, modified_col) > getattr(tgt_table.c, modified_col)),
            )
        else:
            stmt = stmt.on_conflict_do_update(
                index_elements=[pk_col.name],
                set_=update_cols,
            )

        try:
            with tgt_engine.begin() as conn:
                conn.execute(stmt)
            processed += len(chunk)
            announce({
                "kind": "progress",
                "table": table_name,
                "processed": processed,
                "total": total,
            })
            logger.debug("Upserted %d rows; last_id=%r", len(chunk), last_id)

        except SQLAlchemyError as exc:
            logger.exception("Upsert error; will retry")
            announce({
                "kind": "log",
                "table": table_name,
                "level": "error",
                "message": str(exc),
            })
            raise self.retry(exc=exc, countdown=30, max_retries=5)

    logger.info("Finished sync %r: %d/%d rows", table_name, processed, total)
    announce({"kind": "progress", "table": table_name, "processed": total, "total": total})
