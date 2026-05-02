"""GET /runs/{run_id}/chart-data/{timeframe} schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.levels import InvalidationLevel
from app.schemas.responses import _BaseResponse
from app.schemas.structure import ChannelLines, FibZones, Pivot
from app.schemas.validated import ValidatedElliottCount, ValidatedNeowaveCount


class ChartBar(BaseModel):
    """One OHLCV bar in Lightweight-Charts-compatible shape."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    time: int = Field(description="Unix timestamp in seconds (UTC).")
    open: float
    high: float
    low: float
    close: float
    volume: int


class ChartDataResponse(_BaseResponse):
    run_id: str
    timeframe: str
    instrument_name: str
    bars: list[ChartBar]
    pivots: list[Pivot]
    elliott_counts: list[ValidatedElliottCount] = Field(default_factory=list)
    neowave_counts: list[ValidatedNeowaveCount] = Field(default_factory=list)
    invalidation_levels: list[InvalidationLevel] = Field(default_factory=list)
    fibonacci_zones: FibZones | None = None
    channel_lines: ChannelLines
