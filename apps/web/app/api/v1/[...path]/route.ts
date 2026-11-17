import type { NextRequest } from "next/server";
import { apiBaseUrl } from "@/lib/api/health";
import { isProxyAllowed } from "@/lib/api/proxy-allowlist";

/**
 * Same-origin proxy from the browser to the AZINCO API (server-side only).
 * - Keeps the session cookie first-party (SameSite=Strict, HttpOnly) on the web origin.
 * - Only allow-listed paths are forwarded; everything else is 404.
 * - Only the headers the API needs are forwarded (no arbitrary header injection).
 */
const FORWARD_REQUEST_HEADERS = ["content-type", "cookie", "x-csrf-token", "accept", "x-request-id"];
const FORWARD_RESPONSE_HEADERS = ["content-type", "x-request-id"];
const TIMEOUT_MS = 15_000;

type Ctx = { params: Promise<{ path: string[] }> };

async function forward(req: NextRequest, ctx: Ctx): Promise<Response> {
  const { path } = await ctx.params;
  const joined = path.join("/");
  if (!isProxyAllowed(joined)) {
    return Response.json(
      { type: "about:blank", title: "Not Found", status: 404, code: "not_found" },
      { status: 404, headers: { "content-type": "application/problem+json" } },
    );
  }

  const headers = new Headers();
  for (const name of FORWARD_REQUEST_HEADERS) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${apiBaseUrl()}/api/v1/${joined}${req.nextUrl.search}`, {
      method: req.method,
      headers,
      body: req.method === "GET" || req.method === "HEAD" ? undefined : await req.text(),
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch {
    return Response.json(
      { type: "about:blank", title: "Bad Gateway", status: 502, code: "api_unreachable",
        detail: "The AZINCO API is not reachable right now." },
      { status: 502, headers: { "content-type": "application/problem+json" } },
    );
  }

  const out = new Headers();
  for (const name of FORWARD_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) out.set(name, value);
  }
  for (const cookie of upstream.headers.getSetCookie()) out.append("set-cookie", cookie);
  out.set("cache-control", "no-store");
  const body = upstream.status === 204 ? null : await upstream.arrayBuffer();
  return new Response(body, { status: upstream.status, headers: out });
}

export const GET = forward;
export const POST = forward;
