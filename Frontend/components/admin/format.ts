import type { Sandbox } from "@/lib/demoData";

export const money = (n: number, digits = 0) =>
  n.toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

export const usedPct = (s: Pick<Sandbox, "spent" | "budget">) =>
  s.budget ? Math.round((s.spent / s.budget) * 100) : 0;

export function barColor(pct: number) {
  if (pct >= 90) return "bg-red-500";
  if (pct >= 75) return "bg-amber-500";
  return "bg-emerald-500";
}

export const isLive = (s: Sandbox) => s.status === "Active" || s.status === "Expiring";

/** Statuses that have an approved budget (approved at some point). */
export const hasApprovedBudget = (s: Sandbox) =>
  s.status !== "Pending" && s.status !== "Rejected";

export const sameEmail = (a?: string, b?: string) =>
  !!a && !!b && a.trim().toLowerCase() === b.trim().toLowerCase();

export const SELF_APPROVAL_MESSAGE = "You cannot approve your own request.";
