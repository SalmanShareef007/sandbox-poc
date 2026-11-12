"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Download, RefreshCw, Search, SearchX } from "lucide-react";
import Skeleton from "@/components/ui/Skeleton";
import EmptyState from "@/components/ui/EmptyState";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/components/providers/ToastProvider";
import { apiFetch } from "@/lib/api";
import { downloadCsv } from "@/lib/csv";
import type { AuditEntry } from "@/lib/types";

const selectCls =
  "border border-border bg-background px-4 py-2.5 text-sm text-foreground focus:border-accent focus:outline-none";

const detailText = (details: Record<string, unknown>) =>
  Object.entries(details ?? {}).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`).join(" · ");

export default function AdminAuditPage() {
  const { getApiToken } = useAuth();
  const { toast } = useToast();
  const tokenRef = useRef(getApiToken);
  useEffect(() => {
    tokenRef.current = getApiToken;
  });

  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [query, setQuery] = useState("");
  const [action, setAction] = useState("All");

  const fetchEntries = useCallback(
    () => apiFetch<AuditEntry[]>(() => tokenRef.current(), "/admin/audit?limit=500"),
    [],
  );

  useEffect(() => {
    let cancelled = false;
    fetchEntries()
      .then((result) => {
        if (!cancelled) setEntries(result);
      })
      .catch((err) => {
        if (!cancelled) toast(err instanceof Error ? err.message : "Could not load the audit log.", "error");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [fetchEntries, toast]);

  const refresh = async () => {
    setRefreshing(true);
    try {
      setEntries(await fetchEntries());
    } catch (err) {
      toast(err instanceof Error ? err.message : "Could not load the audit log.", "error");
    } finally {
      setRefreshing(false);
    }
  };

  const actions = useMemo(() => ["All", ...Array.from(new Set(entries.map((e) => e.action))).sort()], [entries]);
  const q = query.trim().toLowerCase();
  const rows = entries.filter(
    (e) =>
      (action === "All" || e.action === action) &&
      (!q ||
        e.action.toLowerCase().includes(q) ||
        (e.actor ?? "").toLowerCase().includes(q) ||
        (e.resource_id ?? "").toLowerCase().includes(q) ||
        detailText(e.details).toLowerCase().includes(q)),
  );
  const filtersActive = action !== "All" || q !== "";
  const clearFilters = () => {
    setQuery("");
    setAction("All");
  };

  const exportCsv = () =>
    downloadCsv(
      `audit-log-${new Date().toISOString().slice(0, 10)}.csv`,
      ["Time (UTC)", "Actor", "Action", "Resource type", "Resource", "Details"],
      rows.map((e) => [e.timestamp, e.actor ?? "", e.action, e.resource_type ?? "", e.resource_id ?? "", detailText(e.details)]),
    );

  return (
    <section className="border border-border bg-surface shadow-card">
      <div className="flex flex-wrap items-end gap-4 border-b border-border px-6 py-4">
        <div className="relative w-full sm:w-72">
          <Search size={16} className="absolute top-1/2 left-3 -translate-y-1/2 text-muted" aria-hidden="true" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search actor, action, resource..."
            aria-label="Search audit log"
            className="w-full border border-border bg-background py-2.5 pr-4 pl-9 text-sm text-foreground placeholder:text-muted focus:border-accent focus:outline-none"
          />
        </div>

        <label className="flex flex-col gap-1.5 text-xs font-medium text-muted">
          Action
          <select className={selectCls} value={action} onChange={(e) => setAction(e.target.value)}>
            {actions.map((a) => (
              <option key={a} value={a}>{a}</option>
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

        <div className="ml-auto flex gap-3">
          <button
            onClick={() => void refresh()}
            disabled={refreshing}
            title="Reload the latest 500 entries"
            className="inline-flex items-center gap-2 border border-border bg-background px-4 py-2.5 text-sm font-medium text-foreground transition hover:border-accent disabled:opacity-50"
          >
            <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} aria-hidden="true" />
            Refresh
          </button>
          <button
            onClick={exportCsv}
            disabled={rows.length === 0}
            title={`Download the ${rows.length} entries currently shown as a CSV file`}
            className="inline-flex items-center gap-2 border border-border bg-background px-4 py-2.5 text-sm font-medium text-foreground transition hover:border-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download size={16} aria-hidden="true" />
            Export CSV
          </button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-4 p-6" aria-busy="true" aria-label="Loading audit log">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-10" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title="No matching entries"
          text={entries.length ? "Try a different search term or action." : "Actions will appear here as people use the portal."}
          action={filtersActive ? { label: "Clear filters", onClick: clearFilters } : undefined}
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-muted">
                <th scope="col" className="px-6 py-3 font-semibold">Time</th>
                <th scope="col" className="px-6 py-3 font-semibold">Actor</th>
                <th scope="col" className="px-6 py-3 font-semibold">Action</th>
                <th scope="col" className="px-6 py-3 font-semibold">Resource</th>
                <th scope="col" className="px-6 py-3 font-semibold">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((e) => (
                <tr key={e.log_id}>
                  <td className="px-6 py-3 whitespace-nowrap text-muted" title={e.timestamp}>
                    {new Date(e.timestamp).toLocaleString()}
                  </td>
                  <td className="px-6 py-3 text-foreground">{e.actor ?? "—"}</td>
                  <td className="px-6 py-3 font-mono text-xs text-foreground">{e.action}</td>
                  <td className="px-6 py-3">
                    <p className="font-mono text-foreground">{e.resource_id ?? "—"}</p>
                    <p className="mt-0.5 text-xs text-muted">{e.resource_type}</p>
                  </td>
                  <td className="max-w-xs truncate px-6 py-3 text-xs text-muted" title={detailText(e.details)}>
                    {detailText(e.details) || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="border-t border-border px-6 py-3 text-xs text-muted">
        Showing {rows.length} of the latest {entries.length} entries.
      </p>
    </section>
  );
}
