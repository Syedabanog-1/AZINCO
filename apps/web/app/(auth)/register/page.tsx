import type { Metadata } from "next";
import { connection } from "next/server";
import { Suspense } from "react";
import { AuthCard } from "@/components/auth-ui";
import { RegisterForm } from "@/components/forms/register-form";

export const metadata: Metadata = { title: "Create account" };

export default function RegisterPage() {
  return (
    <AuthCard title="Create your account" subtitle="We will send a confirmation link to your e-mail.">
      <Suspense fallback={<div className="h-64 animate-pulse rounded-md bg-line/40" />}>
        <RegisterWithRuntimeConfig />
      </Suspense>
    </AuthCard>
  );
}

async function RegisterWithRuntimeConfig() {
  await connection(); // read runtime env, not build-time env
  return <RegisterForm devMailboxUrl={process.env.AZINCO_DEV_MAILBOX_URL ?? null} />;
}
