"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { apiFetch } from "@/lib/api";
import type { SandboxLifecycle } from "@/lib/types";

const statusStyle: Record<string, string> = {
  Pending: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  Approved: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  Completed: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  Rejected: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400",
  Cancelled: "border-border bg-surface-2 text-muted",
};

function Pill({ status }: { status: string }) {
  return (
    <span className={`shrink-0 border px-2 py-0.5 text-xs font-medium ${statusStyle[status] ?? statusStyle.Cancelled}`} title={`Status: ${status}`}>
      {status}
    </span>
  );
}

/** Extension and decommission requests for one sandbox. Reloads when `refreshKey` changes. */
export default function LifecycleHistory({ reference, refreshKey }: { reference: string; refreshKey: number }) {
  const { getApiToken } = useAuth();
  const tokenRef = useRef(getApiToken);
  useEffect(() => {
    tokenRef.current = getApiToken;
  });
  const [data, setData] = useState<SandboxLifecycle | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<SandboxLifecycle>(() => tokenRef.current(), `/sandboxes/${encodeURIComponent(reference)}/lifecycle`)
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load history.");
      });
    return () => {
      cancelled = true;
    };
  }, [reference, refreshKey]);

  if (error && !data) return <p className="text-sm text-red-700 dark:text-red-400">{error}</p>;
  if (!data) return <p className="text-sm text-muted">Loading history…</p>;
  if (!data.extensions.length && !data.decommissions.length) {
    return <p className="text-sm text-muted">No extension or decommission requests yet.</p>;
  }

  return (
    <div className="space-y-5">
      {data.extensions.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold tracking-wider text-muted">EXTENSIONS</p>
          <ul className="divide-y divide-border">
            {data.extensions.map((e) => (
              <li key={e.id} className="flex flex-wrap items-start gap-3 py-3 text-sm">
                <div className="min-w-0 flex-1">
                  <p className="text-foreground">
                    <span className="font-mono">{e.id}</span> · +{e.extraDays} days
                    {e.requestedExpiry ? ` (to ${e.requestedExpiry})` : ""}
                  </p>
                  <p className="mt-0.5 text-xs text-muted">{e.reason}</p>
                  {e.decisionBy && (
                    <p className="mt-0.5 text-xs text-muted">
                      Decided by {e.decisionBy}{e.decisionReason ? `: ${e.decisionReason}` : ""}
                    </p>
                  )}
                </div>
                <span className="text-xs text-muted" title="Date requested">{e.requestedOn}</span>
                <Pill status={e.status} />
              </li>
            ))}
          </ul>
        </div>
      )}
      {data.decommissions.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold tracking-wider text-muted">DECOMMISSION</p>
          <ul className="divide-y divide-border">
            {data.decommissions.map((d) => (
              <li key={d.id} className="flex flex-wrap items-start gap-3 py-3 text-sm">
                <div className="min-w-0 flex-1">
                  <p className="text-foreground">
                    <span className="font-mono">{d.id}</span> · {d.source === "expiry" ? "Raised automatically at expiry" : d.source === "admin-flag" ? "Flagged by an administrator" : `Requested by ${d.requestedBy ?? "user"}`}
                  </p>
                  {d.reason && <p className="mt-0.5 text-xs text-muted">{d.reason}</p>}
                  {d.cleanupEligibleOn && <p className="mt-0.5 text-xs text-muted">Cleanup eligible from {d.cleanupEligibleOn}</p>}
                  {d.decisionBy && (
                    <p className="mt-0.5 text-xs text-muted">
                      Decided by {d.decisionBy}{d.decisionReason ? `: ${d.decisionReason}` : ""}
                    </p>
                  )}
                </div>
                <span className="text-xs text-muted" title="Date requested">{d.requestedOn}</span>
                <Pill status={d.status} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
