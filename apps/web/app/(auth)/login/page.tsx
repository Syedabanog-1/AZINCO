import type { Metadata } from "next";
import { AuthCard } from "@/components/auth-ui";
import { LoginForm } from "@/components/forms/login-form";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <AuthCard title="Sign in" subtitle="Clients, reviewers and staff sign in here.">
      <LoginForm />
    </AuthCard>
  );
}
