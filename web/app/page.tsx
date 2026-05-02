"use client";

import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

import { Dropzone } from "@/components/dropzone";
import { FileRow, type FileRowState } from "@/components/file-row";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, postAnalyze, postUpload } from "@/lib/api";
import type { FileValidation } from "@/lib/schemas";
import { TIMEFRAMES, type Timeframe } from "@/lib/timeframes";


type StagedFile = {
  id: string;
  file: File;
  timeframe: Timeframe;
  state: FileRowState;
  validation: FileValidation | null;
};


/** Pick the first timeframe not already in use; fall back to "1D" if all are taken. */
function nextDefaultTimeframe(used: Set<string>): Timeframe {
  return (TIMEFRAMES.find((tf) => !used.has(tf)) ?? "1D") as Timeframe;
}


export default function HomePage() {
  const router = useRouter();
  const [instrumentName, setInstrumentName] = useState("");
  const [staged, setStaged] = useState<StagedFile[]>([]);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [phase, setPhase] = useState<"idle" | "uploading" | "starting">("idle");

  const onFiles = useCallback((files: File[]) => {
    setSubmitError(null);
    setStaged((prev) => {
      const used = new Set(prev.map((s) => s.timeframe));
      const additions: StagedFile[] = [];
      for (const file of files) {
        const tf = nextDefaultTimeframe(used);
        used.add(tf);
        additions.push({
          id: crypto.randomUUID(),
          file,
          timeframe: tf,
          state: "pending",
          validation: null,
        });
      }
      return [...prev, ...additions];
    });
  }, []);

  const removeFile = (id: string) => {
    setStaged((prev) => prev.filter((s) => s.id !== id));
  };

  const setTimeframe = (id: string, tf: Timeframe) => {
    setStaged((prev) => prev.map((s) => (s.id === id ? { ...s, timeframe: tf } : s)));
  };

  const duplicateTimeframes = useMemo(() => {
    const counts = new Map<string, number>();
    for (const s of staged) {
      counts.set(s.timeframe, (counts.get(s.timeframe) ?? 0) + 1);
    }
    return [...counts.entries()].filter(([, n]) => n > 1).map(([tf]) => tf);
  }, [staged]);

  const canSubmit =
    staged.length > 0 &&
    instrumentName.trim().length > 0 &&
    duplicateTimeframes.length === 0 &&
    phase === "idle";

  const submit = async () => {
    if (!canSubmit) return;
    setSubmitError(null);
    setPhase("uploading");
    setStaged((prev) => prev.map((s) => ({ ...s, state: "validating", validation: null })));

    try {
      const upload = await postUpload({
        instrumentName: instrumentName.trim(),
        files: staged.map((s) => ({ file: s.file, timeframe: s.timeframe })),
      });

      setStaged((prev) =>
        prev.map((s) => {
          const result = upload.files.find(
            (f) => f.filename === s.file.name && f.timeframe === s.timeframe,
          );
          return {
            ...s,
            validation: result ?? null,
            state: result
              ? result.issues.some((i) => i.severity === "error")
                ? "invalid"
                : "valid"
              : "invalid",
          };
        }),
      );

      if (!upload.accepted) {
        setSubmitError(
          "One or more files failed validation. Fix the issues below and try again.",
        );
        setPhase("idle");
        return;
      }

      setPhase("starting");
      const analyze = await postAnalyze({
        sessionId: upload.session_id,
        instrumentName: instrumentName.trim(),
      });
      router.push(`/analyze/${analyze.run_id}`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : (err as Error).message;
      setSubmitError(message);
      setStaged((prev) => prev.map((s) => ({ ...s, state: "pending" })));
      setPhase("idle");
    }
  };

  return (
    <section className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-12">
      <motion.header
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
        className="flex flex-col gap-3"
      >
        <span className="text-xs font-medium uppercase tracking-[0.18em] text-[color:var(--color-accent)]">
          Multi-agent structural analysis
        </span>
        <h1 className="text-3xl font-semibold tracking-tight text-[color:var(--color-fg)] sm:text-4xl">
          Upload OHLCV CSVs for an instrument
        </h1>
        <p className="text-sm leading-relaxed text-[color:var(--color-muted)] sm:text-base">
          Drop one CSV per timeframe (e.g. monthly, weekly, daily, 4h, 1h).
          Deterministic Python preprocessing builds a compact structural summary
          per timeframe; LLM agents then propose ranked Elliott + NEOWave counts
          on those summaries — never on raw price data.
        </p>
      </motion.header>

      <Card>
        <CardHeader>
          <CardTitle>Instrument</CardTitle>
          <CardDescription>
            Free-text label — &ldquo;NIFTY 50&rdquo;, &ldquo;RELIANCE&rdquo;, &ldquo;BTC-USD&rdquo;.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Input
            value={instrumentName}
            onChange={(e) => setInstrumentName(e.currentTarget.value)}
            placeholder="e.g. NIFTY 50"
            maxLength={80}
            disabled={phase !== "idle"}
            autoFocus
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Timeframes</CardTitle>
          <CardDescription>
            Up to 8 files. Per-file timeframe selector — wave-agent does not
            auto-detect (auto-detection is brittle around weekends and holidays).
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {staged.length > 0 ? (
            <div className="flex flex-col gap-3">
              {staged.map((s) => (
                <FileRow
                  key={s.id}
                  file={s.file}
                  timeframe={s.timeframe}
                  state={s.state}
                  validation={s.validation}
                  onTimeframeChange={(tf) => setTimeframe(s.id, tf)}
                  onRemove={() => removeFile(s.id)}
                />
              ))}
            </div>
          ) : null}

          <Dropzone onFiles={onFiles} disabled={phase !== "idle" || staged.length >= 8} />

          {duplicateTimeframes.length > 0 ? (
            <div className="flex items-start gap-2 rounded-md border border-amber-700/40 bg-amber-900/20 p-3 text-xs text-amber-200">
              <AlertTriangle className="mt-0.5 h-4 w-4" aria-hidden />
              <p>
                Duplicate timeframe label
                {duplicateTimeframes.length > 1 ? "s" : ""}:{" "}
                {duplicateTimeframes.map((tf) => (
                  <Badge key={tf} tone="warning" className="mx-1">
                    {tf}
                  </Badge>
                ))}
                — each timeframe may appear at most once per session.
              </p>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {submitError ? (
        <div className="rounded-md border border-red-700/40 bg-red-950/30 p-3 text-sm text-red-200">
          {submitError}
        </div>
      ) : null}

      <div className="flex items-center justify-between gap-4">
        <p className="text-xs text-[color:var(--color-muted)]">
          Numeric levels in the report are computed in Python — never generated by an LLM.
        </p>
        <Button onClick={submit} disabled={!canSubmit} aria-disabled={!canSubmit}>
          {phase === "uploading" ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              Validating
            </>
          ) : phase === "starting" ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              Starting analysis
            </>
          ) : (
            <>
              Run analysis <ArrowRight className="h-4 w-4" aria-hidden />
            </>
          )}
        </Button>
      </div>
    </section>
  );
}
