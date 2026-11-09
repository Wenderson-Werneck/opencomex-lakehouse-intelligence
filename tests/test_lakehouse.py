import pytest
from src.models import TradeRecord, VesselLineup
from src.lakehouse import ComexLakehouseEngine
from src.analytics import MaritimeCongestionAnalyzer


def test_medallion_ingestion_and_gold_trade_balance():
    engine = ComexLakehouseEngine()

    sample_trades = [
        TradeRecord(
            transaction_id="TX_202611_001",
            flow_direction="EXPORT",
            reporter_country="BRA",
            partner_country="EST",
            hs6_code="720211",
            hs6_description="Ferro-manganese containing by weight > 2% carbon",
            net_weight_kg=500_000,
            fob_usd=650_000.0,
            port_unlocode="BRSSZ",
            period_year_month="2026-11",
        ),
        TradeRecord(
            transaction_id="TX_202611_002",
            flow_direction="IMPORT",
            reporter_country="BRA",
            partner_country="EST",
            hs6_code="847130",
            hs6_description="Data processing machines",
            net_weight_kg=10_000,
            fob_usd=150_000.0,
            port_unlocode="BRSSZ",
            period_year_month="2026-11",
        ),
    ]

    inserted = engine.ingest_trade_bronze_to_silver(sample_trades)
    assert inserted == 2

    # Check Gold Trade Balance
    df_balance = engine.build_gold_trade_balance()
    assert len(df_balance) == 1
    row = df_balance.iloc[0]
    assert row["reporter_country"] == "BRA"
    assert row["partner_country"] == "EST"
    assert row["total_export_usd"] == 650_000.0
    assert row["total_import_usd"] == 150_000.0
    assert row["trade_balance_usd"] == 500_000.0

    # Check Gold Commodity Benchmark
    df_bench = engine.build_gold_commodity_benchmarks()
    assert len(df_bench) == 2
    ferro_row = df_bench[df_bench["hs6_code"] == "720211"].iloc[0]
    assert ferro_row["weighted_usd_per_kg"] == 1.30  # 650,000 / 500,000

    engine.close()


def test_maritime_congestion_analyzer():
    lineups = [
        VesselLineup(
            vessel_name="Nordic Pioneer",
            imo_number="9876543",
            port_unlocode="BRSSZ",
            eta_timestamp="2026-11-09T08:00:00Z",
            cargo_type="CONTAINER",
            deadweight_tonnage=65000,
            status="WAITING_ANCHORAGE",
        ),
        VesselLineup(
            vessel_name="Baltic Trader",
            imo_number="9123456",
            port_unlocode="BRSSZ",
            eta_timestamp="2026-11-09T09:00:00Z",
            cargo_type="BULK_MINERAL",
            deadweight_tonnage=85000,
            status="BERTHED",
        ),
        VesselLineup(
            vessel_name="Tallinn Star",
            imo_number="9555432",
            port_unlocode="EELLK",
            eta_timestamp="2026-11-09T10:00:00Z",
            cargo_type="CONTAINER",
            deadweight_tonnage=45000,
            status="OPERATING",
        ),
    ]

    df_congestion = MaritimeCongestionAnalyzer.calculate_port_congestion_index(lineups)
    assert len(df_congestion) == 2

    # Port of Santos (BRSSZ) has 2 vessels: 1 waiting, 1 berthed -> 50% congestion
    santos_row = df_congestion[df_congestion["port_unlocode"] == "BRSSZ"].iloc[0]
    assert santos_row["total_vessels"] == 2
    assert santos_row["waiting_at_anchorage"] == 1
    assert santos_row["congestion_rate_pct"] == 50.0

    # Port of Muuga/Tallinn (EELLK) has 1 vessel operating -> 0% congestion
    tallinn_row = df_congestion[df_congestion["port_unlocode"] == "EELLK"].iloc[0]
    assert tallinn_row["congestion_rate_pct"] == 0.0
