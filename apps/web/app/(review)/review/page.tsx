import type { Metadata } from "next";
import { PlannedInterfacePage } from "@/components/planned-interface";
import { PLANNED } from "@/lib/content";

export const metadata: Metadata = { title: "Reviewer dashboard" };

export default function Page() {
  return <PlannedInterfacePage plan={PLANNED.review} />;
}
