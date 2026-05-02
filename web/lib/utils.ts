import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Tailwind class merger — combines clsx + tailwind-merge so later utilities win. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const DISCLAIMER =
  "wave-agent is an educational and engineering demo. It is NOT investment advice " +
  "and NOT a trading recommendation. The system proposes structural interpretations " +
  "and deterministic levels; humans decide actions. Numeric levels (invalidation, " +
  "Fibonacci, channel projections) are properties of past price geometry, not forecasts.";
