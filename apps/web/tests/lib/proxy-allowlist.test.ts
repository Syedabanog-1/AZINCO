import { describe, expect, it } from "vitest";
import { isProxyAllowed } from "@/lib/api/proxy-allowlist";

describe("API proxy allow-list", () => {
  it.each([
    "auth/login",
    "auth/logout",
    "auth/register",
    "auth/verify-email",
    "auth/mfa/setup",
    "auth/mfa/confirm",
    "me",
    "tenants/0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b",
  ])("allows %s", (path) => expect(isProxyAllowed(path)).toBe(true));

  it.each([
    "",
    "health",
    "ready",
    "docs",
    "openapi.json",
    "auth/login/../../internal",
    "tenants/not-a-uuid",
    "tenants/0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b/members",
    "me?x=1",
    "admin/kill-switch",
  ])("blocks %s", (path) => expect(isProxyAllowed(path)).toBe(false));
});
