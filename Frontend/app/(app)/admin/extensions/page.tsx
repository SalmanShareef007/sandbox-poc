"use client";

import { useState } from "react";
import { CalendarClock, CircleCheck, X } from "lucide-react";
import Modal from "@/components/ui/Modal";
import Tabs, { type TabItem } from "@/components/ui/Tabs";
import EmptyState from "@/components/ui/EmptyState";
import Skeleton from "@/components/ui/Skeleton";
import ReasonDialog from "@/components/admin/ReasonDialog";
import { sameEmail, SELF_APPROVAL_MESSAGE } from "@/components/admin/format";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import { useToast } from "@/components/providers/ToastProvider";
import { useAuth } from "@/hooks/useAuth";
import { addDays, formatDemoDate, parseDemoDate } from "@/lib/dates";
import type { ExtensionRequest, ExtensionStatus } from "@/lib/demoData";

type TabKey = "pending" | "decided";

const statusStyles: Record<ExtensionStatus, string> = {
  Pending: "border-accent/30 bg-accent/10 text-accent-dark dark:text-accent-light",
  Approved: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  Rejected: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400",
};

const btnPrimary =
  "bg-accent-gradient inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white shadow-accent transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50";
const btnSecondary =
  "inline-flex items-center gap-2 border border-border bg-surface-2 px-5 py-2.5 text-sm font-medium text-foreground transition hover:border-accent disabled:cursor-not-allowed disabled:opacity-50";

const extendedExpiry = (expiry: string | null | undefined, days: number) =>
  expiry ? formatDemoDate(addDays(parseDemoDate(expiry), days)) : undefined;

