import "@fontsource/spectral/500.css";
import "@fontsource/spectral/600.css";
import "@fontsource-variable/public-sans";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "AZINCO — AI-assisted accounting, expert approved", template: "%s · AZINCO" },
  description:
    "Bookkeeping, reconciliation, financial statements and tax records for Pakistani and international businesses. AI prepares, code calculates, a qualified Reviewer of Record approves.",
};

/** Root shell only. Each area adds its own chrome: (public), (auth), and the signed-in app shell. */
export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <a href="#main" className="skip-link">
          Skip to content
        </a>
        <div className="border-b border-warn/20 bg-warn-tint px-4 py-1.5 text-center text-xs font-medium text-warn">
          Pre-alpha preview. Not production-ready: payments, AI models and OCR are [MOCK] or
          [SANDBOX], and all data is synthetic.
        </div>
        {children}
      </body>
    </html>
  );
}
