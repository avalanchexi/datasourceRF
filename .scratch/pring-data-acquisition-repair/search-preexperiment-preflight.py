"""Read-only runtime credential presence and today's budget; never emit secret values."""
from datetime import UTC, datetime, timedelta
import json
import sqlite3
from zoneinfo import ZoneInfo
from pring_cycle.runtime import RuntimePaths
from pring_cycle.secrets import parse_data_source_secrets
from pring_cycle.retrieval_ledger import daily_consumption


def preflight() -> dict[str, object]:
    paths = RuntimePaths.discover()
    keys = parse_data_source_secrets(paths.secrets)
    document = {
        'runtime': paths.as_document(),
        'configured': {name: bool(keys.get(name)) for name in ('TAVILY_API_KEY', 'EXA_API_KEY')},
        'network_requests': 0,
        'production_writes': 0,
        'observed_at': datetime.now(UTC).isoformat(),
    }
    if paths.database.is_file():
        with sqlite3.connect(paths.database.resolve().as_uri() + '?mode=ro', uri=True) as connection:
            connection.row_factory = sqlite3.Row
            document['active_or_queued_runs'] = connection.execute(
                "SELECT COUNT(*) FROM parent_run WHERE status IN ('queued', 'running')"
            ).fetchone()[0]
            try:
                document['today_consumed'] = daily_consumption(connection, datetime.now(UTC))
            except sqlite3.OperationalError as error:
                document['today_consumed'] = None
                document['budget_read_error'] = str(error)
                document['legacy_attempt_columns'] = [r['name'] for r in connection.execute(
                    'PRAGMA table_info(run_retrieval_attempt)')]
                document['request_tables'] = [r['name'] for r in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'retrieval_%'")]
                if 'retrieval_physical_request' not in document['request_tables']:
                    start = datetime.now(ZoneInfo('Asia/Shanghai')).replace(
                        hour=0, minute=0, second=0, microsecond=0)
                    end = start + timedelta(days=1)
                    counts = {'tavily': 0, 'exa': 0, 'ai_websearch': 0}
                    for row in connection.execute(
                        'SELECT channel, outcome, budget_charged, occurred_at FROM run_retrieval_attempt'
                    ):
                        if (row['channel'] in counts
                                and start <= datetime.fromisoformat(row['occurred_at']) < end
                                and (row['budget_charged'] or row['outcome'] in (
                                    'not_found', 'candidate_source', 'verified', 'failed'))):
                            counts[row['channel']] += 1
                    document['today_consumed'] = counts
                    document['budget_basis'] = 'conservative legacy attempt count; no schema changes'
    else:
        document['today_consumed'] = None
    return document


if __name__ == "__main__":
    print(json.dumps(preflight(), indent=2))
