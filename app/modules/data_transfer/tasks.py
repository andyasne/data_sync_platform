import logging
import os

from celery import shared_task
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    select,
    func,
    inspect,
    delete,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError

from ...utils.sse import announcer

logger = logging.getLogger(__name__)

@shared_task(bind=True, name="sync_table")
def sync_table_task(self, table_name: str, modified_col: str = "server_modified_date") -> None:
    logger.info("Starting sync: table=%r  modified_col=%r", table_name, modified_col)

    # ──── 1) Engines ──────────────────────────────────────────────────────────
    src_engine = create_engine(os.environ["SOURCE_DB_URI"])
    tgt_engine = create_engine(os.environ["TARGET_DB_URI"])
    logger.debug("DSNs → src=%s  tgt=%s", src_engine.url, tgt_engine.url)

    # ──── 2) Reflect source ───────────────────────────────────────────────────
    src_meta = MetaData()
    src_table = Table(table_name, src_meta, autoload_with=src_engine)
    logger.info("Source columns: %s", [c.name for c in src_table.columns])

    # ──── 3) Ensure target exists ─────────────────────────────────────────────
    tgt_meta = MetaData()
    inspector = inspect(tgt_engine)
    if not inspector.has_table(table_name):
        logger.info("Creating target table %r…", table_name)
        tgt_table = Table(table_name, tgt_meta)
        for col in src_table.columns:
            tgt_table.append_column(col.copy())
        tgt_meta.create_all(tgt_engine)
        logger.info("Table %r created; skipping sync this run.", table_name)
        return

    tgt_table = Table(table_name, tgt_meta, autoload_with=tgt_engine)
    logger.info("Target table %r exists; proceeding to sync.", table_name)

    # ──── 4) PK detection ──────────────────────────────────────────────────────
    pk_cols = list(src_table.primary_key.columns)
    if not pk_cols:
        # full truncate + reload
        logger.warning("No PK on %r; doing full reload.", table_name)
        with tgt_engine.begin() as conn:
            deleted = conn.execute(delete(tgt_table)).rowcount
            logger.info("Cleared %d rows from %r", deleted, table_name)
            rows = conn.execute(select(src_table)).mappings().all()
            if rows:
                conn.execute(pg_insert(tgt_table), rows)
                logger.info("Reloaded %d rows into %r", len(rows), table_name)
            else:
                logger.info("No rows found in source %r; nothing to load.", table_name)
        return

    pk_col = pk_cols[0]

    # ──── 5) Count & chunked upsert ────────────────────────────────────────────
    with src_engine.connect() as conn:
        total_rows = conn.execute(select(func.count()).select_from(src_table)).scalar() or 0

    chunk_size = int(os.getenv("CHUNK_SIZE", 10_000))
    logger.info("Total rows=%d; chunk_size=%d", total_rows, chunk_size)

    last_id = 0
    processed = 0
    has_mod   = modified_col in src_table.c

    while True:
        with src_engine.connect() as conn:
            chunk = (
                conn.execute(
                    select(src_table)
                    .where(pk_col > last_id)
                    .order_by(pk_col)
                    .limit(chunk_size)
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
                where=(
                    getattr(stmt.excluded, modified_col)
                    > getattr(tgt_table.c, modified_col)
                ),
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
            announcer.announce(
                {"table": table_name, "processed": processed, "total": total_rows}
            )
            logger.debug("Upserted %d rows; last_id=%r", len(chunk), last_id)
        except SQLAlchemyError as exc:
            logger.exception("Upsert error; will retry")
            raise self.retry(exc=exc, countdown=30, max_retries=5)

    logger.info("Finished sync %r: %d/%d rows processed", table_name, processed, total_rows)
