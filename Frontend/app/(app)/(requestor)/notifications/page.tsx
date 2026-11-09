"use client";

import { useState } from "react";
import { Bell } from "lucide-react";
import Skeleton from "@/components/ui/Skeleton";
import EmptyState from "@/components/ui/EmptyState";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import type { Notification } from "@/lib/demoData";

type Tab = "All" | Notification["category"];
const tabs: Tab[] = ["All", "Budget", "Approval"];

const badgeStyles: Record<Notification["category"], string> = {
  Budget: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  Approval: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400",
};

export default function NotificationsPage() {
  const { notifications, isLoading } = useSandboxes();
  const [tab, setTab] = useState<Tab>("All");

  const countFor = (t: Tab) =>
    t === "All" ? notifications.length : notifications.filter((n) => n.category === t).length;

  const rows = notifications.filter((n) => tab === "All" || n.category === tab);

  return (
    <section className="rounded-card border border-border bg-surface shadow-card">
      {/* Tabs */}
      <div className="flex gap-1 border-b border-border px-6 pt-2">
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`border-b-2 px-3 py-4 text-sm font-medium transition ${
              tab === t
                ? "border-accent text-accent"
                : "border-transparent text-muted hover:text-foreground"
            }`}
          >
            {t} <span className="ml-0.5 text-xs">{countFor(t)}</span>
          </button>
        ))}
      </div>

      {/* List */}
      {isLoading ? (
        <div className="space-y-5 p-6" aria-busy="true" aria-label="Loading notifications">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="flex gap-4">
              <Skeleton className="h-6 w-20" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-3 w-1/3" />
              </div>
            </div>
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Bell}
          title="No notifications"
          text={
            tab === "All"
              ? "You're all caught up. Budget and approval alerts will appear here."
              : `You have no ${tab.toLowerCase()} notifications.`
          }
        />
      ) : (
        <ul className="divide-y divide-border">
          {rows.map((n) => (
            <li key={n.id} className="flex flex-wrap items-start gap-4 px-6 py-5 transition hover:bg-surface-2/50">
              <span
                className={`mt-0.5 h-fit shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-medium ${badgeStyles[n.category]}`}
              >
                {n.category}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">{n.title}</p>
                <p className="mt-1 text-xs text-muted">To: {n.to}</p>
              </div>
              <span className="shrink-0 text-xs text-muted">{n.when}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}