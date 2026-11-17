import type { Metadata } from "next";
import { connection } from "next/server";
import { Suspense } from "react";
import { COMPONENT_LABELS, fetchSystemStatus } from "@/lib/api/health";

export const metadata: Metadata = { title: "System status" };

export default function StatusPage() {
  return (
    <section className="mx-auto max-w-4xl px-6 py-14">
      <h1 className="text-3xl font-semibold tracking-tight">System status</h1>
      <p className="mt-2 text-sm text-ink-soft">
        Live readiness of the AZINCO API and the services it depends on. Checked on every page
        load from the server; the browser never talks to internal services directly.
      </p>
      <Suspense fallback={<StatusSkeleton />}>
        <LiveStatus />
      </Suspense>
    </section>
  );
}

async function LiveStatus() {
  await connection(); // request-time only: never prerender a status snapshot
  const status = await fetchSystemStatus();

  if (status.api === "down") {
    return (
      <div className="mt-8 rounded-lg border border-fail/30 bg-fail-tint p-5" role="alert">
        <p className="font-semibold text-fail">API unavailable</p>
        <p className="mt-1 text-sm">{status.error}</p>
        <p className="mt-3 text-xs text-ink-soft">Checked at {status.checkedAt}</p>
      </div>
    );
  }

  const ready = status.readiness.status === "ready";
  return (
    <div className="mt-8 space-y-6">
      <div
        className={`flex items-center justify-between rounded-lg border p-5 ${
          ready ? "border-ok/30 bg-ok-tint" : "border-fail/30 bg-fail-tint"
        }`}
      >
        <div>
          <p className={`text-lg font-semibold ${ready ? "text-ok" : "text-fail"}`}>
            {ready ? "All systems operational" : "Degraded — a dependency is not ready"}
          </p>
          <p className="mt-1 text-xs text-ink-soft">
            {status.health.service} v{status.health.version} · environment{" "}
            <span className="font-mono">{status.health.environment}</span> · checked at{" "}
            {status.checkedAt}
          </p>
        </div>
        <StatusPill ok={ready} label={ready ? "Ready" : "Not ready"} />
      </div>

      <table className="w-full overflow-hidden rounded-lg border border-line bg-white text-sm">
        <thead className="bg-paper text-left text-xs uppercase tracking-wide text-ink-soft">
          <tr>
            <th className="px-4 py-3 font-medium">Component</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 text-right font-medium">Latency</th>
            <th className="px-4 py-3 font-medium">Detail</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          <tr>
            <td className="px-4 py-3">API service</td>
            <td className="px-4 py-3">
              <StatusPill ok label="Up" />
            </td>
            <td className="px-4 py-3 text-right font-mono text-ink-soft">—</td>
            <td className="px-4 py-3 text-ink-soft">/health</td>
          </tr>
          {status.readiness.components.map((c) => (
            <tr key={c.name}>
              <td className="px-4 py-3">{COMPONENT_LABELS[c.name] ?? c.name}</td>
              <td className="px-4 py-3">
                <StatusPill ok={c.status === "ok"} label={c.status === "ok" ? "OK" : "Fail"} />
              </td>
              <td className="px-4 py-3 text-right font-mono text-ink-soft">
                {c.latency_ms.toFixed(1)} ms
              </td>
              <td className="px-4 py-3 font-mono text-xs text-ink-soft">{c.detail ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatusPill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
        ok ? "bg-ok-tint text-ok" : "bg-fail-tint text-fail"
      }`}
    >
      <span aria-hidden className={`size-1.5 rounded-full ${ok ? "bg-ok" : "bg-fail"}`} />
      {label}
    </span>
  );
}

function StatusSkeleton() {
  return (
    <div className="mt-8 space-y-3" aria-busy="true" aria-label="Checking services">
      <div className="h-20 animate-pulse rounded-lg bg-line/60" />
      <div className="h-48 animate-pulse rounded-lg bg-line/40" />
    </div>
  );
}
