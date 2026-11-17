# apps/web — AZINCO web (Next.js 16, App Router)

Strict TypeScript, Tailwind CSS v4, Zod. Cache Components enabled (Next 16 default).

| Route | What |
|---|---|
| `/` | Public site: services, how it works, delivery modes, payments (**Banking Channels** / Card / PayPal), jurisdictions |
| `/status` | Live system status — server-side call to the API `/health` + `/ready` |
| `/login`, `/dashboard`, `/review`, `/admin` | Clearly labelled placeholders for later steps (not fake features) |
| `/healthz` | Container liveness probe |

```bash
npm ci
npm run dev            # http://localhost:3000 (needs the API on :8000, or set AZINCO_API_INTERNAL_URL)
npm run check          # typecheck + unit tests + production build
npm run test:e2e       # Playwright against a running stack (npx playwright install chromium first)
```

`AZINCO_API_INTERNAL_URL` is read on the server only (default `http://localhost:8000`). The browser never calls internal services directly.
