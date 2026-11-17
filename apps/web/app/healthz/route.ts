// Liveness probe for the web container (Docker HEALTHCHECK). No dependencies, no data.
export function GET(): Response {
  return Response.json({ status: "ok", service: "azinco-web" });
}
