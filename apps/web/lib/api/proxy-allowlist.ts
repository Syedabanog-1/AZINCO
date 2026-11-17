// Paths the browser may reach on the API through the same-origin proxy (/api/v1/...).
export const PROXY_ALLOWED: readonly RegExp[] = [
  /^auth\/(register|verify-email|login|logout|mfa\/setup|mfa\/confirm)$/,
  /^me$/,
  /^tenants\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
];

export function isProxyAllowed(path: string): boolean {
  return PROXY_ALLOWED.some((re) => re.test(path));
}
