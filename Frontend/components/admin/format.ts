"use client";

import type { Sandbox } from "@/lib/types";
import { useRole } from "@/hooks/useRole";

export const money = (n: number | null, digits = 0, currency = "USD") =>
  n === null ? "Unavailable" : n.toLocaleString("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

export const usedPct = (s: Pick<Sandbox, "spent" | "budget" | "costCurrency" | "budgetCurrency">) =>
  s.budget && s.spent !== null && (s.costCurrency ?? "USD") === (s.budgetCurrency ?? "USD")
    ? Math.round((s.spent / s.budget) * 100) : 0;

export const hasComparableCost = (s: Sandbox): s is Sandbox & { spent: number } =>
  s.spent !== null && (s.costCurrency ?? "USD") === (s.budgetCurrency ?? "USD");

export function useMoney() {
  const { budgetCurrency } = useRole();
  return (amount: number | null, digits = 0, currency = budgetCurrency) => money(amount, digits, currency);
}

export function barColor(pct: number) {
  if (pct >= 90) return "bg-red-500";
  if (pct >= 75) return "bg-amber-500";
  return "bg-emerald-500";
}

export const isLive = (s: Sandbox) => s.status === "Active" || s.status === "Expiring" || s.status === "Expired";

/** Statuses that have an approved budget (approved at some point). */
export const hasApprovedBudget = (s: Sandbox) =>
  s.status !== "Pending" && s.status !== "Rejected";

export const sameEmail = (a?: string, b?: string) =>
  !!a && !!b && a.trim().toLowerCase() === b.trim().toLowerCase();

export const SELF_APPROVAL_MESSAGE = "You cannot approve your own request.";
