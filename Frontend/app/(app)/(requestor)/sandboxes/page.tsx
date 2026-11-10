"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Box, Search, SearchX } from "lucide-react";
import StatusBadge from "@/components/ui/StatusBadge";
import Skeleton from "@/components/ui/Skeleton";
import EmptyState from "@/components/ui/EmptyState";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import type { Sandbox, SandboxStatus } from "@/lib/types";
import { hasComparableCost, useMoney, usedPct } from "@/components/admin/format";

const tabs: ("All" | SandboxStatus)[] = [
  "All",
  "Pending",
  "Provisioning",
  "Active",
  "Expiring",
  "Expired",
  "Failed",
  "Rejected",
  "Decommissioned",
];

type TypeFilter = "All" | Sandbox["type"];
const typeOptions: TypeFilter[] = ["All", "Subscription", "Resource Group"];

type SortKey = "default" | "expiry" | "spend" | "budgetPct";
const sortOptions: { value: SortKey; label: string }[] = [
  { value: "default", label: "Default" },
  { value: "expiry", label: "Expiry soonest" },
  { value: "spend", label: "Spend high to low" },
  { value: "budgetPct", label: "Budget used %" },
];

const selectCls =
  "border border-border bg-background px-4 py-2.5 text-sm text-foreground focus:border-accent focus:outline-none";

const budgetPct = (s: Sandbox) => hasComparableCost(s) && s.budget ? s.spent / s.budget : -1;

const comparators: Record<Exclude<SortKey, "default">, (a: Sandbox, b: Sandbox) => number> = {
  expiry: (a, b) => (a.daysLeft ?? Infinity) - (b.daysLeft ?? Infinity),
  spend: (a, b) => (b.spent ?? -Infinity) - (a.spent ?? -Infinity),
  budgetPct: (a, b) => budgetPct(b) - budgetPct(a),
};

function barColor(pct: number) {
  if (pct >= 90) return "bg-red-500";
  if (pct >= 75) return "bg-amber-500";
  return "bg-emerald-500";
}

