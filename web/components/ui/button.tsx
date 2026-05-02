"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost";
type Size = "default" | "sm";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-[color:var(--color-accent)] text-[color:var(--color-accent-fg)] hover:opacity-90 disabled:opacity-50",
  secondary:
    "bg-[color:var(--color-card)] text-[color:var(--color-fg)] border border-[color:var(--color-border)] hover:border-[color:var(--color-accent)] disabled:opacity-50",
  ghost:
    "text-[color:var(--color-fg)] hover:bg-[color:var(--color-card)] disabled:opacity-50",
};

const SIZES: Record<Size, string> = {
  default: "h-10 px-5 text-sm",
  sm: "h-8 px-3 text-xs",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "default", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-[opacity,border-color,background] duration-200 ease-out focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--color-accent)] disabled:cursor-not-allowed",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    />
  ),
);
Button.displayName = "Button";
