/** Timeframe labels — mirrors backend `app.schemas.timeframe.Timeframe`. */
export const TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1D", "1W", "1M"] as const;

export type Timeframe = (typeof TIMEFRAMES)[number];
