import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "ExperimentIQ — Statistical A/B Testing Platform",
  description:
    "An experimentation platform that tells teams whether a product change actually worked, backed by sound statistics.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
        <Navbar />
        <main className="flex-1 mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          {children}
        </main>
        <footer className="border-t border-slate-900 py-5 text-center text-xs text-slate-500">
          ExperimentIQ &middot; Deterministic SHA-256 Bucketing &middot; Two-Proportion Z-Test &amp; Welch&apos;s T-Test Verified Against SciPy
        </footer>
      </body>
    </html>
  );
}
