"use client";

import {
  ColorType,
  CrosshairMode,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
  createChart,
} from "lightweight-charts";
import * as React from "react";


type ChartBar = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type Pivot = {
  idx: number;
  datetime: string;
  price: number;
  type: "H" | "L";
  label: string;
  confirmed: boolean;
};

type InvalidationLevel = {
  price: number;
  direction: "above" | "below";
  reason: string;
};

type FibLevel = {
  ratio: number;
  price: number;
};

type ChannelLine = {
  slope: number;
  intercept: number;
};

type ChannelLines = {
  upper: ChannelLine;
  lower: ChannelLine;
  slope_angle_deg: number;
  fit_pivot_indices: number[];
};


export interface PriceChartProps {
  bars: ChartBar[];
  pivots: Pivot[];
  channelLines: ChannelLines;
  fibonacciRetracements?: FibLevel[];
  invalidationLevels?: InvalidationLevel[];
  showPivots?: boolean;
  showChannel?: boolean;
  showFibs?: boolean;
  showInvalidation?: boolean;
}


export function PriceChart(props: PriceChartProps) {
  const {
    bars,
    pivots,
    channelLines,
    fibonacciRetracements = [],
    invalidationLevels = [],
    showPivots = true,
    showChannel = true,
    showFibs = true,
    showInvalidation = true,
  } = props;
  const containerRef = React.useRef<HTMLDivElement>(null);
  const chartRef = React.useRef<IChartApi | null>(null);
  const candleSeriesRef = React.useRef<ISeriesApi<"Candlestick"> | null>(null);

  // Mount chart once
  React.useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9099a8",
        fontFamily: "var(--font-inter), system-ui",
      },
      grid: {
        vertLines: { color: "rgba(120,128,140,0.08)" },
        horzLines: { color: "rgba(120,128,140,0.08)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: {
        borderColor: "rgba(120,128,140,0.20)",
      },
      timeScale: {
        borderColor: "rgba(120,128,140,0.20)",
        rightOffset: 6,
        secondsVisible: false,
        timeVisible: true,
      },
    });
    const candles = chart.addCandlestickSeries({
      upColor: "#34d399",
      downColor: "#f87171",
      borderUpColor: "#34d399",
      borderDownColor: "#f87171",
      wickUpColor: "#34d399",
      wickDownColor: "#f87171",
    });
    chartRef.current = chart;
    candleSeriesRef.current = candles;
    return () => {
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
    };
  }, []);

  // Push bars
  React.useEffect(() => {
    if (!candleSeriesRef.current) return;
    candleSeriesRef.current.setData(
      bars.map((b) => ({
        time: b.time as Time,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      })),
    );
    chartRef.current?.timeScale().fitContent();
  }, [bars]);

  // Pivot markers (with labels)
  React.useEffect(() => {
    if (!candleSeriesRef.current) return;
    if (!showPivots) {
      candleSeriesRef.current.setMarkers([]);
      return;
    }
    const barIdxByIdx = new Map<number, ChartBar>();
    bars.forEach((b, i) => barIdxByIdx.set(i, b));

    const markers: SeriesMarker<Time>[] = pivots
      .map((p): SeriesMarker<Time> | null => {
        const bar = barIdxByIdx.get(p.idx);
        if (!bar) return null;
        return {
          time: bar.time as Time,
          position: p.type === "H" ? "aboveBar" : "belowBar",
          color: p.confirmed ? "#fbbf24" : "rgba(251,191,36,0.55)",
          shape: p.type === "H" ? "arrowDown" : "arrowUp",
          text: p.label !== "?" ? p.label : "",
          size: 1,
        };
      })
      .filter((m): m is SeriesMarker<Time> => m !== null);
    candleSeriesRef.current.setMarkers(markers);
  }, [pivots, bars, showPivots]);

  // Channel lines (upper + lower)
  React.useEffect(() => {
    const chart = chartRef.current;
    const series = candleSeriesRef.current;
    if (!chart || !series) return;
    const removed: { remove: () => void }[] = [];
    if (!showChannel || bars.length === 0) {
      return () => undefined;
    }
    // Channel lines are y = slope * idx + intercept where idx is the bar index.
    const upper = chart.addLineSeries({
      color: "rgba(160, 170, 200, 0.45)",
      lineStyle: LineStyle.Dashed,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    const lower = chart.addLineSeries({
      color: "rgba(160, 170, 200, 0.45)",
      lineStyle: LineStyle.Dashed,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    upper.setData(
      bars.map((b, i) => ({
        time: b.time as Time,
        value: channelLines.upper.slope * i + channelLines.upper.intercept,
      })),
    );
    lower.setData(
      bars.map((b, i) => ({
        time: b.time as Time,
        value: channelLines.lower.slope * i + channelLines.lower.intercept,
      })),
    );
    removed.push({ remove: () => chart.removeSeries(upper) });
    removed.push({ remove: () => chart.removeSeries(lower) });
    return () => {
      for (const r of removed) r.remove();
    };
  }, [bars, channelLines, showChannel]);

  // Fibonacci retracement price lines
  React.useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;
    if (!showFibs) return () => undefined;
    const handles = fibonacciRetracements.map((f) =>
      series.createPriceLine({
        price: f.price,
        color: "rgba(180, 175, 220, 0.55)",
        lineStyle: LineStyle.Dotted,
        lineWidth: 1,
        axisLabelVisible: true,
        title: `r${Math.round(f.ratio * 100)}`,
      }),
    );
    return () => {
      for (const h of handles) series.removePriceLine(h);
    };
  }, [fibonacciRetracements, showFibs]);

  // Invalidation levels
  React.useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;
    if (!showInvalidation) return () => undefined;
    const handles = invalidationLevels.map((inv) =>
      series.createPriceLine({
        price: inv.price,
        color: "#fb923c",
        lineStyle: LineStyle.Solid,
        lineWidth: 2,
        axisLabelVisible: true,
        title: `Invalid: ${inv.price.toFixed(0)}`,
      }),
    );
    return () => {
      for (const h of handles) series.removePriceLine(h);
    };
  }, [invalidationLevels, showInvalidation]);

  return (
    <div
      ref={containerRef}
      className="h-[460px] w-full rounded-md border border-[color:var(--color-border)] bg-[color:var(--color-card)]"
      role="img"
      aria-label="Interactive price chart with pivot annotations and structural overlays"
    />
  );
}
