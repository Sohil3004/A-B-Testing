export type MetricType = "conversion" | "continuous";
export type ExperimentStatus = "draft" | "running" | "paused" | "completed";

export interface Variant {
  id: number;
  key: string;
  name: string;
  weight: number;
  is_control: boolean;
}

export interface Experiment {
  id: number;
  key: string;
  name: string;
  description: string;
  hypothesis: string;
  metric_type: MetricType;
  metric_event: string;
  traffic_allocation: number;
  alpha: number;
  power: number;
  mde: number;
  status: ExperimentStatus;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  ended_at: string | null;
  variants: Variant[];
  users: number;
}

export interface Interval {
  low: number;
  high: number;
}

export interface VariantResult {
  variant_id: number;
  key: string;
  name: string;
  is_control: boolean;
  weight: number;
  users: number;
  conversions: number | null;
  rate: number | null;
  rate_ci: Interval | null;
  mean: number | null;
  std: number | null;
  mean_ci: Interval | null;
}

export interface ComparisonResult {
  test: "two_proportion_z_test" | "welch_t_test";
  statistic: number;
  df: number | null;
  p_value: number;
  alpha: number;
  significant: boolean;
  absolute_diff: number;
  relative_lift: number | null;
  ci_diff: Interval;
  ci_relative_lift: Interval | null;
}

export interface Verdict {
  status:
    | "not_enough_data"
    | "significant_positive"
    | "significant_negative"
    | "no_significant_difference";
  headline: string;
  detail: string;
}

export interface SRMOut {
  chi2: number;
  p_value: number;
  expected: number[];
  observed: number[];
  mismatch: boolean;
}

export interface Progress {
  required_per_variant: number | null;
  smallest_variant: number;
  fraction: number | null;
}

export interface TimePoint {
  t: string;
  control: number | null;
  treatment: number | null;
  p_value: number | null;
}

export interface ResultsOut {
  experiment: Experiment;
  variants: VariantResult[];
  comparison: ComparisonResult | null;
  verdict: Verdict;
  srm: SRMOut;
  progress: Progress;
  timeseries: TimePoint[];
  warnings: string[];
  computed_at: string;
}

export interface SampleSizeRequest {
  metric_type: MetricType;
  baseline: number;
  std_dev?: number | null;
  mde: number;
  mde_type: "relative" | "absolute";
  alpha: number;
  power: number;
  daily_traffic?: number | null;
}

export interface SampleSizeResponse {
  per_variant: number;
  total: number;
  baseline: number;
  target: number;
  absolute_effect: number;
  alpha: number;
  power: number;
  estimated_days: number | null;
}

export interface AssignResponse {
  experiment_key: string;
  user_id: string;
  variant: string | null;
  in_experiment: boolean;
  reason: "assigned" | "existing" | "not_in_allocation" | "experiment_not_running";
}

export interface ExperimentCreateInput {
  name: string;
  key?: string;
  description?: string;
  hypothesis?: string;
  metric_type: MetricType;
  metric_event: string;
  traffic_allocation: number;
  alpha: number;
  power: number;
  mde: number;
  variants: {
    key: string;
    name: string;
    weight: number;
    is_control: boolean;
  }[];
}

const DEFAULT_API_KEY =
  process.env.NEXT_PUBLIC_API_KEY || "dev-secret-key";

export function getApiConfig() {
  if (typeof window === "undefined") {
    // Server-side: use the Vercel Service Binding (BACKEND_URL) injected at runtime
    const serverBase =
      process.env.BACKEND_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://localhost:8000";
    return { baseUrl: serverBase, apiKey: DEFAULT_API_KEY };
  }
  // Client-side: default to same-origin (routed via top-level /api/(.*) rewrite)
  const fallbackUrl = process.env.NEXT_PUBLIC_API_URL || "";
  return {
    baseUrl: localStorage.getItem("experimentiq_api_url") ?? fallbackUrl,
    apiKey: localStorage.getItem("experimentiq_api_key") || DEFAULT_API_KEY,
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { baseUrl, apiKey } = getApiConfig();
  const cleanBase = baseUrl.replace(/\/$/, "");
  const url = cleanBase
    ? new URL(`/api/v1${path}`, cleanBase).toString()
    : `/api/v1${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      detail =
        typeof err.detail === "string"
          ? err.detail
          : JSON.stringify(err.detail || err);
    } catch {
      // ignore json parse failure
    }
    throw new Error(detail);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json();
}

export const api = {
  listExperiments: (status?: ExperimentStatus) =>
    request<Experiment[]>(status ? `/experiments?status=${status}` : "/experiments"),
  getExperiment: (id: number) => request<Experiment>(`/experiments/${id}`),
  createExperiment: (payload: ExperimentCreateInput) =>
    request<Experiment>("/experiments", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  transitionExperiment: (id: number, action: "start" | "pause" | "end") =>
    request<Experiment>(`/experiments/${id}/${action}`, { method: "POST" }),
  deleteExperiment: (id: number) =>
    request<void>(`/experiments/${id}`, { method: "DELETE" }),
  getResults: (id: number) => request<ResultsOut>(`/experiments/${id}/results`),
  calculateSampleSize: (payload: SampleSizeRequest) =>
    request<SampleSizeResponse>("/stats/sample-size", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  assignUser: (experiment_key: string, user_id: string) =>
    request<AssignResponse>("/assign", {
      method: "POST",
      body: JSON.stringify({ experiment_key, user_id }),
    }),
  logEvent: (payload: {
    experiment_key: string;
    user_id: string;
    event_type: string;
    value?: number | null;
  }) =>
    request<{ accepted: number; rejected: number; errors: string[] }>("/events", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
