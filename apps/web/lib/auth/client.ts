"use client";

// Browser-side helpers for the auth pages. Calls go to the same-origin proxy (/api/v1/...).

export type Problem = { status: number; title: string; detail?: string; code?: string };

export type Membership = {
  tenant_id: string;
  tenant_name: string;
  role: string;
  permissions: string[];
};

export type Me = {
  id: string;
  email: string;
  display_name: string;
  user_type: string;
  mfa_enabled: boolean;
  mfa_required: boolean;
  mfa_satisfied: boolean;
  memberships: Membership[];
  platform_roles: string[];
  platform_permissions: string[];
};

export type Result<T> = { ok: true; data: T } | { ok: false; problem: Problem };

function csrfToken(): string {
  const entry = document.cookie.split("; ").find((c) => c.startsWith("azinco_csrf="));
  return entry ? decodeURIComponent(entry.slice("azinco_csrf=".length)) : "";
}

export async function apiCall<T>(
  path: string,
  options: { method?: "GET" | "POST"; body?: unknown } = {},
): Promise<Result<T>> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { accept: "application/json" };
  if (method !== "GET") {
    headers["content-type"] = "application/json";
    headers["x-csrf-token"] = csrfToken();
  }
  let res: Response;
  try {
    res = await fetch(`/api/v1/${path}`, {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch {
    return { ok: false, problem: { status: 0, title: "Network error", detail: "Check your connection." } };
  }
  if (res.status === 204) return { ok: true, data: undefined as T };
  const json: unknown = await res.json().catch(() => ({}));
  if (res.ok) return { ok: true, data: json as T };
  const p = json as Partial<Problem>;
  return {
    ok: false,
    problem: { status: res.status, title: p.title ?? "Error", detail: p.detail, code: p.code },
  };
}

export function messageFor(problem: Problem): string {
  if (problem.status === 422 && problem.code !== "weak_password") {
    return "Please check the form: a field is missing or not valid.";
  }
  return problem.detail ?? problem.title;
}
