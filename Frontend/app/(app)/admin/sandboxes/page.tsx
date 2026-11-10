"use client";

import { useState } from "react";
import { Flag, Search, SearchX } from "lucide-react";
import StatusBadge from "@/components/ui/StatusBadge";
import Skeleton from "@/components/ui/Skeleton";
import EmptyState from "@/components/ui/EmptyState";
import Tabs, { type TabItem } from "@/components/ui/Tabs";
import { barColor, hasComparableCost, useMoney, usedPct } from "@/components/admin/format";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import type { Sandbox, SandboxStatus } from "@/lib/types";
import ReasonDialog from "@/components/admin/ReasonDialog";

type StatusFilter = "All" | SandboxStatus;
type TypeFilter = "All" | Sandbox["type"];

const statuses: SandboxStatus[] = [
  "Pending",
  "Provisioning",
  "Failed",
  "Active",
  "Expiring",
  "Expired",
  "Rejected",
  "Decommissioning",
  "Decommissioned",
];
const typeOptions: TypeFilter[] = ["All", "Subscription", "Resource Group"];

const selectCls =
  "border border-border bg-background px-4 py-2.5 text-sm text-foreground focus:border-accent focus:outline-none";

export default function AdminSandboxesPage() {
  const money = useMoney();
  const { adminRequests: all, isLoading, flagCleanup } = useSandboxes();
  const [cleanup, setCleanup] = useState<Sandbox | null>(null);
  const [status, setStatus] = useState<StatusFilter>("All");
  const [unit, setUnit] = useState("All");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("All");
  const [query, setQuery] = useState("");

  const units = ["All", ...Array.from(new Set(all.map((s) => s.businessUnit))).sort()];

  const tabs: TabItem<StatusFilter>[] = [
    { value: "All", label: "All", count: all.length },
    ...statuses.map((s) => ({
      value: s,
      label: s,
      count: all.filter((x) => x.status === s).length,
    })),
  ];

  const q = query.trim().toLowerCase();
  const rows = all.filter(
    (s) =>
      (status === "All" || s.status === status) &&
      (unit === "All" || s.businessUnit === unit) &&
      (typeFilter === "All" || s.type === typeFilter) &&
      (!q ||
        s.name.toLowerCase().includes(q) ||
        s.id.toLowerCase().includes(q) ||
        s.requestorName.toLowerCase().includes(q) ||
        s.requestorEmail.toLowerCase().includes(q))
  );

  const filtersActive = status !== "All" || unit !== "All" || typeFilter !== "All" || q !== "";
  const clearFilters = () => {
    setStatus("All");
    setUnit("All");
    setTypeFilter("All");
    setQuery("");
  };

  return (
    <section className="border border-border bg-surface shadow-card">
      <div className="border-b border-border px-6 pt-2">
        <Tabs tabs={tabs} value={status} onChange={setStatus} label="Sandbox status" />
      </div>

      <div className="flex flex-wrap items-end gap-4 border-b border-border px-6 py-4">
        <div className="relative w-full sm:w-72">
          <Search size={16} className="absolute top-1/2 left-3 -translate-y-1/2 text-muted" aria-hidden="true" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name, ID or requestor..."
            aria-label="Search sandboxes"
            className="w-full border border-border bg-background py-2.5 pr-4 pl-9 text-sm text-foreground placeholder:text-muted focus:border-accent focus:outline-none"
          />
        </div>

        <label className="flex flex-col gap-1.5 text-xs font-medium text-muted">
          Business unit
          <select className={selectCls} value={unit} onChange={(e) => setUnit(e.target.value)}>
            {units.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </label>

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
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-10" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title="No matching sandboxes"
          text="Try a different search term or adjust the filters."
          action={filtersActive ? { label: "Clear filters", onClick: clearFilters } : undefined}
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[960px] text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-muted">
                <th scope="col" className="px-6 py-3 font-semibold">Sandbox</th>
                <th scope="col" className="px-6 py-3 font-semibold">Requestor</th>
                <th scope="col" className="px-6 py-3 font-semibold">Business unit</th>
                <th scope="col" className="px-6 py-3 font-semibold">Status</th>
                <th scope="col" className="px-6 py-3 font-semibold">Budget used</th>
                <th scope="col" className="px-6 py-3 text-right font-semibold">Spend</th>
                <th scope="col" className="px-6 py-3 font-semibold">Expiry</th>
                <th scope="col" className="px-6 py-3 font-semibold">Cleanup</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((s) => {
                const pct = usedPct(s);
                const noSpend = s.status === "Pending" || s.status === "Rejected";
                return (
                  <tr key={s.id}>
                    <td className="px-6 py-4">
                      <p className="font-mono text-foreground">{s.name}</p>
                      <p className="mt-0.5 text-xs text-muted">
                        {s.id} · {s.type}
                      </p>
                    </td>
                    <td className="px-6 py-4">
                      <p className="text-foreground">{s.requestorName}</p>
                      <p className="mt-0.5 text-xs text-muted">{s.requestorEmail}</p>
                    </td>
                    <td className="px-6 py-4">
                      <p className="text-foreground">{s.businessUnit}</p>
                      <p className="mt-0.5 text-xs text-muted">{s.costCenter}</p>
                    </td>
                    <td className="px-6 py-4">
                      <StatusBadge status={s.status} />
                    </td>
                    <td className="w-56 px-6 py-4">
                      {noSpend ? (
                        <span className="text-muted">{money(s.budget)} requested</span>
                      ) : !hasComparableCost(s) ? (
                        <span className="text-muted">Cost data unavailable</span>
                      ) : (
                        <>
                          <div className="h-2 overflow-hidden bg-background">
                            <div
                              className={`h-full ${barColor(pct)}`}
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
                              s.status === "Expiring"
                                ? "text-amber-700 dark:text-amber-400"
                                : "text-muted"
                            }`}
                          >
                            {s.daysLeft} days left
                          </p>
                        </>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {s.cleanupFlagged ? <p className="text-xs text-muted">Flagged; eligible {s.cleanupEligibleOn}</p> : (s.status === "Active" || s.status === "Expiring" || s.status === "Expired") && !s.operationInProgress ? (
                        <button onClick={() => setCleanup(s)} className="inline-flex items-center gap-2 text-sm text-accent"><Flag size={16} />Flag cleanup</button>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <ReasonDialog
        open={cleanup !== null}
        onClose={() => setCleanup(null)}
        title="Flag sandbox for cleanup"
        confirmLabel="Flag cleanup"
        intro={cleanup && <>Flag <span className="font-mono">{cleanup.name}</span> for resource deletion. Expired sandboxes wait for their grace period; other approved cleanup can start immediately.</>}
        onConfirm={async (reason) => { if (cleanup && await flagCleanup(cleanup.id, reason)) setCleanup(null); }}
      />
    </section>
  );
}
