from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pring_cycle.evidence import AsOfMode, EvidenceRepository
from pring_cycle.official_context import ingest_official_context_document
from pring_cycle.runtime import RuntimePaths, initialize_runtime


def test_date_only_history_is_available_on_next_shanghai_day(tmp_path: Path) -> None:
    paths = RuntimePaths.discover(tmp_path / "runtime")
    initialize_runtime(paths)
    url = "https://www.stats.gov.cn/sj/zxfb/202608/t20260809_1.html"
    content = """<h1>2026年7月份居民消费价格</h1><p>发布时间：2026-08-09</p>
    <table><tr><th>指标</th><th>环比（%）</th><th>同比（%）</th><th>累计平均同比（%）</th></tr>
    <tr><td>不包括食品和能源</td><td>0.1</td><td>1.0</td><td>1.2</td></tr></table>""".encode()
    imported = ingest_official_context_document(
        paths,
        content,
        family="nbs_core_cpi",
        source_url=url,
        expected_period="2026-07",
        fetched_at=datetime.now(UTC),
        definition_version="metric-catalog-v0001",
    )
    repository = EvidenceRepository(paths.database)
    shanghai = ZoneInfo("Asia/Shanghai")
    for observation_id in imported.observation_ids:
        before = repository.query(
            observation_id,
            mode=AsOfMode.PUBLIC,
            as_of=datetime(2026, 8, 9, 23, 59, 59, tzinfo=shanghai),
        )
        after = repository.trace(
            observation_id, mode=AsOfMode.PUBLIC, as_of=datetime(2026, 8, 10, tzinfo=shanghai)
        )
        assert before.selected_value is None
        assert after.selected_value is not None
        assert after.claims[0].release_at is None
        assert after.claims[0].public_available_at == datetime(2026, 8, 9, 16, tzinfo=UTC)
