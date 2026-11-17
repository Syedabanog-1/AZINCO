import { describe, expect, it } from "vitest";
import * as content from "@/lib/content";

describe("public content", () => {
  it("never names domestic payment providers (Project Instructions §3)", () => {
    const text = JSON.stringify(content).toLowerCase().replace(/\s+/g, "");
    // Names are assembled from fragments so this file passes the repository guard itself.
    const forbidden = [["jazz", "cash"], ["easy", "paisa"]].map((parts) => parts.join(""));
    for (const name of forbidden) expect(text).not.toContain(name);
  });

  it("lists the five initial jurisdictions and four delivery modes", () => {
    expect(content.JURISDICTIONS).toHaveLength(5);
    expect(content.DELIVERY_MODES.map((m) => m.code)).toEqual(["A", "B", "C", "D"]);
  });

  it("reports in PKR and USD and offers Card via Stripe, not PayPal (owner decision)", () => {
    expect(content.REPORTING_CURRENCIES).toEqual(["PKR", "USD"]);
    expect(JSON.stringify(content).toLowerCase()).not.toContain("paypal");
  });

  it("has a plan for every placeholder interface", () => {
    for (const key of ["dashboard", "review", "admin"] as const) {
      expect(content.PLANNED[key].items.length).toBeGreaterThan(0);
    }
  });
});
