"use client";

import Link from "next/link";
import { AlertTriangle, Bell, Box, Clock, IndianRupee, Shield } from "lucide-react";
import StatusBadge from "@/components/ui/StatusBadge";
import Skeleton from "@/components/ui/Skeleton";
import EmptyState from "@/components/ui/EmptyState";
import { useAuth } from "@/hooks/useAuth";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import { hasComparableCost, useMoney, usedPct } from "@/components/admin/format";


function barColor(pct: number) {
  if (pct >= 90) return "bg-red-500";
  if (pct >= 75) return "bg-amber-500";
  return "bg-emerald-500";
}

export default function DashboardPage() {
  const money = useMoney();
  const { account } = useAuth();
  const { sandboxes, notifications, isLoading } = useSandboxes();
  const firstName = account?.name?.split(" ")[0];

  const visible = sandboxes.filter((s) => s.status !== "Rejected");

  const live = sandboxes.filter((s) => s.status === "Active" || s.status === "Expiring");
  const pending = sandboxes.filter((s) => s.status === "Pending");
  const costed = live.filter(hasComparableCost);
  const spent = costed.reduce((sum, s) => sum + s.spent, 0);
  const approved = costed.reduce((sum, s) => sum + s.budget, 0);
  const utilization = approved ? Math.round((spent / approved) * 100) : 0;
  const expiringSoon = sandboxes.find((s) => s.status === "Expiring");

  const stats = [
    { icon: Box, label: "Active sandboxes", value: String(live.length), sub: `${sandboxes.filter((s) => s.status === "Expired").length} expired and awaiting disposition`, tone: "orange" },
    { icon: Clock, label: "Pending requests", value: String(pending.length), sub: "Awaiting IT approval", tone: "cyan" },
    { icon: IndianRupee, label: "Month-to-date spend", value: money(costed.length ? spent : null), sub: `${costed.length} of ${live.length} active sandboxes reported`, tone: "lime" },
    { icon: Shield, label: "Budget utilization", value: costed.length ? `${utilization}%` : "Unavailable", sub: "Across reported sandboxes", tone: "magenta" },
  ];
  const iconTones: Record<string, string> = {
    orange: "bg-accent text-white",
    cyan: "bg-brand-cyan text-[#161616]",
    lime: "bg-brand-lime text-[#161616]",
    magenta: "bg-brand-magenta text-white",
  };

  if (isLoading) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading dashboard">
        <Skeleton className="h-14 w-80 max-w-full" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="pb-1">
        <p className="mb-2 text-xs font-bold tracking-[0.18em] text-accent uppercase">
          Sandbox workspace
        </p>
        <h2 className="text-3xl font-bold text-foreground">
          {firstName ? `Welcome back, ${firstName}` : "Your sandbox overview"}
        </h2>
        <p className="mt-2 text-muted">A clear view of your environments, requests and spend.</p>
      </div>

      {expiringSoon && (
        <div className="flex items-center gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-5 py-4 text-sm text-amber-800 dark:text-amber-300">
          <AlertTriangle size={18} className="shrink-0" />
          <p>
            <span className="font-semibold">{expiringSoon.name}</span> expires in{" "}
            {expiringSoon.daysLeft} day(s).{" "}
            <Link
              href={`/sandboxes/${expiringSoon.id}`}
              className="underline hover:text-amber-900 dark:hover:text-amber-200"
            >
              Request an extension
            </Link>
          </p>
        </div>
      )}

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map(({ icon: Icon, label, value, sub, tone }) => (
          <div key={label} className="rounded-card border border-border bg-surface p-5 shadow-card">
            <div className="flex items-center gap-3">
              <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${iconTones[tone]}`}>
                <Icon size={17} />
              </span>
              <span className="text-sm font-medium text-muted">{label}</span>
            </div>
            <p className="mt-4 break-words text-2xl font-bold text-foreground">{value}</p>
            <p className="mt-1 text-sm text-muted">{sub}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
        {/* My sandboxes */}
        <section className="rounded-card border border-border bg-surface shadow-card">
          <div className="flex items-center justify-between border-b border-border px-6 py-4">
            <h3 className="font-semibold text-foreground">My sandboxes</h3>
            <Link href="/sandboxes" className="text-sm text-accent hover:text-accent-light">
              View all
            </Link>
          </div>

          {visible.length === 0 ? (
            <EmptyState
              icon={Box}
              title="No sandboxes yet"
              text="Request your first Azure sandbox to start experimenting."
              action={{ label: "New request", href: "/requests/new" }}
            />
          ) : (
          <div className="grid gap-4 p-6 md:grid-cols-2">
            {visible.map((s) => {
              const pct = usedPct(s);
              return (
                <Link
                  key={s.id}
                  href={`/sandboxes/${s.id}`}
                  className="block rounded-2xl border border-border bg-surface-2 p-5 transition hover:border-accent"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-mono text-sm text-foreground">{s.name}</p>
                    <StatusBadge status={s.status} />
                  </div>
                  <p className="mt-2 text-sm text-muted">
                    {s.workload} · {s.type}
                  </p>

                  {s.status === "Pending" || s.status === "Provisioning" || s.status === "Failed" ? (
                    <p className="mt-4 text-sm text-muted">
                      Requested {s.requestedOn} · {money(s.budget)} · {s.durationDays} days
                    </p>
                  ) : !hasComparableCost(s) ? (
                    <p className="mt-4 text-sm text-muted">Cost data unavailable</p>
                  ) : (
                    <>
                      <div className="mt-4 h-2 overflow-hidden rounded-full bg-background">
                        <div
                          className={`h-full rounded-full ${barColor(pct)}`}
                          style={{ width: `${Math.min(pct, 100)}%` }}
                        />
                      </div>
                      <div className="mt-2 flex justify-between text-sm">
                        <span className="text-foreground">
                          {money(s.spent, 2, s.costCurrency)} / {money(s.budget)}
                        </span>
                        <span className="text-muted">{s.daysLeft}d left</span>
                      </div>
                    </>
                  )}
                </Link>
              );
            })}
          </div>
          )}
        </section>

        {/* Recent notifications */}
        <section className="rounded-card border border-border bg-surface shadow-card">
          <div className="flex items-center justify-between border-b border-border px-6 py-4">
            <h3 className="font-semibold text-foreground">Recent notifications</h3>
            <Link href="/notifications" className="text-sm text-accent hover:text-accent-light">
              View all
            </Link>
          </div>

          {notifications.length === 0 ? (
            <EmptyState
              icon={Bell}
              title="No notifications"
              text="You're all caught up. Budget and approval alerts will appear here."
            />
          ) : (
          <ul className="divide-y divide-border">
            {notifications.map((n) => (
              <li key={n.id} className="flex gap-3 px-6 py-4">
                <span
                  className={`mt-0.5 h-fit shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                    n.category === "Budget"
                      ? "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400"
                      : "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400"
                  }`}
                >
                  {n.category}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-foreground">{n.title}</p>
                  <p className="mt-1 truncate text-xs text-muted">To: {n.to}</p>
                </div>
                <span className="shrink-0 text-xs text-muted">{n.when}</span>
              </li>
            ))}
          </ul>
          )}
        </section>
      </div>
    </div>
  );
}