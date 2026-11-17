import type { Metadata } from "next";
import { AccountPanel } from "@/components/forms/account-panel";

export const metadata: Metadata = { title: "Your account" };

export default function AccountPage() {
  return (
    <section className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">Your account</h1>
      <div className="mt-6">
        <AccountPanel />
      </div>
    </section>
  );
}
