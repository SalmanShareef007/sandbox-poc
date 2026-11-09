"use client";

import Link from "next/link";
import {
  AlertTriangle,
  CalendarClock,
  CircleCheck,
  ClipboardCheck,
  IndianRupee,
  Hourglass,
  RefreshCw,
  ShieldCheck,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import EmptyState from "@/components/ui/EmptyState";
import Skeleton from "@/components/ui/Skeleton";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import { isLive, money, usedPct } from "@/components/admin/format";
import { parseDemoDate } from "@/lib/dates";

interface Stat {
  icon: LucideIcon;
  label: string;
  value: string;
  sub: string;
  href?: string;
}

type AttentionKind = "pending" | "failed" | "budget";

interface AttentionItem {
  key: string;
  kind: AttentionKind;
  title: string;
  detail: string;
  href: string;
  action: string;
}

const kindStyles: Record<AttentionKind, { label: string; cls: string; icon: LucideIcon }> = {
  pending: {
    label: "Approval",
    cls: "border-accent/30 bg-accent/10 text-accent-dark dark:text-accent-light",
    icon: Hourglass,
  },
  failed: {
    label: "Failed",
    cls: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400",
    icon: RefreshCw,
  },
  budget: {
    label: "Budget",
    cls: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400",
    icon: AlertTriangle,
  },
};

const statCardCls = "block border border-border bg-surface p-5 shadow-card";

export default function AdminOverviewPage() {
  const { adminRequests: all, extensionRequests, isLoading } = useSandboxes();

  if (isLoading) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading admin overview">
        <Skeleton className="h-14 w-80 max-w-full" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <div className="grid gap-6 xl:grid-cols-[3fr_2fr]">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      </div>
    );
  }

  const pending = all
    .filter((s) => s.status === "Pending")
    .sort(
      (a, b) =>
        parseDemoDate(a.requestedOn ?? "").getTime() - parseDemoDate(b.requestedOn ?? "").getTime()
    );
  const pendingExtensions = extensionRequests.filter((e) => e.status === "Pending");
  const active = all.filter((s) => s.status === "Active");
  const expiring = all.filter((s) => s.status === "Expiring");
  const failed = all.filter((s) => s.status === "Failed");
  const live = all.filter(isLive);
  const alerts = live.filter((s) => usedPct(s) >= 90);
  const totalSpend = all.reduce((sum, s) => sum + s.spent, 0);

  const stats: Stat[] = [
    {
      icon: ClipboardCheck,
      label: "Pending approvals",
      value: String(pending.length),
      sub: "Requests awaiting a decision",
      href: "/admin/approvals",
    },
    {
      icon: CalendarClock,
      label: "Pending extensions",
      value: String(pendingExtensions.length),
      sub: "Extension requests to review",
      href: "/admin/extensions",
    },
    { icon: ShieldCheck, label: "Active sandboxes", value: String(active.length), sub: "Running normally" },
    { icon: Hourglass, label: "Expiring soon", value: String(expiring.length), sub: "Within 7 days" },
    { icon: IndianRupee, label: "Total spend", value: money(totalSpend), sub: "Across all sandboxes" },
    { icon: AlertTriangle, label: "Budget alerts", value: String(alerts.length), sub: "At 90% of budget or more" },
  ];

  const attention: AttentionItem[] = [
    ...pending.slice(0, 5).map((s) => ({
      key: `p-${s.id}`,
      kind: "pending" as const,
      title: s.name,
      detail: `${s.requestorName} · requested ${s.requestedOn} · ${money(s.budget)}`,
      href: "/admin/approvals",
      action: "Review",
    })),
    ...failed.map((s) => ({
      key: `f-${s.id}`,
      kind: "failed" as const,
      title: s.name,
      detail: s.provisioningNote ?? "Provisioning failed",
      href: "/admin/approvals?tab=failed",
      action: "Retry",
    })),
    ...alerts.map((s) => ({
      key: `b-${s.id}`,
      kind: "budget" as const,
      title: s.name,
      detail: `${usedPct(s)}% of ${money(s.budget)} used · ${s.requestorName}`,
      href: "/admin/sandboxes",
      action: "View",
    })),
  ];

  const byUnit = Object.entries(
    all.reduce<Record<string, number>>((acc, s) => {
      if (s.spent > 0) acc[s.businessUnit] = (acc[s.businessUnit] ?? 0) + s.spent;
      return acc;
    }, {})
  ).sort(([, a], [, b]) => b - a);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-foreground">Admin overview</h2>
        <p className="mt-1 text-muted">
          Approvals, extensions and spend across every sandbox in the organisation.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {stats.map(({ icon: Icon, label, value, sub, href }) => {
          const body = (
            <>
              <div className="flex items-center gap-2 text-sm text-muted">
                <Icon size={16} className="text-accent" />
                {label}
              </div>
              <p className="mt-3 text-3xl font-bold text-foreground">{value}</p>
              <p className="mt-1 text-sm text-muted">{sub}</p>
            </>
          );
          return href ? (
            <Link key={label} href={href} className={`${statCardCls} transition hover:border-accent`}>
              {body}
            </Link>
          ) : (
            <div key={label} className={statCardCls}>
              {body}
            </div>
          );
        })}
      </div>

      <div className="grid gap-6 xl:grid-cols-[3fr_2fr]">
        <section className="border border-border bg-surface shadow-card">
          <div className="border-b border-border px-6 py-4">
            <h3 className="font-semibold text-foreground">Needs attention</h3>
          </div>
          {attention.length === 0 ? (
            <EmptyState
              icon={CircleCheck}
              title="All clear"
              text="No pending approvals, failed provisioning runs or budget alerts right now."
            />
          ) : (
            <ul className="divide-y divide-border">
              {attention.map((item) => {
                const kind = kindStyles[item.kind];
                return (
                  <li key={item.key} className="flex flex-wrap items-center gap-4 px-6 py-4">
                    <span
                      className={`inline-flex shrink-0 items-center gap-1.5 border px-2.5 py-0.5 text-xs font-medium ${kind.cls}`}
                    >
                      <kind.icon size={12} />
                      {kind.label}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-mono text-sm text-foreground">{item.title}</p>
                      <p className="mt-0.5 truncate text-xs text-muted">{item.detail}</p>
                    </div>
                    <Link
                      href={item.href}
                      className="shrink-0 text-sm font-medium text-accent hover:text-accent-light"
                    >
                      {item.action}
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="border border-border bg-surface shadow-card">
          <div className="border-b border-border px-6 py-4">
            <h3 className="font-semibold text-foreground">Spend by business unit</h3>
          </div>
          {byUnit.length === 0 ? (
            <EmptyState icon={Wallet} title="No spend yet" text="Spend appears here once sandboxes are in use." />
          ) : (
            <ul className="space-y-5 p-6">
              {byUnit.map(([unit, amount]) => {
                const share = totalSpend ? Math.round((amount / totalSpend) * 100) : 0;
                return (
                  <li key={unit}>
                    <div className="flex items-baseline justify-between gap-4 text-sm">
                      <span className="text-foreground">{unit}</span>
                      <span className="text-muted">
                        <span className="font-medium text-foreground">{money(amount)}</span> · {share}%
                      </span>
                    </div>
                    <div
                      className="mt-2 h-2 overflow-hidden bg-background"
                      role="img"
                      aria-label={`${unit}: ${share}% of total spend`}
                    >
                      <div className="bg-accent-gradient h-full" style={{ width: `${share}%` }} />
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
