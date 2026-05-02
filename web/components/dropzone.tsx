"use client";

import { motion } from "framer-motion";
import { Upload } from "lucide-react";
import { useDropzone } from "react-dropzone";

import { cn } from "@/lib/utils";

export interface DropzoneProps {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
}

export function Dropzone({ onFiles, disabled }: DropzoneProps) {
  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    accept: { "text/csv": [".csv"] },
    multiple: true,
    disabled,
    onDropAccepted: onFiles,
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
    >
      <div
        {...getRootProps()}
        className={cn(
          "group relative flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-[color:var(--color-border)] bg-[color:var(--color-card)]/40 p-12 text-center transition-colors duration-200",
          "hover:border-[color:var(--color-accent)]/70",
          isDragActive && "border-[color:var(--color-accent)] bg-[color:var(--color-card)]",
          isDragReject && "border-red-500/60 bg-red-950/20",
          disabled && "cursor-not-allowed opacity-50",
        )}
      >
        <input {...getInputProps()} />
        <Upload
          className="h-7 w-7 text-[color:var(--color-muted)] transition-colors group-hover:text-[color:var(--color-accent)]"
          aria-hidden
        />
        <div className="space-y-1">
          <p className="text-sm font-medium text-[color:var(--color-fg)]">
            {isDragActive ? "Drop the CSVs here" : "Drag & drop CSV files, or click to browse"}
          </p>
          <p className="text-xs text-[color:var(--color-muted)]">
            One file per timeframe. Required columns:{" "}
            <code>datetime, open, high, low, close, volume</code>. Min 100 rows, max 50,000.
          </p>
        </div>
      </div>
    </motion.div>
  );
}
