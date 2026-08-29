from __future__ import annotations

import pytest

from pring_cycle.catalog import METRIC_CATALOG_VERSION, metric_catalog, metric_definition


def test_v1_catalog_freezes_all_61_metric_groups() -> None:
    catalog = metric_catalog()

    assert METRIC_CATALOG_VERSION == "metric-catalog-v0001"
    assert len(catalog) == 61
    assert len({item.metric_id for item in catalog}) == 61
    assert {item.priority for item in catalog} == {"P0", "P1", "P2"}
    assert metric_definition("CN_COMMODITY_CORE_NHII").source_codes == ("NHII.NH",)
    assert metric_definition("CN_COMMODITY_CORE_NHII").source_candidates == ("NHII.NH",)
    assert metric_definition("CN_COMMODITY_CORE_NHII").priority == "P0"
    assert metric_definition("CN_COMMODITY_CORE_NHII").certification_status == "certified"
    lpr = metric_definition("CN_LPR_1Y_5Y")
    assert lpr.certification_status == "certified"
    assert lpr.unit == "percent"
    assert lpr.frequency == "monthly"
    assert lpr.source_codes == ("CHINAMONEY_LPR",)
    assert lpr.release_event_family == "chinamoney_lpr"
    assert lpr.release_rule == "monthly_day_20_holiday_roll_0900_asia_shanghai"
    assert lpr.release_timezone == "Asia/Shanghai"
    assert all(item.release_rule for item in catalog)
    assert metric_definition("CN_SF_COMPONENTS").dimensions == ("component", "measure")


def test_unknown_or_synonym_metric_ids_are_rejected() -> None:
    with pytest.raises(KeyError, match="unknown_metric_id"):
        metric_definition("CPI")
