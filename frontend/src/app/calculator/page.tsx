"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Calculator, Clock, Users, Target, Info } from "lucide-react";
import {
  api,
  MetricType,
  SampleSizeResponse,
} from "@/lib/api";

export default function CalculatorPage() {
  const [metricType, setMetricType] = useState<MetricType>("conversion");
  const [baselinePct, setBaselinePct] = useState(5.0);
  const [baselineMean, setBaselineMean] = useState(45.0);
  const [stdDev, setStdDev] = useState(30.0);
  const [mdePct, setMdePct] = useState(10.0);
  const [mdeType, setMdeType] = useState<"relative" | "absolute">("relative");
  const [alpha, setAlpha] = useState(0.05);
  const [power, setPower] = useState(0.8);
  const [dailyTraffic, setDailyTraffic] = useState(2500);

  const [result, setResult] = useState<SampleSizeResponse | null>(null);
  const [curve, setCurve] = useState<{ mde: number; n: number }[]>([]);
  const [error, setError] = useState<string | null>(null);

  const compute = useCallback(async () => {
    setError(null);
    try {
      const baseline =
        metricType === "conversion" ? baselinePct / 100 : baselineMean;
      const mde =
        mdeType === "relative"
          ? mdePct / 100
          : metricType === "conversion"
          ? mdePct / 100
          : mdePct;

      const res = await api.calculateSampleSize({
        metric_type: metricType,
        baseline,
        std_dev: metricType === "continuous" ? stdDev : undefined,
        mde,
        mde_type: mdeType,
        alpha,
        power,
        daily_traffic: dailyTraffic > 0 ? dailyTraffic : undefined,
      });
      setResult(res);

      // Compute MDE sensitivity curve across relative lifts
      const mdeGrid = [3, 5, 7.5, 10, 12.5, 15, 20, 25, 30];
      const pts = await Promise.all(
        mdeGrid.map(async (m) => {
          const r = await api.calculateSampleSize({
            metric_type: metricType,
            baseline,
            std_dev: metricType === "continuous" ? stdDev : undefined,
            mde: m / 100,
            mde_type: "relative",
            alpha,
            power,
          });
          return { mde: m, n: r.per_variant };
        })
      );
      setCurve(pts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Calculation error");
    }
  }, [
    metricType,
    baselinePct,
    baselineMean,
    stdDev,
    mdePct,
    mdeType,
    alpha,
    power,
    dailyTraffic,
  ]);

  useEffect(() => {
    compute();
  }, [compute]);

  const maxN = curve.length ? Math.max(...curve.map((c) => c.n)) : 1;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          Sample-Size &amp; Power Calculator
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Compute how many users per variant you need before launching an experiment—preventing underpowered tests and mid-test peeking.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        {/* Controls Column */}
        <div className="lg:col-span-5 space-y-5 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <Calculator className="h-4 w-4 text-indigo-400" />
            Design Parameters
          </div>

          {/* Metric type toggle */}
          <div className="grid grid-cols-2 gap-2 rounded-xl bg-slate-950 p-1 border border-slate-800">
            <button
              type="button"
              onClick={() => {
                setMetricType("conversion");
                setMdeType("relative");
                setMdePct(10);
              }}
              className={`rounded-lg py-2 text-xs font-semibold transition ${
                metricType === "conversion"
                  ? "bg-indigo-600 text-white"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Conversion (Proportion)
            </button>
            <button
              type="button"
              onClick={() => {
                setMetricType("continuous");
                setMdeType("relative");
                setMdePct(10);
              }}
              className={`rounded-lg py-2 text-xs font-semibold transition ${
                metricType === "continuous"
                  ? "bg-indigo-600 text-white"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Continuous (Revenue)
            </button>
          </div>

          {metricType === "conversion" ? (
            <div>
              <div className="flex justify-between text-xs">
                <label className="font-medium text-slate-300">
                  Baseline Conversion Rate (Control)
                </label>
                <span className="font-mono font-semibold text-indigo-300">
                  {baselinePct.toFixed(1)}%
                </span>
              </div>
              <input
                type="range"
                min={0.5}
                max={50}
                step={0.5}
                value={baselinePct}
                onChange={(e) => setBaselinePct(Number(e.target.value))}
                className="mt-2 w-full accent-indigo-500"
              />
              <div className="mt-1 flex justify-between text-[11px] text-slate-500">
                <span>0.5%</span>
                <span>25%</span>
                <span>50%</span>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-300">
                  Baseline Mean ($)
                </label>
                <input
                  type="number"
                  min={0.1}
                  step={1}
                  value={baselineMean}
                  onChange={(e) => setBaselineMean(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-300">
                  Std Deviation (&sigma;)
                </label>
                <input
                  type="number"
                  min={0.1}
                  step={1}
                  value={stdDev}
                  onChange={(e) => setStdDev(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
                />
              </div>
            </div>
          )}

          {/* MDE */}
          <div>
            <div className="flex items-center justify-between text-xs">
              <label className="font-medium text-slate-300">
                Minimum Detectable Effect (MDE)
              </label>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setMdeType("relative")}
                  className={`rounded px-2 py-0.5 text-[11px] font-medium ${
                    mdeType === "relative"
                      ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                      : "text-slate-500"
                  }`}
                >
                  Relative %
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setMdeType("absolute");
                    if (metricType === "conversion") setMdePct(1.0);
                  }}
                  className={`rounded px-2 py-0.5 text-[11px] font-medium ${
                    mdeType === "absolute"
                      ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                      : "text-slate-500"
                  }`}
                >
                  Absolute
                </button>
              </div>
            </div>
            <div className="mt-2 flex items-center gap-3">
              <input
                type="range"
                min={mdeType === "relative" ? 2 : 0.2}
                max={mdeType === "relative" ? 50 : 15}
                step={mdeType === "relative" ? 1 : 0.2}
                value={mdePct}
                onChange={(e) => setMdePct(Number(e.target.value))}
                className="flex-1 accent-indigo-500"
              />
              <span className="w-16 text-right font-mono text-sm font-bold text-indigo-300">
                {mdePct}
                {mdeType === "relative" || metricType === "conversion"
                  ? "%"
                  : ""}
              </span>
            </div>
          </div>

          {/* Alpha and Power */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300">
                False Positive Rate (&alpha;)
              </label>
              <select
                value={alpha}
                onChange={(e) => setAlpha(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
              >
                <option value={0.01}>1% (99% confidence)</option>
                <option value={0.05}>5% (95% confidence)</option>
                <option value={0.1}>10% (90% confidence)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300">
                Statistical Power (1 - &beta;)
              </label>
              <select
                value={power}
                onChange={(e) => setPower(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white"
              >
                <option value={0.8}>80% (standard)</option>
                <option value={0.9}>90% (high power)</option>
                <option value={0.95}>95% (strict)</option>
              </select>
            </div>
          </div>

          {/* Daily traffic */}
          <div>
            <label className="block text-xs font-medium text-slate-300">
              Expected Daily Users Entering Test
            </label>
            <input
              type="number"
              min={100}
              step={500}
              value={dailyTraffic}
              onChange={(e) => setDailyTraffic(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm text-white"
            />
          </div>

          {error && (
            <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-xs text-rose-300">
              {error}
            </div>
          )}
        </div>

        {/* Output & Sensitivity Chart Column */}
        <div className="lg:col-span-7 space-y-6">
          {result && (
            <>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="rounded-2xl border border-indigo-500/30 bg-indigo-500/10 p-5">
                  <div className="flex items-center justify-between text-xs font-medium text-indigo-300">
                    <span>Per Variant (n)</span>
                    <Users className="h-4 w-4" />
                  </div>
                  <p className="mt-2 font-mono text-3xl font-bold text-white">
                    {result.per_variant.toLocaleString()}
                  </p>
                  <p className="mt-1 text-xs text-indigo-200/70">
                    Users needed in Control &amp; Treatment
                  </p>
                </div>

                <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
                  <div className="flex items-center justify-between text-xs font-medium text-slate-400">
                    <span>Total Sample (2n)</span>
                    <Target className="h-4 w-4 text-emerald-400" />
                  </div>
                  <p className="mt-2 font-mono text-3xl font-bold text-white">
                    {result.total.toLocaleString()}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    Detects{" "}
                    {metricType === "conversion"
                      ? `${(result.baseline * 100).toFixed(2)}% → ${(
                          result.target * 100
                        ).toFixed(2)}%`
                      : `$${result.baseline.toFixed(2)} → $${result.target.toFixed(
                          2
                        )}`}
                  </p>
                </div>

                <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
                  <div className="flex items-center justify-between text-xs font-medium text-slate-400">
                    <span>Estimated Duration</span>
                    <Clock className="h-4 w-4 text-amber-400" />
                  </div>
                  <p className="mt-2 font-mono text-3xl font-bold text-white">
                    {result.estimated_days !== null
                      ? `${result.estimated_days}d`
                      : "—"}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    At {dailyTraffic.toLocaleString()} users/day
                  </p>
                </div>
              </div>

              {/* Sensitivity Chart */}
              <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-white">
                      Sample Size vs. Relative MDE Sensitivity
                    </h3>
                    <p className="text-xs text-slate-400">
                      Sample size scales inversely with the square of the effect size ($n \propto 1/\Delta^2$). Halving the MDE quadruples required traffic.
                    </p>
                  </div>
                </div>

                <div className="mt-6 space-y-2.5">
                  {curve.map((pt) => {
                    const widthPct = Math.max(
                      4,
                      Math.min(100, (pt.n / maxN) * 100)
                    );
                    const isSelected =
                      mdeType === "relative" && Math.abs(pt.mde - mdePct) < 1.2;
                    return (
                      <div
                        key={pt.mde}
                        className="grid grid-cols-12 items-center gap-3 text-xs"
                      >
                        <div className="col-span-2 font-mono text-right text-slate-300">
                          {pt.mde}% lift
                        </div>
                        <div className="col-span-7 h-5 rounded-md bg-slate-950 p-0.5 border border-slate-800/80">
                          <div
                            className={`h-full rounded transition-all ${
                              isSelected
                                ? "bg-indigo-500"
                                : "bg-slate-700/80"
                            }`}
                            style={{ width: `${widthPct}%` }}
                          />
                        </div>
                        <div className="col-span-3 font-mono text-slate-300">
                          {pt.n.toLocaleString()} / arm
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Formula callout */}
              <div className="flex items-start gap-3 rounded-xl border border-slate-800/80 bg-slate-900/40 p-4 text-xs text-slate-400">
                <Info className="h-4 w-4 shrink-0 text-indigo-400 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-medium text-slate-200">
                    Statistical Methodology
                  </p>
                  {metricType === "conversion" ? (
                    <p>
                      Uses the Fleiss two-proportion formula without continuity
                      correction: combines the pooled variance under $H_0$ ($p_1 = p_2$) with the unpooled variance under $H_1$, matching{" "}
                      <code className="text-indigo-300">
                        scipy.stats
                      </code>{" "}
                      and{" "}
                      <code className="text-indigo-300">
                        statsmodels
                      </code>
                      .
                    </p>
                  ) : (
                    <p>
                      Uses the two-sample normal/Welch approximation{" "}
                      <code className="text-indigo-300">
                        n = 2 &middot; (z_(1-&alpha;/2) + z_(1-&beta;))&sup2; &middot; &sigma;&sup2; / &Delta;&sup2;
                      </code>
                      , verified against the exact non-central $t$ distribution in{" "}
                      <code className="text-indigo-300">scipy.stats.nct</code>.
                    </p>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
