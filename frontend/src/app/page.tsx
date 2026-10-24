"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Plus,
  Play,
  Pause,
  Square,
  ArrowUpRight,
  Users,
  FlaskConical,
  Percent,
  DollarSign,
  AlertCircle,
  Sparkles,
  Trash2,
} from "lucide-react";
import {
  api,
  Experiment,
  ExperimentCreateInput,
  ExperimentStatus,
  MetricType,
} from "@/lib/api";

const STATUS_BADGE: Record<
  ExperimentStatus,
  { label: string; className: string; dot: string }
> = {
  running: {
    label: "Running",
    className:
      "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    dot: "bg-emerald-400 animate-pulse",
  },
  completed: {
    label: "Completed",
    className: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
    dot: "bg-indigo-400",
  },
  paused: {
    label: "Paused",
    className: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    dot: "bg-amber-400",
  },
  draft: {
    label: "Draft",
    className: "bg-slate-800 text-slate-300 border-slate-700",
    dot: "bg-slate-400",
  },
};

export default function HomePage() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [statusFilter, setStatusFilter] = useState<ExperimentStatus | "all">(
    "all"
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.listExperiments(
        statusFilter === "all" ? undefined : statusFilter
      );
      setExperiments(list);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not reach the ExperimentIQ backend."
      );
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const handleTransition = async (
    id: number,
    action: "start" | "pause" | "end"
  ) => {
    try {
      await api.transitionExperiment(id, action);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Transition failed");
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Delete experiment "${name}" and all its logged events?`)) {
      return;
    }
    try {
      await api.deleteExperiment(id);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const totalUsers = experiments.reduce((acc, e) => acc + (e.users || 0), 0);
  const runningCount = experiments.filter((e) => e.status === "running").length;
  const completedCount = experiments.filter(
    (e) => e.status === "completed"
  ).length;

  return (
    <div className="space-y-8">
      {/* Header Banner */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Experiments
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Deterministic SHA-256 variant assignment, real-time event logging,
            and SciPy-verified hypothesis tests.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-600/20 hover:bg-indigo-500 transition"
        >
          <Plus className="h-4 w-4" />
          New Experiment
        </button>
      </div>

      {/* KPI Summary Strip */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-800/90 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between text-xs font-medium text-slate-400">
            <span>Total Experiments</span>
            <FlaskConical className="h-4 w-4 text-indigo-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-white">
            {experiments.length}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Two-arm A/B controlled designs
          </p>
        </div>

        <div className="rounded-xl border border-slate-800/90 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between text-xs font-medium text-slate-400">
            <span>Active / Running</span>
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse" />
          </div>
          <p className="mt-2 text-2xl font-bold text-emerald-300">
            {runningCount}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Currently bucketing traffic
          </p>
        </div>

        <div className="rounded-xl border border-slate-800/90 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between text-xs font-medium text-slate-400">
            <span>Completed Decisions</span>
            <Sparkles className="h-4 w-4 text-indigo-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-indigo-300">
            {completedCount}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Locked for post-hoc analysis
          </p>
        </div>

        <div className="rounded-xl border border-slate-800/90 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between text-xs font-medium text-slate-400">
            <span>Assigned Users</span>
            <Users className="h-4 w-4 text-sky-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-white">
            {totalUsers.toLocaleString()}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Across visible experiments
          </p>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex flex-wrap gap-1.5">
          {(["all", "running", "completed", "paused", "draft"] as const).map(
            (st) => (
              <button
                key={st}
                type="button"
                onClick={() => setStatusFilter(st)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition ${
                  statusFilter === st
                    ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                    : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
                }`}
              >
                {st}
              </button>
            )
          )}
        </div>
        <span className="text-xs text-slate-500">
          Click any experiment to inspect confidence intervals, p-values &amp; SRM checks
        </span>
      </div>

      {/* Error State */}
      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200">
          <AlertCircle className="h-5 w-5 shrink-0 text-rose-400" />
          <div>
            <p className="font-semibold">Backend Connection Error</p>
            <p className="mt-0.5 text-xs text-rose-300/90">{error}</p>
            <p className="mt-2 text-xs text-slate-300">
              Ensure the FastAPI server is running on{" "}
              <code className="rounded bg-slate-900 px-1.5 py-0.5 font-mono">
                http://localhost:8000
              </code>{" "}
              and seeded with{" "}
              <code className="rounded bg-slate-900 px-1.5 py-0.5 font-mono">
                python -m simulator.simulate --reset
              </code>
              .
            </p>
          </div>
        </div>
      )}

      {/* Experiments List */}
      {loading ? (
        <div className="grid grid-cols-1 gap-4">
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              className="h-32 animate-pulse rounded-xl border border-slate-800/80 bg-slate-900/50"
            />
          ))}
        </div>
      ) : experiments.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-900/30 p-12 text-center">
          <FlaskConical className="mx-auto h-10 w-10 text-slate-600" />
          <h3 className="mt-3 text-base font-semibold text-white">
            No experiments found
          </h3>
          <p className="mt-1 text-xs text-slate-400">
            Create a new experiment or run the traffic simulator to populate demo experiments.
          </p>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
          >
            <Plus className="h-4 w-4" />
            Create First Experiment
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {experiments.map((exp) => {
            const badge = STATUS_BADGE[exp.status];
            const control = exp.variants.find((v) => v.is_control) || exp.variants[0];
            const treatment =
              exp.variants.find((v) => !v.is_control) || exp.variants[1];

            return (
              <div
                key={exp.id}
                className="group relative rounded-xl border border-slate-800/90 bg-slate-900/60 p-5 transition hover:border-indigo-500/40 hover:bg-slate-900"
              >
                <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2.5">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${badge.className}`}
                      >
                        <span className={`h-1.5 w-1.5 rounded-full ${badge.dot}`} />
                        {badge.label}
                      </span>
                      <span className="inline-flex items-center gap-1 rounded-md bg-slate-800/90 px-2 py-0.5 text-xs font-medium text-slate-300">
                        {exp.metric_type === "conversion" ? (
                          <Percent className="h-3 w-3 text-indigo-400" />
                        ) : (
                          <DollarSign className="h-3 w-3 text-emerald-400" />
                        )}
                        {exp.metric_type === "conversion"
                          ? "Conversion (Z-Test)"
                          : "Continuous (Welch T-Test)"}
                      </span>
                      <code className="rounded bg-slate-950 px-2 py-0.5 font-mono text-xs text-slate-400 border border-slate-800">
                        {exp.key}
                      </code>
                    </div>

                    <Link
                      href={`/experiments/${exp.id}`}
                      className="inline-flex items-center gap-1.5 text-lg font-semibold text-white group-hover:text-indigo-300 transition"
                    >
                      {exp.name}
                      <ArrowUpRight className="h-4 w-4 opacity-60 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition" />
                    </Link>

                    {exp.hypothesis && (
                      <p className="text-xs text-slate-400 line-clamp-2 max-w-3xl">
                        <span className="font-medium text-slate-300">
                          Hypothesis:
                        </span>{" "}
                        {exp.hypothesis}
                      </p>
                    )}
                  </div>

                  {/* Right metrics & controls */}
                  <div className="flex flex-wrap items-center gap-6 border-t border-slate-800/80 pt-3 lg:border-t-0 lg:pt-0">
                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-slate-500">
                        Success Event
                      </div>
                      <div className="mt-0.5 font-mono text-xs font-semibold text-slate-200">
                        {exp.metric_event}
                      </div>
                    </div>

                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-slate-500">
                        Traffic Split
                      </div>
                      <div className="mt-0.5 text-xs font-semibold text-slate-200">
                        {Math.round((control?.weight ?? 0.5) * 100)}% /{" "}
                        {Math.round((treatment?.weight ?? 0.5) * 100)}%
                        {exp.traffic_allocation < 1 && (
                          <span className="ml-1 text-slate-400">
                            ({Math.round(exp.traffic_allocation * 100)}% alloc)
                          </span>
                        )}
                      </div>
                    </div>

                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-slate-500">
                        Target MDE / &alpha;
                      </div>
                      <div className="mt-0.5 text-xs font-semibold text-slate-200">
                        {(exp.mde * 100).toFixed(0)}% rel &middot;{" "}
                        {(exp.alpha * 100).toFixed(0)}%
                      </div>
                    </div>

                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-slate-500">
                        Users Assigned
                      </div>
                      <div className="mt-0.5 font-mono text-sm font-bold text-white">
                        {exp.users.toLocaleString()}
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5">
                      {(exp.status === "draft" || exp.status === "paused") && (
                        <button
                          type="button"
                          onClick={() => handleTransition(exp.id, "start")}
                          title={
                            exp.status === "draft"
                              ? "Start experiment"
                              : "Resume experiment"
                          }
                          className="inline-flex items-center gap-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1.5 text-xs font-medium text-emerald-300 hover:bg-emerald-500/20"
                        >
                          <Play className="h-3.5 w-3.5" />
                          {exp.status === "draft" ? "Start" : "Resume"}
                        </button>
                      )}
                      {exp.status === "running" && (
                        <button
                          type="button"
                          onClick={() => handleTransition(exp.id, "pause")}
                          title="Pause experiment"
                          className="inline-flex items-center gap-1 rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-1.5 text-xs font-medium text-amber-300 hover:bg-amber-500/20"
                        >
                          <Pause className="h-3.5 w-3.5" />
                          Pause
                        </button>
                      )}
                      {(exp.status === "running" ||
                        exp.status === "paused") && (
                        <button
                          type="button"
                          onClick={() => handleTransition(exp.id, "end")}
                          title="End experiment"
                          className="inline-flex items-center gap-1 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-2.5 py-1.5 text-xs font-medium text-indigo-300 hover:bg-indigo-500/20"
                        >
                          <Square className="h-3.5 w-3.5" />
                          End
                        </button>
                      )}
                      <Link
                        href={`/experiments/${exp.id}`}
                        className="inline-flex items-center gap-1 rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-700"
                      >
                        Results
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      </Link>
                      <button
                        type="button"
                        onClick={() => handleDelete(exp.id, exp.name)}
                        title="Delete experiment"
                        className="rounded-lg p-1.5 text-slate-500 hover:bg-rose-500/10 hover:text-rose-400"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {showCreate && (
        <CreateExperimentModal
          onClose={() => setShowCreate(false)}
          onCreated={async () => {
            setShowCreate(false);
            await load();
          }}
        />
      )}
    </div>
  );
}

function CreateExperimentModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [key, setKey] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [metricType, setMetricType] = useState<MetricType>("conversion");
  const [metricEvent, setMetricEvent] = useState("purchase");
  const [treatmentShare, setTreatmentShare] = useState(50);
  const [trafficAllocation, setTrafficAllocation] = useState(100);
  const [mdePct, setMdePct] = useState(10);
  const [alpha, setAlpha] = useState(0.05);
  const [power, setPower] = useState(0.8);
  const [controlName, setControlName] = useState("Control");
  const [treatmentName, setTreatmentName] = useState("Treatment");
  const [startImmediately, setStartImmediately] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErr(null);
    try {
      const wTreat = Number((treatmentShare / 100).toFixed(2));
      const wCtrl = Number((1 - wTreat).toFixed(2));
      const payload: ExperimentCreateInput = {
        name: name.trim(),
        key: key.trim() ? key.trim() : undefined,
        hypothesis: hypothesis.trim(),
        metric_type: metricType,
        metric_event: metricEvent.trim(),
        traffic_allocation: Number((trafficAllocation / 100).toFixed(2)),
        alpha,
        power,
        mde: Number((mdePct / 100).toFixed(4)),
        variants: [
          {
            key: "control",
            name: controlName.trim() || "Control",
            weight: wCtrl,
            is_control: true,
          },
          {
            key: "treatment",
            name: treatmentName.trim() || "Treatment",
            weight: wTreat,
            is_control: false,
          },
        ],
      };
      const created = await api.createExperiment(payload);
      if (startImmediately) {
        await api.transitionExperiment(created.id, "start");
      }
      onCreated();
    } catch (error) {
      setErr(error instanceof Error ? error.message : "Failed to create");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm overflow-y-auto">
      <div className="w-full max-w-xl rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl my-8">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <h2 className="text-lg font-bold text-white">Create A/B Experiment</h2>
            <p className="text-xs text-slate-400">
              Pre-register your success metric, traffic split, and minimum detectable effect.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-xs text-slate-400 hover:text-white"
          >
            ESC
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          {err && (
            <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
              {err}
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="sm:col-span-2">
              <label className="block text-xs font-medium text-slate-300">
                Experiment Name *
              </label>
              <input
                type="text"
                required
                placeholder="e.g. One-Click Checkout Flow"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300">
                Slug Key (optional)
              </label>
              <input
                type="text"
                pattern="^[a-z0-9][a-z0-9_-]{0,63}$"
                placeholder="auto-generated"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm text-white focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300">
              Hypothesis
            </label>
            <textarea
              rows={2}
              placeholder="Replacing the 3-step checkout with a single sheet will increase purchase conversion by at least 10%."
              value={hypothesis}
              onChange={(e) => setHypothesis(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-medium text-slate-300">
                Primary Metric Type *
              </label>
              <select
                value={metricType}
                onChange={(e) => setMetricType(e.target.value as MetricType)}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
              >
                <option value="conversion">
                  Conversion Rate (Two-Proportion Z-Test)
                </option>
                <option value="continuous">
                  Continuous / Revenue (Welch&apos;s T-Test)
                </option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300">
                Success Event Name *
              </label>
              <input
                type="text"
                required
                pattern="^[A-Za-z0-9_.:-]{1,64}$"
                placeholder="purchase"
                value={metricEvent}
                onChange={(e) => setMetricEvent(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm text-white focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Variants */}
          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3.5 space-y-3">
            <div className="flex items-center justify-between text-xs font-medium text-slate-300">
              <span>
                Variant Traffic Split ({100 - treatmentShare}% Control /{" "}
                {treatmentShare}% Treatment)
              </span>
              <span className="font-mono text-indigo-300">
                {100 - treatmentShare}/{treatmentShare}
              </span>
            </div>
            <input
              type="range"
              min={10}
              max={90}
              step={5}
              value={treatmentShare}
              onChange={(e) => setTreatmentShare(Number(e.target.value))}
              className="w-full accent-indigo-500"
            />
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-slate-400">
                  Control Label
                </label>
                <input
                  type="text"
                  required
                  value={controlName}
                  onChange={(e) => setControlName(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1.5 text-xs text-white"
                />
              </div>
              <div>
                <label className="block text-[11px] text-slate-400">
                  Treatment Label
                </label>
                <input
                  type="text"
                  required
                  value={treatmentName}
                  onChange={(e) => setTreatmentName(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1.5 text-xs text-white"
                />
              </div>
            </div>
          </div>

          {/* Statistical Design Parameters */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <label className="block text-xs font-medium text-slate-300">
                Target MDE (%)
              </label>
              <input
                type="number"
                min={1}
                max={200}
                step={1}
                required
                value={mdePct}
                onChange={(e) => setMdePct(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-sm text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300">
                Significance (&alpha;)
              </label>
              <select
                value={alpha}
                onChange={(e) => setAlpha(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-sm text-white"
              >
                <option value={0.01}>0.01 (99% CI)</option>
                <option value={0.05}>0.05 (95% CI)</option>
                <option value={0.1}>0.10 (90% CI)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300">
                Power (1 - &beta;)
              </label>
              <select
                value={power}
                onChange={(e) => setPower(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-sm text-white"
              >
                <option value={0.8}>80%</option>
                <option value={0.9}>90%</option>
                <option value={0.95}>95%</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300">
                Traffic Alloc (%)
              </label>
              <input
                type="number"
                min={5}
                max={100}
                step={5}
                required
                value={trafficAllocation}
                onChange={(e) => setTrafficAllocation(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-sm text-white"
              />
            </div>
          </div>

          <label className="flex items-center gap-2 pt-1 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={startImmediately}
              onChange={(e) => setStartImmediately(e.target.checked)}
              className="rounded border-slate-700 bg-slate-950 text-indigo-600"
            />
            Start experiment immediately after creation
          </label>

          <div className="flex justify-end gap-2 border-t border-slate-800 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-xs font-medium text-slate-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-indigo-600 px-5 py-2 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {submitting ? "Creating..." : "Create Experiment"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
