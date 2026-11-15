from dataclasses import dataclass

@dataclass
class Order:
    target_period_s: float
    axle_diameter_mm: float
    spool_ids: dict[str,int]