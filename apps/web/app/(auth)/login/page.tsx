import type { Metadata } from "next";
import { PlannedInterfacePage } from "@/components/planned-interface";
import { PLANNED } from "@/lib/content";

export const metadata: Metadata = { title: "Sign in" };

export default function Page() {
  return <PlannedInterfacePage plan={PLANNED.login} />;
}
