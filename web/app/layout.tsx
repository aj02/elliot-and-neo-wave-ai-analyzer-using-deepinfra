import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";

import { ThemeToggle } from "@/components/theme-toggle";

import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "wave-agent — Elliott Wave + NEOWave structural analysis",
  description:
    "Educational engineering demo. Multi-agent Elliott Wave + NEOWave structural " +
    "analysis on uploaded OHLCV CSVs. Not investment advice.",
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: {
  readonly children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body className="min-h-dvh antialiased">
        <Providers>
          <div className="flex min-h-dvh flex-col">
            <header className="flex items-center justify-between border-b border-[color:var(--color-border)] bg-[color:var(--color-card)]/40 px-6 py-3 text-sm">
              <Link
                href="/"
                className="flex items-baseline gap-2 font-semibold tracking-tight text-[color:var(--color-fg)]"
              >
                <span className="text-[color:var(--color-accent)]">wave-agent</span>
                <span className="text-xs font-normal text-[color:var(--color-muted)]">
                  educational demo · not investment advice
                </span>
              </Link>
              <div className="flex items-center gap-4">
                <nav className="hidden gap-5 text-xs text-[color:var(--color-muted)] sm:flex">
                  <Link href="/" className="hover:text-[color:var(--color-fg)]">
                    Upload
                  </Link>
                  <Link href="/about" className="hover:text-[color:var(--color-fg)]">
                    About
                  </Link>
                </nav>
                <ThemeToggle />
              </div>
            </header>
            <main className="flex-1">{children}</main>
            <footer className="border-t border-[color:var(--color-border)] bg-[color:var(--color-card)] px-6 py-4 text-xs leading-relaxed text-[color:var(--color-muted)]">
              <p>
                <strong className="text-[color:var(--color-fg)]">Disclaimer.</strong>{" "}
                wave-agent is an educational engineering demo. It is not investment
                advice and not a trading recommendation. The system proposes
                structural interpretations and deterministic levels; humans decide
                actions. Numeric levels are properties of past price geometry, not
                forecasts.
              </p>
            </footer>
          </div>
        </Providers>
      </body>
    </html>
  );
}
