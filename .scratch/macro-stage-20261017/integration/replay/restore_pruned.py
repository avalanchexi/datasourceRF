"""Put back on the replay copy the originals retention pruned after the 10-14 run.

Usage: python3 restore_pruned.py <copy database> <backup taken before the 10-14 run>

The copy is at the 10-19 run's retention window (from 2026-04-21); the 10-14, 10-15 and
10-16 windows start one to three sessions earlier. Every source claim the backup holds and
the copy does not (2026-04-14 to 04-20: 32,702 claims), with its acquisition links and
release events, is inserted as it was. Run once on the copy, never on the real database.
"""
import sqlite3
import sys

copy, backup = sys.argv[1], sys.argv[2]
c = sqlite3.connect(copy, isolation_level=None)
c.execute(f"attach 'file:{backup}?mode=ro&immutable=1' as o")


def restore(table: str, where: str) -> None:
    cols = ",".join(r[1] for r in c.execute(f"pragma main.table_info({table})"))
    n = c.execute(f"insert or ignore into main.{table}({cols}) select {cols} from o.{table} {where}").rowcount
    print(table, n)


c.execute("begin")
c.execute(
    "create temp table restored as select claim_id from o.source_claim "
    "where claim_id not in (select claim_id from main.source_claim)"
)
restore(
    "release_event",
    "where release_event_id in (select release_event_id from o.source_claim where claim_id in "
    "(select claim_id from temp.restored)) and release_event_id not in "
    "(select release_event_id from main.release_event)",
)
restore(
    "acquisition_request",
    "where acquisition_id in (select acquisition_id from o.source_claim_acquisition where "
    "claim_id in (select claim_id from temp.restored)) and acquisition_id not in "
    "(select acquisition_id from main.acquisition_request)",
)
restore("source_claim", "where claim_id in (select claim_id from temp.restored)")
restore("source_claim_acquisition", "where claim_id in (select claim_id from temp.restored)")
restore("claim_matched_quote", "where claim_id in (select claim_id from temp.restored)")
restore("derived_observation", "where 1")
c.execute("commit")
