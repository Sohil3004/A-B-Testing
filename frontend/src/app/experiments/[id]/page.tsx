"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  Clock,
  MinusCircle,
  TrendingUp,
  TrendingDown,
  ShieldCheck,
  Play,
  Pause,
  Square,
  Send,
  Hash,
  RefreshCw,
} from "lucide-react";
import {
  api,
  AssignResponse,
  ResultsOut,
  TimePoint,
  VariantResult,
} from "@/lib/api";

const VERDICT_THEME = {
  significant_positive: {
    border: "border-emerald-500/40",
    bg: "bg-emerald-500/10",
    text: "text-emerald-300",
    badge: "bg-emerald-500/20 text-emerald-200 border-emerald-500/40",
    icon: CheckCircle2,
  },
  significant_negative: {
    border: "border-rose-500/40",
    bg: "bg-rose-500/10",
    text: "text-rose-300",
    badge: "bg-rose-500/20 text-rose-200 border-rose-500/40",
    icon: TrendingDown,
  },
  no_significant_difference: {
    border: "border-slate-700",
    bg: "bg-slate-900/90",
    text: "text-slate-200",
    badge: "bg-slate-800 text-slate-300 border-slate-700",
    icon: MinusCircle,
  },
  not_enough_data: {
    border: "border-amber-500/40",
    bg: "bg-amber-500/10",
    text: "text-amber-300",
    badge: "bg-amber-500/20 text-amber-200 border-amber-500/40",
    icon: Clock,
  },
};

function fmtPct(v: number | null | undefined, digits = 2, signed = false): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const pct = (v * 100).toFixed(digits);
  return signed && v > 0 ? `+${pct}%` : `${pct}%`;
}

function fmtMetric(
  v: number | null | undefined,
  isConversion: boolean
): string {
  if (v === null || v === undefined) return "—";
  return isConversion ? `${(v * 100).toFixed(2)}%` : `$${v.toFixed(2)}`;
}

