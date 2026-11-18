import type { Metadata } from "next";
import { AccountPanel } from "@/components/forms/account-panel";
import { PageHeader } from "@/components/ui";

export const metadata: Metadata = { title: "Account and security" };

export default function AccountPage() {
  return (
    <>
      <PageHeader
        title="Account and security"
        description="Your profile, workspaces and sign-in protection."
      />
      <div className="mt-8">
        <AccountPanel />
      </div>
    </>
  );
}
