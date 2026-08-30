from __future__ import annotations

import pytest

from pring_cycle.catalog import (
    METRIC_CATALOG_V0001,
    METRIC_CATALOG_VERSION,
    metric_catalog,
    metric_catalog_v0001,
    metric_definition,
)


def test_v2_catalog_freezes_all_61_metric_groups_without_mutating_v1() -> None:
    catalog = metric_catalog()

    assert METRIC_CATALOG_VERSION == "metric-catalog-v0002"
    assert METRIC_CATALOG_V0001 == "metric-catalog-v0001"
    assert len(catalog) == 61
    assert len(metric_catalog_v0001()) == 61
    assert {item.definition_version for item in metric_catalog_v0001()} == {
        "metric-catalog-v0001"
    }
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


def test_multiscalar_metric_groups_freeze_measure_dimensions_and_allowed_units() -> None:
    money = metric_definition("CN_M1_M2")
    social_financing = metric_definition("CN_SF_TOTAL")
    industrial_finance = metric_definition("CN_INDUSTRIAL_FINANCE")
    inventory = metric_definition("CN_FINISHED_GOODS_INVENTORY")
    warrants = metric_definition("CN_FUTURES_WARRANTS")

    assert money.dimensions == ("aggregate", "measure")
    assert money.allowed_units == ("hundred_million_cny", "percent")
    assert social_financing.dimensions == ("measure",)
    assert social_financing.allowed_units == ("hundred_million_cny", "percent")
    assert industrial_finance.dimensions == ("item", "measure")
    assert inventory.dimensions == ("measure",)
    assert warrants.dimensions == ("symbol", "warehouse", "exchange", "measure")
    assert {
        metric_definition(metric_id).frequency
        for metric_id in (
            "CN_M1_M2",
            "CN_LOAN_STRUCTURE",
            "CN_INDUSTRIAL_VA",
            "CN_INDUSTRIAL_FINANCE",
            "CN_FINISHED_GOODS_INVENTORY",
            "CN_INVENTORY_TURNOVER",
            "CN_TOOL_LIQUIDITY_MONTHLY",
            "CN_CREDIT_IMPULSE",
        )
    } == {"monthly"}


def test_contract_and_derived_metric_identities_preserve_required_semantics() -> None:
    comex = metric_definition("COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT")

    central_parity = metric_definition("CN_USDCNY_CENTRAL_PARITY")

    assert comex.dimensions == ("contract_month", "measure", "roll_chain_version")
    assert comex.unit == "usd_per_troy_ounce"
    assert central_parity.dimensions == ("currency_pair", "quote_direction")
    assert central_parity.unit == "cny_per_usd"
    assert central_parity.release_event_family == "pbc_usdcny_central_parity"
    assert metric_definition("CN_OMO_7D_RATE").release_event_family == "pbc_omo_notice"
    assert metric_definition("CN_CORE_CPI").release_event_family == "nbs_core_cpi"
    assert (
        metric_definition("CN_INDUSTRIAL_FINANCE").release_event_family
        == "nbs_industrial_finance"
    )
    assert (
        metric_definition("CN_SF_COMPONENTS").release_event_family
        == "pbc_social_financing"
    )
    assert metric_definition("CN_CREDIT_IMPULSE").unit == "percentage_points"
    assert metric_definition("CN_ORDER_INVENTORY_SPREAD").unit == (
        "diffusion_index_points"
    )
    assert metric_definition("CN_PRODUCTION_ORDER_SPREAD").unit == (
        "diffusion_index_points"
    )
    assert metric_definition("EIA_BRENT_RBRTE").unit == "usd_per_barrel"
    assert "barrel" in metric_definition("CN_FUTURES_WARRANTS").allowed_units


def test_unknown_or_synonym_metric_ids_are_rejected() -> None:
    with pytest.raises(KeyError, match="unknown_metric_id"):
        metric_definition("CPI")
