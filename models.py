from typing import List, Optional, Literal
from pydantic import BaseModel, Field


DirectiveType = Literal[
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
]


class HourData(BaseModel):
    hour: int = Field(ge=0, le=23)
    demand_kwh: float = Field(ge=0)
    solar_kwh: float = Field(ge=0)
    tariff_bdt_per_kwh: float = Field(ge=0)


class BatteryData(BaseModel):
    capacity_kwh: float = Field(gt=0)
    initial_energy_kwh: float = Field(ge=0)
    minimum_energy_kwh: float = Field(ge=0)
    max_charge_kwh_per_hour: float = Field(ge=0)
    max_discharge_kwh_per_hour: float = Field(ge=0)


class EnergyScenario(BaseModel):
    scenario_id: str
    operator_notes: List[str] = Field(min_length=1, max_length=3)
    hours: List[HourData] = Field(min_length=24, max_length=24)
    battery: BatteryData


class SolarReduction(BaseModel):
    hours: List[int]
    factor: float = Field(ge=0, le=1)


class MinimumBatteryReserve(BaseModel):
    hours: List[int]
    minimum_energy_kwh: float = Field(ge=0)


class NoChargeWindow(BaseModel):
    hours: List[int]


class NoDischargeWindow(BaseModel):
    hours: List[int]


class MaxGridWindow(BaseModel):
    hours: List[int]
    max_grid_kwh: float = Field(ge=0)


class DirectiveInterpretation(BaseModel):
    note_index: int
    applies: bool
    directive_type: DirectiveType
    structured_adjustment: Optional[dict]
    explanation: str


class HourlyPlan(BaseModel):
    hour: int
    grid_kwh: float = Field(ge=0)
    solar_used_kwh: float = Field(ge=0)
    battery_action: Literal["charge", "discharge", "idle"]
    battery_kwh: float = Field(ge=0)
    battery_energy_after_kwh: float = Field(ge=0)


class OptimizationResponse(BaseModel):
    scenario_id: str
    directive_interpretation: List[DirectiveInterpretation]
    hourly_plan: List[HourlyPlan]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str
