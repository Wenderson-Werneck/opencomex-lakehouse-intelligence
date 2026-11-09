import sqlite3
import pandas as pd
from typing import List, Dict, Any
from src.models import TradeRecord, VesselLineup


class ComexLakehouseEngine:
    """
    Implements a three-tier Medallion architecture (Bronze -> Silver -> Gold)
    for international trade and supply chain analytics.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self._init_schemas()

    def _init_schemas(self) -> None:
        cursor = self.conn.cursor()
        # Bronze: Raw ingestion audit table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bronze_raw_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_feed TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Silver: Cleansed, strongly-typed relational trade table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS silver_trade_records (
                transaction_id TEXT PRIMARY KEY,
                flow_direction TEXT NOT NULL,
                reporter_country TEXT NOT NULL,
                partner_country TEXT NOT NULL,
                hs6_code TEXT NOT NULL,
                hs6_description TEXT,
                net_weight_kg REAL NOT NULL,
                fob_usd REAL NOT NULL,
                unit_price_usd_per_kg REAL GENERATED ALWAYS AS (fob_usd / net_weight_kg) VIRTUAL,
                port_unlocode TEXT NOT NULL,
                period_year_month TEXT NOT NULL
            )
        """)

        # Silver: Vessel Port Lineups
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS silver_vessel_lineups (
                imo_number TEXT,
                port_unlocode TEXT,
                vessel_name TEXT,
                cargo_type TEXT,
                deadweight_tonnage REAL,
                status TEXT,
                eta_timestamp TEXT,
                PRIMARY KEY (imo_number, port_unlocode, eta_timestamp)
            )
        """)
        self.conn.commit()

    def ingest_trade_bronze_to_silver(self, records: List[TradeRecord]) -> int:
        """
        Validates records, appends to bronze raw audit, and merges into silver.
        """
        cursor = self.conn.cursor()
        inserted_count = 0

        for r in records:
            # Bronze audit log
            cursor.execute(
                "INSERT INTO bronze_raw_events (source_feed, payload_json) VALUES (?, ?)",
                ("COMEX_STAT_API", r.model_dump_json())
            )
            # Silver merge/upsert
            cursor.execute("""
                INSERT INTO silver_trade_records (
                    transaction_id, flow_direction, reporter_country, partner_country,
                    hs6_code, hs6_description, net_weight_kg, fob_usd, port_unlocode, period_year_month
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(transaction_id) DO UPDATE SET
                    fob_usd = excluded.fob_usd,
                    net_weight_kg = excluded.net_weight_kg
            """, (
                r.transaction_id, r.flow_direction, r.reporter_country, r.partner_country,
                r.hs6_code, r.hs6_description, r.net_weight_kg, r.fob_usd, r.port_unlocode, r.period_year_month
            ))
            inserted_count += 1

        self.conn.commit()
        return inserted_count

    def build_gold_trade_balance(self) -> pd.DataFrame:
        """
        Aggregates bilateral trade balances: Export FOB - Import FOB.
        """
        query = """
            SELECT 
                reporter_country,
                partner_country,
                period_year_month,
                SUM(CASE WHEN flow_direction = 'EXPORT' THEN fob_usd ELSE 0 END) AS total_export_usd,
                SUM(CASE WHEN flow_direction = 'IMPORT' THEN fob_usd ELSE 0 END) AS total_import_usd,
                SUM(CASE WHEN flow_direction = 'EXPORT' THEN fob_usd ELSE -fob_usd END) AS trade_balance_usd,
                SUM(net_weight_kg) / 1000.0 AS total_metric_tons
            FROM silver_trade_records
            GROUP BY reporter_country, partner_country, period_year_month
            ORDER BY total_export_usd DESC
        """
        return pd.read_sql_query(query, self.conn)

    def build_gold_commodity_benchmarks(self) -> pd.DataFrame:
        """
        Computes weighted average unit price (USD/kg) and volume distribution by HS-6 code.
        """
        query = """
            SELECT 
                hs6_code,
                hs6_description,
                flow_direction,
                COUNT(*) as transaction_count,
                SUM(net_weight_kg) as total_volume_kg,
                SUM(fob_usd) as total_fob_usd,
                ROUND(SUM(fob_usd) / SUM(net_weight_kg), 4) as weighted_usd_per_kg
            FROM silver_trade_records
            GROUP BY hs6_code, hs6_description, flow_direction
            ORDER BY total_fob_usd DESC
        """
        return pd.read_sql_query(query, self.conn)

    def close(self) -> None:
        self.conn.close()