export default function ExtensionsPage() {
  const { adminRequests, extensionRequests, isLoading, approveExtension, rejectExtension } =
    useSandboxes();
  const { toast } = useToast();
  const { account } = useAuth();

  const [tab, setTab] = useState<TabKey>("pending");
  const [approving, setApproving] = useState<ExtensionRequest | null>(null);
  const [rejecting, setRejecting] = useState<ExtensionRequest | null>(null);

  const pending = extensionRequests.filter((e) => e.status === "Pending");
  const decided = extensionRequests.filter((e) => e.status !== "Pending");
  const rows = tab === "pending" ? pending : decided;

  const tabs: TabItem<TabKey>[] = [
    { value: "pending", label: "Pending", count: pending.length },
    { value: "decided", label: "Decided", count: decided.length },
  ];

  const expiryFor = (sandboxId: string) => adminRequests.find((s) => s.id === sandboxId)?.expiry;

  return (
    <section className="border border-border bg-surface shadow-card">
      <div className="border-b border-border px-6 pt-2">
        <Tabs tabs={tabs} value={tab} onChange={setTab} label="Extension status" />
      </div>

      {isLoading ? (
        <div className="space-y-4 p-6" aria-busy="true" aria-label="Loading extension requests">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-36" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={CalendarClock}
          title={tab === "pending" ? "No pending extensions" : "No decided extensions"}
          text={
            tab === "pending"
              ? "There are no extension requests waiting for review."
              : "Approved and rejected extension requests will appear here."
          }
        />
      ) : (
        <div className="space-y-4 p-6">
          {rows.map((e) => {
            const isOwn = sameEmail(e.requestorEmail, account?.username);
            const currentExpiry = expiryFor(e.sandboxId);
            const newExpiry = extendedExpiry(currentExpiry, e.extraDays);

            return (
              <article
                key={e.id}
                className="border border-border bg-surface-2/40"
                aria-labelledby={`ext-${e.id}`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-5 py-4">
                  <div>
                    <h3 id={`ext-${e.id}`} className="font-mono text-foreground">
                      {e.sandboxName}
                    </h3>
                    <p className="mt-0.5 text-xs text-muted">
                      {e.id} · requested {e.requestedOn}
                    </p>
                  </div>
                  <span className={`border px-2.5 py-0.5 text-xs font-medium ${statusStyles[e.status]}`}>
                    {e.status}
                  </span>
                </div>

                <div className="space-y-4 p-5">
                  <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                    <div>
                      <dt className="text-xs text-muted">Requestor</dt>
                      <dd className="mt-0.5 text-foreground">
                        {e.requestorName}
                        <span className="block text-xs text-muted">{e.requestorEmail}</span>
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted">Extra days</dt>
                      <dd className="mt-0.5 text-foreground">+{e.extraDays} days</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted">
                        {e.status === "Approved" ? "Expiry (extended)" : "Current expiry"}
                      </dt>
                      <dd className="mt-0.5 text-foreground">{currentExpiry ?? "—"}</dd>
                    </div>
                    {e.status === "Pending" && (
                      <div>
                        <dt className="text-xs text-muted">New expiry if approved</dt>
                        <dd className="mt-0.5 text-emerald-700 dark:text-emerald-400">
                          {newExpiry ?? "—"}
                        </dd>
                      </div>
                    )}
                  </dl>

                  <div className="text-sm">
                    <p className="text-xs text-muted">Reason</p>
                    <p className="mt-0.5 text-foreground">{e.reason}</p>
                  </div>

                  {e.status === "Rejected" && e.decisionReason && (
                    <div className="border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-400">
                      <p className="font-semibold">Rejection reason</p>
                      <p className="mt-1">{e.decisionReason}</p>
                    </div>
                  )}
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4">
                  {e.status === "Pending" ? (
                    <>
                      <p className="text-sm text-muted">{isOwn ? SELF_APPROVAL_MESSAGE : ""}</p>
                      <div className="flex gap-3">
                        <button onClick={() => setRejecting(e)} disabled={isOwn} className={btnSecondary}>
                          <X size={16} aria-hidden="true" />
                          Reject
                        </button>
                        <button onClick={() => setApproving(e)} disabled={isOwn} className={btnPrimary}>
                          <CircleCheck size={16} aria-hidden="true" />
                          Approve
                        </button>
                      </div>
                    </>
                  ) : (
                    <p className="text-sm text-muted">
                      {e.status} by <span className="text-foreground">{e.decisionBy ?? "—"}</span>
                    </p>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}

      <Modal open={approving !== null} onClose={() => setApproving(null)} title="Approve extension">
        {approving && (
          <>
            <div className="space-y-3 p-6 text-sm text-muted">
              <p>
                Extend <span className="font-mono text-foreground">{approving.sandboxName}</span> by{" "}
                <span className="text-foreground">{approving.extraDays} days</span> for{" "}
                {approving.requestorName}?
              </p>
              <p>
                New expiry:{" "}
                <span className="text-foreground">
                  {extendedExpiry(expiryFor(approving.sandboxId), approving.extraDays) ?? "—"}
                </span>
              </p>
            </div>
            <div className="flex justify-end gap-3 border-t border-border px-6 py-4">
              <button onClick={() => setApproving(null)} className={btnSecondary}>
                Cancel
              </button>
              <button
                onClick={async () => {
                  if (await approveExtension(approving.id)) {
                    toast(
                      `Extended ${approving.sandboxName} by ${approving.extraDays} days. Terraform is updating the expiry tag.`,
                      "success"
                    );
                    setApproving(null);
                  }
                }}
                className={btnPrimary}
              >
                Confirm
              </button>
            </div>
          </>
        )}
      </Modal>

      <ReasonDialog
        open={rejecting !== null}
        onClose={() => setRejecting(null)}
        title="Reject extension"
        confirmLabel="Reject extension"
        intro={
          rejecting && (
            <>
              Reject the {rejecting.extraDays}-day extension for{" "}
              <span className="font-mono text-foreground">{rejecting.sandboxName}</span>.{" "}
              {rejecting.requestorName} will see your reason in the sandbox timeline.
            </>
          )
        }
        onConfirm={async (reason) => {
          if (!rejecting) return;
          if (await rejectExtension(rejecting.id, reason)) {
            toast(`Extension rejected for ${rejecting.sandboxName}.`, "info");
            setRejecting(null);
          }
        }}
      />
    </section>
  );
}
