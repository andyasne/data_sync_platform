import math, os
from sqlalchemy import create_engine, MetaData, Table, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from app.utils.celery import make_celery
from flask import current_app
from ...utils.sse import announcer
from celery import shared_task

def get_celery():
    return current_app.celery_app

@shared_task(bind=True, name="sync_table_task")
def sync_table_task(self, table_name, modified_col="server_modified_date"):
    # Instead of current_app, import your config here directly
    import os
    from flask import current_app
    from sqlalchemy import create_engine, MetaData, Table, select
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.exc import SQLAlchemyError
    from ...utils.sse import announcer

    src_engine = create_engine(os.environ.get("SOURCE_DB_URI", ""))
    tgt_engine = create_engine(os.environ.get("TARGET_DB_URI", ""))
    src_meta = MetaData(bind=src_engine)
    tgt_meta = MetaData(bind=tgt_engine)
    src_table = Table(table_name, src_meta, autoload_with=src_engine)
    tgt_table = Table(table_name, tgt_meta, autoload_with=tgt_engine)
    pk_col = list(src_table.primary_key.columns)[0]

    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 10000))
    total = src_engine.execute(select(pk_col).select_from(src_table)).rowcount or 0
    chunks = math.ceil(total / CHUNK_SIZE) if total else 0

    last_id = 0
    processed = 0
    while True:
        rows = src_engine.execute(
            select(src_table)
            .where(pk_col > last_id)
            .order_by(pk_col)
            .limit(CHUNK_SIZE)
        ).fetchall()
        if not rows:
            break
        last_id = rows[-1][pk_col]

        values = [dict(r) for r in rows]
        stmt = pg_insert(tgt_table).values(values)
        update_cols = {c.name: getattr(stmt.excluded, c.name)
                       for c in tgt_table.columns if c.name != pk_col.name}
        stmt = stmt.on_conflict_do_update(
            index_elements=[pk_col.name],
            set_=update_cols,
            where=(getattr(stmt.excluded, modified_col) >
                   getattr(tgt_table.c, modified_col))
        )
        try:
            tgt_engine.execute(stmt)
            processed += len(values)
            announcer.announce({
                "table": table_name,
                "processed": processed,
                "total": total
            })
        except SQLAlchemyError as exc:
            self.retry(exc=exc, countdown=30, max_retries=5)
