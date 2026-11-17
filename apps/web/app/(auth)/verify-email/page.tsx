import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthCard } from "@/components/auth-ui";
import { VerifyEmail } from "@/components/forms/verify-email";

export const metadata: Metadata = { title: "Confirm e-mail" };

export default function VerifyEmailPage() {
  return (
    <AuthCard title="Confirm your e-mail">
      <Suspense fallback={<div className="h-10 animate-pulse rounded-md bg-line/40" />}>
        <VerifyEmail />
      </Suspense>
    </AuthCard>
  );
}
