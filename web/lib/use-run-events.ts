"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { wsBase } from "@/lib/api";
import { RunEventSchema, type RunEvent } from "@/lib/schemas";


export type ConnectionStatus = "connecting" | "open" | "closed" | "error";


export interface RunEventsState {
  events: RunEvent[];
  status: ConnectionStatus;
  error: string | null;
}


export interface AgentRowState {
  agent: "elliott" | "neowave";
  timeframe: string;
  phase: "queued" | "running" | "completed";
  candidates?: number;
  cacheHit?: boolean;
}


export interface DerivedRunState {
  timeframes: string[];
  agentRows: AgentRowState[];
  validationByTimeframe: Record<
    string,
    {
      elliott_surviving: number;
      elliott_rejected: number;
      neowave_surviving: number;
      neowave_rejected: number;
    } | undefined
  >;
  synthesisPhase: "queued" | "running" | "completed";
  synthesisScenarios?: number;
  runPhase: "running" | "completed" | "error";
  errorMessage?: string;
}


export function useRunEvents(runId: string): RunEventsState {
  const [state, setState] = useState<RunEventsState>({
    events: [],
    status: "connecting",
    error: null,
  });
  // Track open sockets across React StrictMode double-effects.
  const closingRef = useRef(false);

  useEffect(() => {
    closingRef.current = false;
    const ws = new WebSocket(`${wsBase}/ws/runs/${runId}`);

    ws.onopen = () => {
      if (!closingRef.current) setState((s) => ({ ...s, status: "open" }));
    };
    ws.onmessage = (msgEvt: MessageEvent) => {
      try {
        const raw: unknown = JSON.parse(msgEvt.data as string);
        const parsed = RunEventSchema.safeParse(raw);
        if (parsed.success) {
          setState((s) => ({ ...s, events: [...s.events, parsed.data] }));
        }
      } catch {
        /* ignore malformed frame */
      }
    };
    ws.onclose = () => {
      if (!closingRef.current) setState((s) => ({ ...s, status: "closed" }));
    };
    ws.onerror = () => {
      if (!closingRef.current) {
        setState((s) => ({ ...s, status: "error", error: "WebSocket error" }));
      }
    };

    return () => {
      closingRef.current = true;
      try {
        ws.close();
      } catch {
        /* noop */
      }
    };
  }, [runId]);

  return state;
}


/** Derive a friendly UI state from the raw event list. Pure function — easy to test. */
export function deriveRunState(events: readonly RunEvent[]): DerivedRunState {
  const timeframes: string[] = [];
  const agentRows = new Map<string, AgentRowState>();
  const validationByTimeframe: DerivedRunState["validationByTimeframe"] = {};
  let synthesisPhase: DerivedRunState["synthesisPhase"] = "queued";
  let synthesisScenarios: number | undefined;
  let runPhase: DerivedRunState["runPhase"] = "running";
  let errorMessage: string | undefined;

  for (const evt of events) {
    const data = (evt.data ?? {}) as Record<string, unknown>;
    switch (evt.type) {
      case "preprocessing_started": {
        const tfs = data.timeframes as string[] | undefined;
        if (Array.isArray(tfs)) {
          for (const tf of tfs) {
            if (!timeframes.includes(tf)) timeframes.push(tf);
            for (const agent of ["elliott", "neowave"] as const) {
              const key = `${agent}:${tf}`;
              if (!agentRows.has(key)) {
                agentRows.set(key, { agent, timeframe: tf, phase: "queued" });
              }
            }
          }
        }
        break;
      }
      case "agent_started": {
        const agent = data.agent as "elliott" | "neowave" | undefined;
        const tf = data.timeframe as string | undefined;
        if (agent && tf) {
          if (!timeframes.includes(tf)) timeframes.push(tf);
          agentRows.set(`${agent}:${tf}`, { agent, timeframe: tf, phase: "running" });
        }
        break;
      }
      case "agent_completed": {
        const agent = data.agent as "elliott" | "neowave" | undefined;
        const tf = data.timeframe as string | undefined;
        const candidates = data.candidates as number | undefined;
        const cacheHit = Boolean(data.cache_hit);
        if (agent && tf) {
          agentRows.set(`${agent}:${tf}`, {
            agent,
            timeframe: tf,
            phase: "completed",
            candidates,
            cacheHit,
          });
        }
        break;
      }
      case "validation_completed": {
        const tf = data.timeframe as string | undefined;
        if (tf) {
          validationByTimeframe[tf] = {
            elliott_surviving: Number(data.elliott_surviving ?? 0),
            elliott_rejected: Number(data.elliott_rejected ?? 0),
            neowave_surviving: Number(data.neowave_surviving ?? 0),
            neowave_rejected: Number(data.neowave_rejected ?? 0),
          };
        }
        break;
      }
      case "synthesis_started":
        synthesisPhase = "running";
        break;
      case "synthesis_completed":
        synthesisPhase = "completed";
        synthesisScenarios = Number(data.scenarios ?? 0);
        break;
      case "run_completed":
        runPhase = "completed";
        break;
      case "error":
        runPhase = "error";
        errorMessage =
          (data.message as string | undefined) ?? "An error occurred during the run.";
        break;
    }
  }

  return {
    timeframes,
    agentRows: [...agentRows.values()],
    validationByTimeframe,
    synthesisPhase,
    synthesisScenarios,
    runPhase,
    errorMessage,
  };
}


export function useDerivedRunState(events: readonly RunEvent[]): DerivedRunState {
  return useMemo(() => deriveRunState(events), [events]);
}
