"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { FlaskConical, Calculator, KeyRound, Check, Activity } from "lucide-react";
import { getApiConfig } from "@/lib/api";

export function Navbar() {
  const pathname = usePathname();
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [apiUrl, setApiUrl] = useState("http://localhost:8000");
  const [apiKey, setApiKey] = useState("dev-secret-key");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const cfg = getApiConfig();
    setApiUrl(cfg.baseUrl);
    setApiKey(cfg.apiKey);
  }, []);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem("experimentiq_api_url", apiUrl.trim());
    localStorage.setItem("experimentiq_api_key", apiKey.trim());
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      setShowKeyModal(false);
      window.location.reload();
    }, 500);
  };

  const navItems = [
    { href: "/", label: "Experiments", icon: FlaskConical },
    { href: "/calculator", label: "Sample-Size Calculator", icon: Calculator },
  ];

  return (
    <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-slate-950/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3.5 sm:px-6 lg:px-8">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/15 border border-indigo-500/30 text-indigo-400 group-hover:bg-indigo-500/25 transition">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-white">
                Experiment<span className="text-indigo-400">IQ</span>
              </span>
              <span className="ml-2 hidden rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-slate-400 sm:inline-block">
                Stat Engine v1.0
              </span>
            </div>
          </Link>

          <nav className="flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active =
                item.href === "/"
                  ? pathname === "/" || pathname.startsWith("/experiments")
                  : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition ${
                    active
                      ? "bg-indigo-500/15 text-indigo-300 border border-indigo-500/30"
                      : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setShowKeyModal(true)}
            className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/90 px-3 py-1.5 text-xs font-medium text-slate-300 hover:border-slate-700 hover:bg-slate-800 transition"
            title="Configure API URL & X-API-Key"
          >
            <KeyRound className="h-3.5 w-3.5 text-indigo-400" />
            <span className="hidden sm:inline">API Config</span>
          </button>
        </div>
      </div>

      {showKeyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
            <h2 className="text-lg font-semibold text-white">API Connection Settings</h2>
            <p className="mt-1 text-xs text-slate-400">
              All requests authenticate via the <code className="text-indigo-300">X-API-Key</code> header.
            </p>
            <form onSubmit={handleSave} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300">Backend URL</label>
                <input
                  type="url"
                  required
                  value={apiUrl}
                  onChange={(e) => setApiUrl(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-300">X-API-Key</label>
                <input
                  type="text"
                  required
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm text-white focus:border-indigo-500 focus:outline-none"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowKeyModal(false)}
                  className="rounded-lg px-4 py-2 text-xs font-medium text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
                >
                  {saved ? <Check className="h-4 w-4" /> : null}
                  {saved ? "Saved" : "Save & Reload"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </header>
  );
}
