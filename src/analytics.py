from typing import List
from src.models import VesselLineup
import pandas as pd


class MaritimeCongestionAnalyzer:
    """
    Computes port congestion indices, average anchorage wait times,
    and berth occupancy rates from vessel lineups.
    """

    @staticmethod
    def calculate_port_congestion_index(lineups: List[VesselLineup]) -> pd.DataFrame:
        if not lineups:
            return pd.DataFrame()

        data = [l.model_dump() for l in lineups]
        df = pd.DataFrame(data)

        agg = df.groupby("port_unlocode").agg(
            total_vessels=("imo_number", "count"),
            waiting_at_anchorage=("status", lambda s: (s == "WAITING_ANCHORAGE").sum()),
            berthed_or_operating=("status", lambda s: s.isin(["BERTHED", "OPERATING"]).sum()),
            total_dwt=("deadweight_tonnage", "sum"),
        ).reset_index()

        # Congestion Index = (Waiting Vessels / Total Vessels) * 100
        agg["congestion_rate_pct"] = (
            (agg["waiting_at_anchorage"] / agg["total_vessels"]) * 100.0
        ).round(2)

        return agg.sort_values(by="congestion_rate_pct", ascending=False)
