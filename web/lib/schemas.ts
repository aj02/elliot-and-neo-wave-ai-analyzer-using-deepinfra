import { z } from "zod";

import { TIMEFRAMES } from "@/lib/timeframes";

/* eslint-disable @typescript-eslint/no-redeclare */

export const TimeframeSchema = z.enum(TIMEFRAMES);

export const ValidationIssueSchema = z.object({
  severity: z.enum(["error", "warning"]),
  code: z.string(),
  message: z.string(),
  row: z.number().int().nullable().optional(),
});

export const FileValidationSchema = z.object({
  filename: z.string(),
  timeframe: TimeframeSchema,
  rows: z.number().int(),
  date_range: z.tuple([z.string(), z.string()]).nullable(),
  issues: z.array(ValidationIssueSchema),
});

export const UploadResponseSchema = z.object({
  disclaimer: z.string(),
  session_id: z.string(),
  instrument_name: z.string(),
  files: z.array(FileValidationSchema),
  accepted: z.boolean(),
});

export const AnalyzeResponseSchema = z.object({
  disclaimer: z.string(),
  run_id: z.string(),
  websocket_url: z.string(),
});

export const RunEventSchema = z.object({
  type: z.enum([
    "preprocessing_started",
    "preprocessing_completed",
    "agent_started",
    "agent_completed",
    "validation_completed",
    "synthesis_started",
    "synthesis_completed",
    "run_completed",
    "error",
  ]),
  run_id: z.string(),
  at: z.string(),
  data: z.record(z.string(), z.unknown()).default({}),
});

export type ValidationIssue = z.infer<typeof ValidationIssueSchema>;
export type FileValidation = z.infer<typeof FileValidationSchema>;
export type UploadResponse = z.infer<typeof UploadResponseSchema>;
export type AnalyzeResponse = z.infer<typeof AnalyzeResponseSchema>;
export type RunEvent = z.infer<typeof RunEventSchema>;
