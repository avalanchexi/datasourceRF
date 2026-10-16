"""The identity a page shows for its projection, without importing the dashboard toolkit.

The topbar and the shell served before the interactive dashboard loads both name the
same seven fields, so a reader never sees one set of labels give way to another.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from pring_cycle.projections import ProjectionSet
from pring_cycle.run_health import ProducerRun

_COMPLETENESS = {"complete": "完整", "degraded": "降级"}


def local_time(value: datetime) -> str:
    return value.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S 北京时间")


def identity_fields(
    projection: ProjectionSet | None,
    *,
    producer: ProducerRun | None,
    rendered_at: datetime,
) -> list[tuple[str, str]]:
    """The seven identity fields of the page; all belong to ``projection``, never the pointer."""
    run = producer.run_id if producer else "未提供"
    generated = local_time(rendered_at)
    if projection is None:
        return [
            ("目标交易日", "尚无"),
            ("模型版本", "尚无"),
            ("投影", "等待首次完整运行"),
            ("完整度", "尚无"),
            ("分析截止", "尚无"),
            ("运行", run),
            ("页面生成", generated),
        ]
    envelope = projection.envelope
    return [
        ("目标交易日", envelope.target_business_date),
        ("模型版本", envelope.model_version_id),
        ("投影", envelope.projection_set_id),
        ("完整度", _COMPLETENESS.get(envelope.completeness, envelope.completeness)),
        ("分析截止", local_time(envelope.system_as_of)),
        ("运行", run),
        ("页面生成", generated),
    ]
