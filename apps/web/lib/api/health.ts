import { z } from "zod";

// Contract of the AZINCO API health endpoints (services/api/azinco_api/health/router.py).
export const HealthSchema = z.object({
  status: z.literal("ok"),
  service: z.string(),
  version: z.string(),
  environment: z.string(),
  base_currency: z.string().length(3),
  reporting_currencies: z.array(z.string().length(3)),
});

export const ComponentSchema = z.object({
  name: z.string(),
  status: z.enum(["ok", "fail"]),
  latency_ms: z.number().nonnegative(),
  detail: z.string().nullable(),
});

export const ReadinessSchema = z.object({
  status: z.enum(["ready", "not_ready"]),
  components: z.array(ComponentSchema),
});

export type Health = z.infer<typeof HealthSchema>;
export type Readiness = z.infer<typeof ReadinessSchema>;

export type SystemStatus =
  | { api: "up"; health: Health; readiness: Readiness; checkedAt: string }
  | { api: "down"; error: string; checkedAt: string };

const TIMEOUT_MS = 5000;

/** Server-side base URL of the API. Never exposed to the browser. */
export function apiBaseUrl(env: Record<string, string | undefined> = process.env): string {
  return (env.AZINCO_API_INTERNAL_URL ?? "http://localhost:8000").replace(/\/+$/, "");
}

async function getJson(fetchImpl: typeof fetch, url: string): Promise<unknown> {
  const res = await fetchImpl(url, {
    cache: "no-store",
    headers: { accept: "application/json" },
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  // /ready answers 503 with a valid body when a dependency is down — still parse it.
  if (!res.ok && res.status !== 503) {
    throw new Error(`API responded ${res.status}`);
  }
  return res.json();
}

export async function fetchSystemStatus(
  fetchImpl: typeof fetch = fetch,
  baseUrl: string = apiBaseUrl(),
  now: () => Date = () => new Date(),
): Promise<SystemStatus> {
  const checkedAt = now().toISOString();
  try {
    const [healthRaw, readyRaw] = await Promise.all([
      getJson(fetchImpl, `${baseUrl}/health`),
      getJson(fetchImpl, `${baseUrl}/ready`),
    ]);
    const health = HealthSchema.safeParse(healthRaw);
    const readiness = ReadinessSchema.safeParse(readyRaw);
    if (!health.success || !readiness.success) {
      return { api: "down", error: "Unexpected response format from the API.", checkedAt };
    }
    return { api: "up", health: health.data, readiness: readiness.data, checkedAt };
  } catch (err) {
    const reason =
      err instanceof Error && err.name === "TimeoutError"
        ? "The API did not respond in time."
        : "The API is not reachable.";
    return { api: "down", error: reason, checkedAt };
  }
}

export const COMPONENT_LABELS: Record<string, string> = {
  postgres: "Database (PostgreSQL)",
  redis: "Queue & cache (Redis)",
  storage: "Document storage (S3)",
};