export default function ExperimentResultsPage() {
  const params = useParams<{ id: string }>();
  const experimentId = Number(params.id);

  const [data, setData] = useState<ResultsOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Live sandbox state
  const [testUserId, setTestUserId] = useState("user-demo-42");
  const [assignResult, setAssignResult] = useState<AssignResponse | null>(null);
  const [eventValue, setEventValue] = useState("49.99");
  const [sandboxMsg, setSandboxMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!experimentId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.getResults(experimentId);
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load results");
    } finally {
      setLoading(false);
    }
  }, [experimentId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleLifecycle = async (action: "start" | "pause" | "end") => {
    try {
      await api.transitionExperiment(experimentId, action);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Action failed");
    }
  };

  const handleAssignTest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!data) return;
    setSandboxMsg(null);
    try {
      const res = await api.assignUser(
        data.experiment.key,
        testUserId.trim()
      );
      setAssignResult(res);
      await load();
    } catch (err) {
      setSandboxMsg(err instanceof Error ? err.message : "Assign error");
    }
  };

  const handleLogMetricEvent = async () => {
    if (!data) return;
    setSandboxMsg(null);
    try {
      const isConv = data.experiment.metric_type === "conversion";
      await api.logEvent({
        experiment_key: data.experiment.key,
        user_id: testUserId.trim(),
        event_type: data.experiment.metric_event,
        value: isConv ? null : Number(eventValue) || 25.0,
      });
      setSandboxMsg(
        `Logged '${data.experiment.metric_event}' for ${testUserId.trim()} and recomputed stats!`
      );
      await load();
    } catch (err) {
      setSandboxMsg(err instanceof Error ? err.message : "Event log failed");
    }
  };

  if (loading && !data) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 animate-pulse rounded bg-slate-900" />
        <div className="h-36 animate-pulse rounded-2xl bg-slate-900" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl bg-slate-900" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Experiments
        </Link>
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-6 text-sm text-rose-200">
          {error || "Experiment not found"}
        </div>
      </div>
    );
  }

  const {
    experiment: exp,
    variants,
    comparison,
    verdict,
    srm,
    progress,
    timeseries,
    warnings,
  } = data;

  const isConversion = exp.metric_type === "conversion";
  const theme = VERDICT_THEME[verdict.status];
  const VerdictIcon = theme.icon;
  const progressPct =
    progress.fraction !== null
      ? Math.min(100, Math.round(progress.fraction * 100))
      : null;

  return (
    <div className="space-y-8">
      {/* Top navigation & actions */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div className="space-y-1">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-indigo-300 transition"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            All Experiments
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              {exp.name}
            </h1>
            <code className="rounded-md border border-slate-800 bg-slate-900 px-2.5 py-0.5 font-mono text-xs text-slate-400">
              {exp.key}
            </code>
            <span className="rounded-full border border-slate-700 bg-slate-800 px-2.5 py-0.5 text-xs font-semibold capitalize text-slate-200">
              {exp.status}
            </span>
          </div>
          {exp.hypothesis && (
            <p className="text-xs text-slate-400 max-w-3xl">{exp.hypothesis}</p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={load}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-3 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
          {(exp.status === "draft" || exp.status === "paused") && (
            <button
              type="button"
              onClick={() => handleLifecycle("start")}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-emerald-500"
            >
              <Play className="h-3.5 w-3.5" />
              {exp.status === "draft" ? "Start Experiment" : "Resume"}
            </button>
          )}
          {exp.status === "running" && (
            <button
              type="button"
              onClick={() => handleLifecycle("pause")}
              className="inline-flex items-center gap-1.5 rounded-lg border border-amber-500/40 bg-amber-500/15 px-3.5 py-2 text-xs font-semibold text-amber-200 hover:bg-amber-500/25"
            >
              <Pause className="h-3.5 w-3.5" />
              Pause
            </button>
          )}
          {(exp.status === "running" || exp.status === "paused") && (
            <button
              type="button"
              onClick={() => handleLifecycle("end")}
              className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-500/40 bg-indigo-500/15 px-3.5 py-2 text-xs font-semibold text-indigo-200 hover:bg-indigo-500/25"
            >
              <Square className="h-3.5 w-3.5" />
              End Test
            </button>
          )}
        </div>
      </div>

      {/* Plain-English Verdict Banner */}
      <div
        className={`rounded-2xl border ${theme.border} ${theme.bg} p-6 shadow-lg`}
      >
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div className="flex items-start gap-4">
            <div
              className={`rounded-xl border p-3 ${theme.badge} shrink-0 mt-0.5`}
            >
              <VerdictIcon className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Statistical Verdict
                </span>
                <span
                  className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${theme.badge}`}
                >
                  {comparison?.test === "welch_t_test"
                    ? "Welch's Two-Sample T-Test"
                    : "Two-Proportion Z-Test"}
                </span>
              </div>
              <h2 className={`mt-1 text-xl font-bold ${theme.text}`}>
                {verdict.headline}
              </h2>
              <p className="mt-1 text-sm text-slate-200/90 leading-relaxed max-w-3xl">
                {verdict.detail}
              </p>
            </div>
          </div>

          {comparison && (
            <div className="flex shrink-0 items-center gap-6 rounded-xl border border-slate-800/90 bg-slate-950/75 px-5 py-3.5">
              <div>
                <div className="text-[11px] uppercase tracking-wider text-slate-400">
                  Relative Lift
                </div>
                <div
                  className={`mt-0.5 font-mono text-2xl font-bold ${
                    comparison.significant
                      ? comparison.absolute_diff > 0
                        ? "text-emerald-400"
                        : "text-rose-400"
                      : "text-white"
                  }`}
                >
                  {fmtPct(comparison.relative_lift, 1, true)}
                </div>
              </div>
              <div className="h-8 w-px bg-slate-800" />
              <div>
                <div className="text-[11px] uppercase tracking-wider text-slate-400">
                  p-value (&alpha;={exp.alpha})
                </div>
                <div className="mt-0.5 font-mono text-2xl font-bold text-white">
                  {comparison.p_value < 0.0001
                    ? "< 0.0001"
                    : comparison.p_value.toFixed(4)}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Warnings (Peeking / SRM) */}
      {warnings.length > 0 && (
        <div className="space-y-2">
          {warnings.map((w, idx) => (
            <div
              key={idx}
              className="flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-xs text-amber-200"
            >
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}

      {/* Key Stat Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="text-xs font-medium text-slate-400">
            Test Statistic
          </div>
          <div className="mt-2 font-mono text-2xl font-bold text-white">
            {comparison
              ? `${
                  comparison.test === "welch_t_test" ? "t" : "z"
                } = ${comparison.statistic.toFixed(3)}`
              : "—"}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {comparison?.df
              ? `Welch–Satterthwaite df = ${comparison.df.toFixed(1)}`
              : "Pooled SE under H₀"}
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="text-xs font-medium text-slate-400">
            Absolute Difference (T - C)
          </div>
          <div className="mt-2 font-mono text-2xl font-bold text-white">
            {comparison
              ? isConversion
                ? `${(comparison.absolute_diff * 100).toFixed(2)} pp`
                : `$${comparison.absolute_diff.toFixed(2)}`
              : "—"}
          </div>
          <div className="mt-1 font-mono text-xs text-slate-400">
            {comparison
              ? `${Math.round((1 - exp.alpha) * 100)}% CI [${
                  isConversion
                    ? `${(comparison.ci_diff.low * 100).toFixed(2)}, ${(
                        comparison.ci_diff.high * 100
                      ).toFixed(2)} pp`
                    : `$${comparison.ci_diff.low.toFixed(
                        2
                      )}, $${comparison.ci_diff.high.toFixed(2)}`
                }]`
              : "Waiting for observations"}
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between text-xs font-medium text-slate-400">
            <span>Sample Ratio Mismatch (SRM)</span>
            <ShieldCheck
              className={`h-4 w-4 ${
                srm.mismatch ? "text-rose-400" : "text-emerald-400"
              }`}
            />
          </div>
          <div className="mt-2 font-mono text-2xl font-bold text-white">
            {srm.mismatch ? "MISMATCH" : "Healthy"}
          </div>
          <div className="mt-1 font-mono text-xs text-slate-500">
            &chi;&sup2; = {srm.chi2.toFixed(2)}, p = {srm.p_value.toFixed(3)}
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between text-xs font-medium text-slate-400">
            <span>Sample Size Progress</span>
            <span className="font-mono text-indigo-300">
              {progressPct !== null ? `${progressPct}%` : "—"}
            </span>
          </div>
          <div className="mt-2 font-mono text-lg font-bold text-white">
            {progress.smallest_variant.toLocaleString()}{" "}
            <span className="text-xs font-normal text-slate-400">
              /{" "}
              {progress.required_per_variant
                ? `${progress.required_per_variant.toLocaleString()} per arm`
                : "estimating..."}
            </span>
          </div>
          <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-950">
            <div
              className="h-full rounded-full bg-indigo-500 transition-all"
              style={{ width: `${progressPct ?? 5}%` }}
            />
          </div>
        </div>
      </div>

      {/* Variant Comparison & Forest Plot */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Variant breakdown table + visual bars */}
        <div className="lg:col-span-7 rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-5">
          <div>
            <h3 className="text-base font-semibold text-white">
              Variant Performance &amp; {Math.round((1 - exp.alpha) * 100)}% Confidence Intervals
            </h3>
            <p className="text-xs text-slate-400">
              {isConversion
                ? "Wilson score intervals per variant (behaves accurately even for small n or extreme rates)."
                : "Student's t confidence intervals around sample mean per assigned user."}
            </p>
          </div>

          <VariantComparisonChart
            variants={variants}
            isConversion={isConversion}
          />

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="pb-2 font-medium">Variant</th>
                  <th className="pb-2 font-medium text-right">Traffic Split</th>
                  <th className="pb-2 font-medium text-right">Users</th>
                  <th className="pb-2 font-medium text-right">Events</th>
                  <th className="pb-2 font-medium text-right">
                    {isConversion ? "Conv. Rate" : "Mean / User"}
                  </th>
                  <th className="pb-2 font-medium text-right">
                    {Math.round((1 - exp.alpha) * 100)}% CI
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70 font-mono">
                {variants.map((v) => {
                  const val = isConversion ? v.rate : v.mean;
                  const ci = isConversion ? v.rate_ci : v.mean_ci;
                  return (
                    <tr key={v.variant_id} className="text-slate-200">
                      <td className="py-3 font-sans">
                        <span className="font-semibold text-white">
                          {v.name}
                        </span>
                        {v.is_control && (
                          <span className="ml-2 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
                            Baseline
                          </span>
                        )}
                      </td>
                      <td className="py-3 text-right">
                        {Math.round(v.weight * 100)}%
                      </td>
                      <td className="py-3 text-right">
                        {v.users.toLocaleString()}
                      </td>
                      <td className="py-3 text-right">
                        {(v.conversions ?? 0).toLocaleString()}
                      </td>
                      <td className="py-3 text-right font-bold text-white">
                        {fmtMetric(val, isConversion)}
                      </td>
                      <td className="py-3 text-right text-slate-400">
                        {ci
                          ? `[${fmtMetric(ci.low, isConversion)}, ${fmtMetric(
                              ci.high,
                              isConversion
                            )}]`
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Relative Lift CI Forest Plot */}
        <div className="lg:col-span-5 rounded-2xl border border-slate-800 bg-slate-900/60 p-6 flex flex-col justify-between space-y-4">
          <div>
            <h3 className="text-base font-semibold text-white">
              Treatment Effect &amp; Confidence Interval
            </h3>
            <p className="text-xs text-slate-400">
              A result is statistically significant at &alpha;={exp.alpha} when the{" "}
              {Math.round((1 - exp.alpha) * 100)}% confidence interval does not cross 0%.
            </p>
          </div>

          {comparison && comparison.ci_relative_lift ? (
            <LiftForestPlot
              lift={comparison.relative_lift ?? 0}
              low={comparison.ci_relative_lift.low}
              high={comparison.ci_relative_lift.high}
              mde={exp.mde}
              significant={comparison.significant}
            />
          ) : (
            <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-slate-800 text-xs text-slate-500">
              Collect conversions in both variants to plot relative lift CI.
            </div>
          )}

          <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-3.5 text-xs text-slate-400 space-y-1">
            <div className="font-semibold text-slate-200">
              How to read this interval
            </div>
            <p>
              The dot is the observed relative lift; the horizontal bar spans plausible true effects. Dashed lines mark your pre-registered{" "}
              <span className="text-indigo-300 font-mono">
                &plusmn;{(exp.mde * 100).toFixed(0)}%
              </span>{" "}
              Minimum Detectable Effect.
            </p>
          </div>
        </div>
      </div>

      {/* Cumulative Time-Series & Peeking Trajectory */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
        <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
          <div>
            <h3 className="text-base font-semibold text-white">
              Cumulative Metric &amp; p-Value Trajectory Over Time
            </h3>
            <p className="text-xs text-slate-400">
              Shows how variant performance and the two-sided p-value evolved as users entered the experiment—illustrating why early &ldquo;peeking&rdquo; can catch noisy fluctuations.
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <span className="inline-flex items-center gap-1.5 text-slate-300">
              <span className="h-2.5 w-2.5 rounded-full bg-slate-400" />
              Control
            </span>
            <span className="inline-flex items-center gap-1.5 text-indigo-300">
              <span className="h-2.5 w-2.5 rounded-full bg-indigo-400" />
              Treatment
            </span>
            <span className="inline-flex items-center gap-1.5 text-amber-300">
              <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
              p-value
            </span>
          </div>
        </div>

        <TimeSeriesChart
          points={timeseries}
          isConversion={isConversion}
          alpha={exp.alpha}
        />
      </div>

      {/* Live Deterministic Assignment & Event Sandbox */}
      <div className="rounded-2xl border border-indigo-500/30 bg-slate-900/70 p-6 space-y-4">
        <div className="flex items-center gap-2">
          <Hash className="h-5 w-5 text-indigo-400" />
          <div>
            <h3 className="text-base font-semibold text-white">
              Live Assignment &amp; Event Ingestion Sandbox
            </h3>
            <p className="text-xs text-slate-400">
              Test deterministic SHA-256 hashing (<code className="text-indigo-300">POST /api/v1/assign</code>) and event logging (<code className="text-indigo-300">POST /api/v1/events</code>) for{" "}
              <code className="text-slate-200">{exp.key}</code>. Calling assign repeatedly with the same user ID always returns the same variant.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 items-end">
          <form
            onSubmit={handleAssignTest}
            className="lg:col-span-5 flex items-end gap-2"
          >
            <div className="flex-1">
              <label className="block text-xs font-medium text-slate-300">
                User ID
              </label>
              <input
                type="text"
                required
                value={testUserId}
                onChange={(e) => setTestUserId(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm text-white"
              />
            </div>
            <button
              type="submit"
              className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 h-[38px]"
            >
              1. Assign Variant
            </button>
          </form>

          <div className="lg:col-span-4 flex items-end gap-2">
            {!isConversion && (
              <div className="w-28">
                <label className="block text-xs font-medium text-slate-300">
                  Value ($)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={eventValue}
                  onChange={(e) => setEventValue(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-2 font-mono text-sm text-white"
                />
              </div>
            )}
            <button
              type="button"
              onClick={handleLogMetricEvent}
              className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/15 px-4 py-2 text-xs font-semibold text-emerald-200 hover:bg-emerald-500/25 h-[38px]"
            >
              <Send className="h-3.5 w-3.5" />
              2. Log &lsquo;{exp.metric_event}&rsquo; Event
            </button>
          </div>

          <div className="lg:col-span-3">
            {assignResult && (
              <div className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs font-mono">
                <span className="text-slate-400">Variant:</span>{" "}
                <span className="font-bold text-indigo-300">
                  {assignResult.variant}
                </span>{" "}
                <span className="text-slate-500">({assignResult.reason})</span>
              </div>
            )}
          </div>
        </div>

        {sandboxMsg && (
          <div className="rounded-lg border border-slate-800 bg-slate-950/90 px-3 py-2 text-xs text-indigo-300">
            {sandboxMsg}
          </div>
        )}
      </div>
    </div>
  );
}

function VariantComparisonChart({
  variants,
  isConversion,
}: {
  variants: VariantResult[];
  isConversion: boolean;
}) {
  const values = variants.map((v) => {
    const point = isConversion ? v.rate ?? 0 : v.mean ?? 0;
    const ci = isConversion ? v.rate_ci : v.mean_ci;
    return {
      ...v,
      point,
      low: ci?.low ?? point,
      high: ci?.high ?? point,
    };
  });

  const maxVal = Math.max(...values.map((v) => v.high), 0.0001) * 1.15;

  return (
    <div className="space-y-4 rounded-xl border border-slate-800/80 bg-slate-950/60 p-4">
      {values.map((v) => {
        const barPct = Math.min(100, Math.max(1, (v.point / maxVal) * 100));
        const lowPct = Math.min(100, Math.max(0, (v.low / maxVal) * 100));
        const highPct = Math.min(100, Math.max(0, (v.high / maxVal) * 100));

        return (
          <div key={v.variant_id} className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-slate-200">
                {v.name}{" "}
                <span className="text-slate-500 font-normal">
                  ({v.users.toLocaleString()} users)
                </span>
              </span>
              <span className="font-mono font-bold text-white">
                {fmtMetric(v.point, isConversion)}
              </span>
            </div>
            <div className="relative h-7 w-full rounded-lg bg-slate-900 overflow-hidden">
              <div
                className={`h-full rounded-lg transition-all ${
                  v.is_control ? "bg-slate-600/80" : "bg-indigo-500/80"
                }`}
                style={{ width: `${barPct}%` }}
              />
              {/* Whisker for 95% CI */}
              {v.users > 1 && (
                <div
                  className="absolute top-1/2 -translate-y-1/2 h-0.5 bg-white/90"
                  style={{
                    left: `${lowPct}%`,
                    width: `${Math.max(0.5, highPct - lowPct)}%`,
                  }}
                >
                  <div className="absolute -left-0.5 -top-1.5 h-3.5 w-0.5 bg-white" />
                  <div className="absolute -right-0.5 -top-1.5 h-3.5 w-0.5 bg-white" />
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function LiftForestPlot({
  lift,
  low,
  high,
  mde,
  significant,
}: {
  lift: number;
  low: number;
  high: number;
  mde: number;
  significant: boolean;
}) {
  const bound = Math.max(Math.abs(low), Math.abs(high), mde * 1.4, 0.05) * 1.25;
  const toX = (val: number) => ((val + bound) / (2 * bound)) * 100;

  const zeroX = toX(0);
  const lowX = toX(low);
  const highX = toX(high);
  const pointX = toX(lift);
  const mdePos = toX(mde);
  const mdeNeg = toX(-mde);

  const color = !significant
    ? "#94a3b8"
    : lift > 0
    ? "#34d399"
    : "#fb7185";

  return (
    <div className="rounded-xl border border-slate-800/90 bg-slate-950/70 p-4">
      <svg viewBox="0 0 400 110" className="w-full h-32 overflow-visible">
        {/* Negative & Positive MDE reference lines */}
        <line
          x1={mdeNeg * 4}
          y1={12}
          x2={mdeNeg * 4}
          y2={82}
          stroke="#475569"
          strokeDasharray="3 3"
          strokeWidth={1}
        />
        <line
          x1={mdePos * 4}
          y1={12}
          x2={mdePos * 4}
          y2={82}
          stroke="#475569"
          strokeDasharray="3 3"
          strokeWidth={1}
        />
        {/* Zero line */}
        <line
          x1={zeroX * 4}
          y1={8}
          x2={zeroX * 4}
          y2={86}
          stroke="#e2e8f0"
          strokeWidth={1.5}
        />
        <text
          x={zeroX * 4}
          y={100}
          textAnchor="middle"
          className="fill-slate-300 text-[10px] font-mono"
        >
          0%
        </text>
        <text
          x={mdePos * 4}
          y={100}
          textAnchor="middle"
          className="fill-slate-500 text-[9px] font-mono"
        >
          +{(mde * 100).toFixed(0)}% MDE
        </text>
        <text
          x={mdeNeg * 4}
          y={100}
          textAnchor="middle"
          className="fill-slate-500 text-[9px] font-mono"
        >
          -{(mde * 100).toFixed(0)}%
        </text>

        {/* CI horizontal bar */}
        <line
          x1={lowX * 4}
          y1={48}
          x2={highX * 4}
          y2={48}
          stroke={color}
          strokeWidth={4}
          strokeLinecap="round"
        />
        <line
          x1={lowX * 4}
          y1={38}
          x2={lowX * 4}
          y2={58}
          stroke={color}
          strokeWidth={2.5}
        />
        <line
          x1={highX * 4}
          y1={38}
          x2={highX * 4}
          y2={58}
          stroke={color}
          strokeWidth={2.5}
        />
        {/* Point estimate */}
        <circle cx={pointX * 4} cy={48} r={6} fill={color} />
        <text
          x={pointX * 4}
          y={28}
          textAnchor="middle"
          className="fill-white text-[11px] font-mono font-bold"
        >
          {fmtPct(lift, 1, true)} [{fmtPct(low, 1, true)}, {fmtPct(high, 1, true)}]
        </text>
      </svg>
    </div>
  );
}

function TimeSeriesChart({
  points,
  isConversion,
  alpha,
}: {
  points: TimePoint[];
  isConversion: boolean;
  alpha: number;
}) {
  if (!points || points.length < 2) {
    return (
      <div className="flex h-44 items-center justify-center rounded-xl border border-dashed border-slate-800 text-xs text-slate-500">
        Not enough timestamped data points yet to render cumulative time series.
      </div>
    );
  }

  const w = 760;
  const h = 190;
  const padX = 44;
  const padY = 20;

  const metricVals: number[] = [];
  points.forEach((p) => {
    if (p.control !== null) metricVals.push(p.control);
    if (p.treatment !== null) metricVals.push(p.treatment);
  });

  const minM = metricVals.length ? Math.min(...metricVals) * 0.9 : 0;
  const maxM = metricVals.length ? Math.max(...metricVals) * 1.1 || 0.1 : 1;

  const toX = (i: number) =>
    padX + (i / (points.length - 1)) * (w - padX * 2);
  const toMetricY = (v: number) =>
    h - padY - ((v - minM) / (maxM - minM || 1)) * (h - padY * 2);
  const toPvalY = (p: number) =>
    h - padY - Math.min(1, Math.max(0, p)) * (h - padY * 2);

  const buildPath = (getter: (pt: TimePoint) => number | null, yFn: (v: number) => number) => {
    const coords: string[] = [];
    points.forEach((pt, i) => {
      const v = getter(pt);
      if (v !== null && !Number.isNaN(v)) {
        coords.push(`${coords.length === 0 ? "M" : "L"}${toX(i).toFixed(1)},${yFn(v).toFixed(1)}`);
      }
    });
    return coords.join(" ");
  };

  const controlPath = buildPath((p) => p.control, toMetricY);
  const treatmentPath = buildPath((p) => p.treatment, toMetricY);
  const pvalPath = buildPath((p) => p.p_value, toPvalY);
  const alphaY = toPvalY(alpha);

  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-4">
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-52 overflow-visible">
        {/* Alpha significance threshold line */}
        <line
          x1={padX}
          y1={alphaY}
          x2={w - padX}
          y2={alphaY}
          stroke="#f59e0b"
          strokeDasharray="4 4"
          strokeOpacity={0.45}
          strokeWidth={1}
        />
        <text
          x={w - padX - 4}
          y={alphaY - 4}
          textAnchor="end"
          className="fill-amber-400/80 text-[9px] font-mono"
        >
          p = &alpha; ({alpha})
        </text>

        {/* P-value line */}
        {pvalPath && (
          <path
            d={pvalPath}
            fill="none"
            stroke="#fbbf24"
            strokeWidth={1.5}
            strokeOpacity={0.55}
          />
        )}

        {/* Control & Treatment cumulative metric lines */}
        {controlPath && (
          <path
            d={controlPath}
            fill="none"
            stroke="#94a3b8"
            strokeWidth={2.2}
          />
        )}
        {treatmentPath && (
          <path
            d={treatmentPath}
            fill="none"
            stroke="#818cf8"
            strokeWidth={2.5}
          />
        )}

        {/* Y axis labels */}
        <text
          x={padX - 6}
          y={padY + 4}
          textAnchor="end"
          className="fill-slate-400 text-[9px] font-mono"
        >
          {fmtMetric(maxM, isConversion)}
        </text>
        <text
          x={padX - 6}
          y={h - padY}
          textAnchor="end"
          className="fill-slate-400 text-[9px] font-mono"
        >
          {fmtMetric(minM, isConversion)}
        </text>
      </svg>
    </div>
  );
}
