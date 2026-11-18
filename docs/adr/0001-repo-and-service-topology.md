# ADR-0001: Repository and service topology — monorepo, modular-monolith API + ledger + worker

| Field | Value |
|---|---|
| Status | Accepted (as built in Steps 0.1–0.10) |
| Date | 2026-11-18 |
| Base Standard | §8.2 (small Ledger Service is the only writer), §11.2 (stack) |
| Label | [Recommended] (blueprint AP-9) |

## Decision
One Git monorepo: `apps/web` (Next.js), `services/api` (FastAPI modular monolith),
`services/ledger` (only journal writer, ADR-0016), `services/worker` (Model Gateway + LangGraph,
ADR-0002/0004), `packages/py-common` (Money), `packages/rule-engine` (ADR-0008), `rule-packs/`,
`infra/docker`, `docs/`. Each deployable has its own image and DB role. Modules are extracted into
services only when load or ownership demands it.

## Options
| Option | Pros | Cons |
|---|---|---|
| A. Monorepo + modular monolith + 2 special services (chosen) | One CI, atomic changes, strong boundaries where it matters (money, agents) | Discipline needed to keep module boundaries |
| B. Microservices from day one | Independent scaling | Heavy ops before product-market fit |
| C. Single process for everything | Simplest | Agents and API could reach posting code; violates BS §8.2 |

## Consequences
Shared code lives only in `packages/`; services never import each other. CI builds every image.