export default function SandboxesPage() {
  const money = useMoney();
  const router = useRouter();
  const { sandboxes, isLoading } = useSandboxes();
  const [tab, setTab] = useState<"All" | SandboxStatus>("All");
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("All");
  const [sort, setSort] = useState<SortKey>("default");

  const countFor = (t: "All" | SandboxStatus) =>
    t === "All" ? sandboxes.length : sandboxes.filter((s) => s.status === t).length;

  const q = query.trim().toLowerCase();
  const filtered = sandboxes.filter(
    (s) =>
      (tab === "All" || s.status === tab) &&
      (typeFilter === "All" || s.type === typeFilter) &&
      (!q || s.name.toLowerCase().includes(q) || s.id.toLowerCase().includes(q))
  );
  const rows = sort === "default" ? filtered : [...filtered].sort(comparators[sort]);

  const filtersActive = tab !== "All" || typeFilter !== "All" || q !== "";
  const clearFilters = () => {
    setTab("All");
    setTypeFilter("All");
    setQuery("");
    setSort("default");
  };

  return (
    <section className="rounded-card border border-border bg-surface shadow-card">
      {/* Tabs + search */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border px-6 pt-2">
        <div className="flex flex-wrap gap-1">
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

        <div className="relative mb-2 w-full sm:mb-0 sm:w-64">
          <Search size={16} className="absolute top-1/2 left-3 -translate-y-1/2 text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search sandboxes..."
            aria-label="Search sandboxes"
            className="w-full rounded-full border border-border bg-background py-2.5 pr-4 pl-9 text-sm text-foreground placeholder:text-muted focus:border-accent focus:outline-none"
          />
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-4 border-b border-border px-6 py-4">
        <label className="flex flex-col gap-1.5 text-xs font-medium text-muted">
          Type
          <select
            className={selectCls}
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as TypeFilter)}
          >
            {typeOptions.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1.5 text-xs font-medium text-muted">
          Sort by
          <select
            className={selectCls}
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
          >
            {sortOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>

        {filtersActive && (
          <button
            onClick={clearFilters}
            className="px-2 py-2.5 text-sm font-medium text-accent transition hover:text-accent-light"
          >
            Clear filters
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-4 p-6" aria-busy="true" aria-label="Loading sandboxes">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="flex items-center gap-6">
              <Skeleton className="h-10 flex-1" />
              <Skeleton className="h-6 w-24" />
              <Skeleton className="h-2 w-48" />
              <Skeleton className="h-6 w-20" />
            </div>
          ))}
        </div>
      ) : sandboxes.length === 0 ? (
        <EmptyState
          icon={Box}
          title="No sandboxes yet"
          text="Request your first Azure sandbox to start experimenting."
          action={{ label: "New request", href: "/requests/new" }}
        />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title="No matching sandboxes"
          text="Try a different search term or adjust the filters."
          action={{ label: "Clear filters", onClick: clearFilters }}
        />
      ) : (
      <div className="overflow-x-auto">
        <table className="w-full min-w-[800px] text-left text-sm">
          <thead>
            <tr className="border-b border-border text-xs text-muted">
              <th className="px-6 py-3 font-semibold">Sandbox</th>
              <th className="px-6 py-3 font-semibold">Business unit</th>
              <th className="px-6 py-3 font-semibold">Status</th>
              <th className="px-6 py-3 font-semibold">Budget used</th>
              <th className="px-6 py-3 text-right font-semibold">Spend</th>
              <th className="px-6 py-3 font-semibold">Expiry</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((s) => {
              const noSpend = s.status === "Pending" || s.status === "Rejected";
              const pct = usedPct(s);
              return (
                <tr
                  key={s.id}
                  onClick={() => router.push(`/sandboxes/${s.id}`)}
                  className="cursor-pointer transition hover:bg-surface-2/50"
                >
                  <td className="px-6 py-4">
                    <Link
                      href={`/sandboxes/${s.id}`}
                      onClick={(e) => e.stopPropagation()}
                      className="font-mono text-foreground hover:text-accent"
                    >
                      {s.name}
                    </Link>
                    <p className="mt-0.5 text-xs text-muted">
                      {s.id} · {s.type}
                    </p>
                  </td>
                  <td className="px-6 py-4">
                    <p className="text-foreground">{s.businessUnit}</p>
                    <p className="mt-0.5 text-xs text-muted">{s.costCenter}</p>
                  </td>
                  <td className="px-6 py-4">
                    <StatusBadge status={s.status} />
                  </td>
                  <td className="w-64 px-6 py-4">
                    {noSpend ? (
                      <span className="text-muted">{money(s.budget)} requested</span>
                    ) : !hasComparableCost(s) ? (
                      <span className="text-muted">Cost data unavailable</span>
                    ) : (
                      <>
                        <div className="h-2 overflow-hidden rounded-full bg-background">
                          <div
                            className={`h-full rounded-full ${barColor(pct)}`}
                            style={{ width: `${Math.min(pct, 100)}%` }}
                          />
                        </div>
                        <p className="mt-1.5 text-xs text-muted">
                          {pct}% of {money(s.budget)}
                        </p>
                      </>
                    )}
                  </td>
                  <td className="px-6 py-4 text-right font-medium text-foreground">
                    {money(s.spent, 2, s.costCurrency)}
                  </td>
                  <td className="px-6 py-4">
                    {s.expiry ? (
                      <>
                        <p className="text-foreground">{s.expiry}</p>
                        <p
                          className={`mt-0.5 text-xs ${
                            s.status === "Expiring" ? "text-amber-700 dark:text-amber-400" : "text-muted"
                          }`}
                        >
                          {s.daysLeft} days left
                        </p>
                      </>
                    ) : (
                      <span className="text-muted">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      )}
    </section>
  );
}