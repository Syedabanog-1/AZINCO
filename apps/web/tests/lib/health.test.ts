import { describe, expect, it } from "vitest";
import { apiBaseUrl, fetchSystemStatus } from "@/lib/api/health";

const NOW = () => new Date("2026-01-01T00:00:00.000Z");
const HEALTH = {
  status: "ok",
  service: "azinco-api",
  version: "0.1.0",
  environment: "local",
  base_currency: "PKR",
  reporting_currencies: ["PKR", "USD"],
};
const READY = {
  status: "ready",
  components: [
    { name: "postgres", status: "ok", latency_ms: 3.2, detail: null },
    { name: "redis", status: "ok", latency_ms: 1.1, detail: null },
  ],
};

function fakeFetch(routes: Record<string, { status: number; body: unknown } | Error>): typeof fetch {
  return (async (input: RequestInfo | URL) => {
    const url = String(input);
    const path = new URL(url).pathname;
    const route = routes[path];
    if (route === undefined) throw new Error(`unexpected ${url}`);
    if (route instanceof Error) throw route;
    return new Response(JSON.stringify(route.body), { status: route.status });
  }) as typeof fetch;
}

describe("apiBaseUrl", () => {
  it("defaults to localhost and strips trailing slashes", () => {
    expect(apiBaseUrl({})).toBe("http://localhost:8000");
    expect(apiBaseUrl({ AZINCO_API_INTERNAL_URL: "http://api:8000///" })).toBe("http://api:8000");
  });
});

describe("fetchSystemStatus", () => {
  it("returns up + ready when both endpoints are healthy", async () => {
    const f = fakeFetch({ "/health": { status: 200, body: HEALTH }, "/ready": { status: 200, body: READY } });
    const s = await fetchSystemStatus(f, "http://api:8000", NOW);
    expect(s.api).toBe("up");
    if (s.api === "up") {
      expect(s.readiness.status).toBe("ready");
      expect(s.health.version).toBe("0.1.0");
      expect(s.checkedAt).toBe("2026-01-01T00:00:00.000Z");
    }
  });

  it("parses a 503 readiness body as not_ready instead of failing", async () => {
    const notReady = {
      status: "not_ready",
      components: [{ name: "redis", status: "fail", latency_ms: 5, detail: "ConnectionError" }],
    };
    const f = fakeFetch({ "/health": { status: 200, body: HEALTH }, "/ready": { status: 503, body: notReady } });
    const s = await fetchSystemStatus(f, "http://api:8000", NOW);
    expect(s.api === "up" && s.readiness.status).toBe("not_ready");
  });

  it("reports down with a safe message when the API is unreachable", async () => {
    const f = fakeFetch({ "/health": new TypeError("fetch failed: connect ECONNREFUSED 10.0.0.5:8000") , "/ready": { status: 200, body: READY } });
    const s = await fetchSystemStatus(f, "http://api:8000", NOW);
    expect(s).toEqual({ api: "down", error: "The API is not reachable.", checkedAt: "2026-01-01T00:00:00.000Z" });
  });

  it("reports down when the API returns an unexpected shape", async () => {
    const f = fakeFetch({ "/health": { status: 200, body: { hello: "world" } }, "/ready": { status: 200, body: READY } });
    const s = await fetchSystemStatus(f, "http://api:8000", NOW);
    expect(s.api).toBe("down");
  });

  it("reports down on a 500 from the API", async () => {
    const f = fakeFetch({ "/health": { status: 500, body: {} }, "/ready": { status: 200, body: READY } });
    expect((await fetchSystemStatus(f, "http://api:8000", NOW)).api).toBe("down");
  });
});
