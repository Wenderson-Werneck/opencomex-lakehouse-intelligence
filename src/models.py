from typing import Literal, Optional
from pydantic import BaseModel, Field


class TradeRecord(BaseModel):
    transaction_id: str
    flow_direction: Literal["IMPORT", "EXPORT"]
    reporter_country: str = Field(..., description="ISO 3-letter code (e.g. BRA, USA, EST)")
    partner_country: str = Field(..., description="ISO 3-letter code (e.g. CHN, DEU, EST)")
    hs6_code: str = Field(..., description="6-digit Harmonized System commodity code")
    hs6_description: str
    net_weight_kg: float = Field(..., gt=0)
    fob_usd: float = Field(..., gt=0)
    port_unlocode: str = Field(..., description="UN/LOCODE of port of exit/entry (e.g. BRSSZ, EELLK)")
    period_year_month: str = Field(..., pattern=r"^\d{4}-\d{2}$")


class VesselLineup(BaseModel):
    vessel_name: str
    imo_number: str
    port_unlocode: str
    berth: Optional[str] = None
    eta_timestamp: str
    etd_timestamp: Optional[str] = None
    cargo_type: Literal["CONTAINER", "BULK_MINERAL", "BULK_AGRI", "GENERAL_CARGO"]
    deadweight_tonnage: float
    status: Literal["WAITING_ANCHORAGE", "BERTHED", "OPERATING", "DEPARTED"]


class ContainerTrackEvent(BaseModel):
    container_id: str = Field(..., pattern=r"^[A-Z]{4}\d{7}$")
    carrier_bic: str = Field(..., max_length=4)
    event_type: Literal["GATE_IN", "LOADED_ON_VESSEL", "VESSEL_DEPARTURE", "DISCHARGED", "GATE_OUT_DELIVERED"]
    location_unlocode: str
    event_timestamp: str
