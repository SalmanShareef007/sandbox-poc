"use client";

import { useState } from "react";
import Link from "next/link";
import { Download, Flag, Search, SearchX, Trash2 } from "lucide-react";
import { downloadCsv } from "@/lib/csv";
import StatusBadge from "@/components/ui/StatusBadge";
import Skeleton from "@/components/ui/Skeleton";
import EmptyState from "@/components/ui/EmptyState";
import Tabs, { type TabItem } from "@/components/ui/Tabs";
import { barColor, hasComparableCost, useMoney, usedPct } from "@/components/admin/format";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import type { Sandbox, SandboxStatus } from "@/lib/types";
import ReasonDialog from "@/components/admin/ReasonDialog";
import { useToast } from "@/components/providers/ToastProvider";

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
const PAGE_SIZE = 6;

const selectCls =
  "border border-border bg-background px-4 py-2.5 text-sm text-foreground focus:border-accent focus:outline-none";

export default function AdminSandboxesPage() {
  const money = useMoney();
  const { adminRequests: all, isLoading, flagCleanup, deleteDecommissioned, configuration } = useSandboxes();
  const { toast } = useToast();
  const [cleanup, setCleanup] = useState<Sandbox | null>(null);
  const [status, setStatus] = useState<StatusFilter>("All");
  const [unit, setUnit] = useState("All");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("All");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);

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
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const visibleRows = rows.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  const filtersActive = status !== "All" || unit !== "All" || typeFilter !== "All" || q !== "";
  const exportCsv = () =>
    downloadCsv(
      `sandboxes-${new Date().toISOString().slice(0, 10)}.csv`,
      ["Reference", "Resource group", "Status", "Requestor", "Requestor email", "Business unit", "Cost centre", "Region",
        "Budget", "Spent", "Currency", "Expiry", "Days left"],
      rows.map((s) => [s.id, s.name, s.status, s.requestorName, s.requestorEmail, s.businessUnit, s.costCenter, s.region,
        s.budget, s.spent ?? "", s.budgetCurrency ?? "", s.expiryDate ?? "", s.daysLeft ?? ""]),
    );
  const clearFilters = () => {
    setPage(1);
    setStatus("All");
    setUnit("All");
    setTypeFilter("All");
    setQuery("");
  };
  const removeDecommissioned = async (sandbox: Sandbox) => {
    const confirmed = window.confirm(
      `Permanently remove ${sandbox.name} and its portal history? This is only available after Azure cleanup has completed; it does not delete Azure resources.`
    );
    if (confirmed && await deleteDecommissioned(sandbox.id)) {
      toast(`Removed ${sandbox.name} from the portal.`, "success");
    }
  };

  return (
    <section className="border border-border bg-surface shadow-card">
      <div className="border-b border-border px-6 pt-2">
        <Tabs
          tabs={tabs}
          value={status}
          onChange={(value) => {
            setPage(1);
            setStatus(value);
          }}
          label="Sandbox status"
        />
      </div>

      <div className="flex flex-wrap items-end gap-4 border-b border-border px-6 py-4">
        <div className="relative w-full sm:w-72">
          <Search size={16} className="absolute top-1/2 left-3 -translate-y-1/2 text-muted" aria-hidden="true" />
          <input
            value={query}
            onChange={(e) => {
              setPage(1);
              setQuery(e.target.value);
            }}
            placeholder="Search name, ID or requestor..."
            aria-label="Search sandboxes"
            className="w-full border border-border bg-background py-2.5 pr-4 pl-9 text-sm text-foreground placeholder:text-muted focus:border-accent focus:outline-none"
          />
        </div>

        <label className="flex flex-col gap-1.5 text-xs font-medium text-muted">
          Business unit
          <select
            className={selectCls}
            value={unit}
            onChange={(e) => {
              setPage(1);
              setUnit(e.target.value);
            }}
          >
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
            onChange={(e) => {
              setPage(1);
              setTypeFilter(e.target.value as TypeFilter);
            }}
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

        <button
          onClick={exportCsv}
          disabled={rows.length === 0}
          title={`Download the ${rows.length} sandbox${rows.length === 1 ? "" : "es"} currently shown as a CSV file`}
          className="ml-auto inline-flex items-center gap-2 border border-border bg-background px-4 py-2.5 text-sm font-medium text-foreground transition hover:border-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Download size={16} aria-hidden="true" />
          Export CSV
        </button>
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
              {visibleRows.map((s) => {
                const pct = usedPct(s);
                const noSpend = s.status === "Pending" || s.status === "Rejected";
                return (
                  <tr key={s.id}>
                    <td className="px-6 py-4">
                      <Link href={`/admin/sandboxes/${encodeURIComponent(s.id)}`} className="font-mono text-accent hover:underline">{s.name}</Link>
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
                      {s.status === "Decommissioned" ? (
                        <button
                          onClick={() => void removeDecommissioned(s)}
                          className="inline-flex items-center gap-2 text-sm text-red-600 hover:text-red-700 dark:text-red-400"
                          title="Permanently remove this decommissioned record and its portal history"
                        >
                          <Trash2 size={16} />
                          Delete record
                        </button>
                      ) : s.cleanupFlagged ? (
                        <p className="text-xs text-muted">Flagged; eligible {s.cleanupEligibleOn}</p>
                      ) : s.cleanupAvailable ? (
                        <button onClick={() => setCleanup(s)} className="inline-flex items-center gap-2 text-sm text-accent">
                          <Flag size={16} />
                          Flag cleanup
                        </button>
                      ) : s.status === "Expired" && s.cleanupEligibleOn ? (
                        <p className="text-xs text-muted">
                          {s.cleanupEligibleOn > new Date().toISOString().slice(0, 10)
                            ? `Available after ${s.cleanupEligibleOn}`
                            : "Resolve pending operations before cleanup"}
                        </p>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {!isLoading && rows.length > 0 && (
        <div className="flex items-center justify-between border-t border-border px-6 py-4">
          <p className="text-sm text-muted">
            Showing {(currentPage - 1) * PAGE_SIZE + 1}-{Math.min(currentPage * PAGE_SIZE, rows.length)} of {rows.length}
          </p>
          <nav className="flex items-center gap-2" aria-label="Sandbox pagination">
            <button
              type="button"
              onClick={() => setPage(currentPage - 1)}
              disabled={currentPage === 1}
              className="border border-border px-3 py-2 text-sm text-foreground disabled:cursor-not-allowed disabled:opacity-50"
            >
              Previous
            </button>
            <span className="px-2 text-sm text-muted">Page {currentPage} of {pageCount}</span>
            <button
              type="button"
              onClick={() => setPage(currentPage + 1)}
              disabled={currentPage === pageCount}
              className="border border-border px-3 py-2 text-sm text-foreground disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          </nav>
        </div>
      )}
      <ReasonDialog
        open={cleanup !== null}
        onClose={() => setCleanup(null)}
        title="Flag sandbox for cleanup"
        confirmLabel="Flag cleanup"
        intro={cleanup && <>Flag <span className="font-mono">{cleanup.name}</span> for resource deletion after its expiry date and {configuration?.expiryGraceDays ?? 7} days of grace. Pending extensions must be resolved first.</>}
        onConfirm={async (reason) => { if (cleanup && await flagCleanup(cleanup.id, reason)) setCleanup(null); }}
      />
    </section>
  );
}
