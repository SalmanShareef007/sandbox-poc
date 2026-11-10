"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  Box,
  CalendarPlus,
  Copy,
  ExternalLink,
  Loader,
  Power,
} from "lucide-react";
import StatusBadge from "@/components/ui/StatusBadge";
import Modal from "@/components/ui/Modal";
import Skeleton from "@/components/ui/Skeleton";
import SpendChart from "@/components/ui/SpendChart";
import ExtensionDialog from "@/components/sandbox/ExtensionDialog";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import { useToast } from "@/components/providers/ToastProvider";
import type { HistoryEntry, HistoryStatus, Sandbox } from "@/lib/types";
import { hasComparableCost, useMoney, usedPct } from "@/components/admin/format";


function barColor(pct: number) {
  if (pct >= 90) return "bg-red-500";
  if (pct >= 75) return "bg-amber-500";
  return "bg-emerald-500";
}

type StepState = "done" | "failed" | "pending" | "skipped";

interface Step {
  label: HistoryStatus;
  state: StepState;
  entry?: HistoryEntry;
}

const BASE_STEPS: HistoryStatus[] = ["Submitted", "Approved", "Rejected", "Provisioning", "Active"];
const FAILED_EVENTS: HistoryStatus[] = ["Failed", "Extension rejected", "Decommission rejected"];

function buildTimeline(history: HistoryEntry[], imported = false): Step[] {
  const find = (status: HistoryStatus) => history.find((h) => h.status === status);
  const rejected = find("Rejected");
  // Imported sandboxes were provisioned before the portal, so earlier steps don't apply.
  const preState = (status: HistoryStatus): StepState =>
    imported ? "skipped" : find(status) ? "done" : "pending";

  const steps: Step[] = [
    { label: "Submitted", state: preState("Submitted"), entry: find("Submitted") },
    rejected
      ? { label: "Rejected", state: "failed", entry: rejected }
      : { label: "Approved", state: preState("Approved"), entry: find("Approved") },
    {
      label: "Provisioning",
      state: rejected ? "skipped" : preState("Provisioning"),
      entry: find("Provisioning"),
    },
    {
      label: "Active",
      state: rejected ? "skipped" : find("Active") ? "done" : "pending",
      entry: find("Active"),
    },
  ];

  const events = history
    .filter((h) => !BASE_STEPS.includes(h.status))
    .map<Step>((entry) => ({
      label: entry.status,
      state: FAILED_EVENTS.includes(entry.status) ? "failed" : "done",
      entry,
    }));

  return [...steps, ...events];
}

const dotStyles: Record<StepState, string> = {
  done: "bg-emerald-500",
  failed: "bg-red-500",
  pending: "border border-border bg-surface-2",
  skipped: "border border-border bg-background",
};

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border border-border bg-surface shadow-card">
      <div className="border-b border-border px-6 py-4">
        <h3 className="font-semibold text-foreground">{title}</h3>
      </div>
      <div className="p-6">{children}</div>
    </section>
  );
}

function BackLink() {
  return (
    <Link
      href="/sandboxes"
      className="inline-flex items-center gap-2 text-sm text-muted transition hover:text-foreground"
    >
      <ArrowLeft size={16} />
      Back to sandboxes
    </Link>
  );
}

const actionCls =
  "flex w-full items-center gap-3 border border-border bg-surface-2 px-4 py-3 text-left text-sm font-medium text-foreground transition hover:border-accent disabled:cursor-not-allowed disabled:opacity-50";

function DecommissionForm({ sandbox, onClose }: { sandbox: Sandbox; onClose: () => void }) {
  const { decommissionRequested } = useSandboxes();
  const { toast } = useToast();
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const valid = reason.trim().length > 0;

  const onConfirm = async () => {
    if (!valid || submitting) return;
    setSubmitting(true);
    const ok = await decommissionRequested(sandbox.id, reason.trim());
    setSubmitting(false);
    if (!ok) return;
    toast(`Decommission requested for ${sandbox.name}`, "success");
    onClose();
  };

  return (
    <>
      <div className="space-y-4 p-6">
        <p className="text-sm text-muted">
          This asks IT Administrators to tear down{" "}
          <span className="font-mono text-foreground">{sandbox.name}</span> and all of its
          resources. This cannot be undone once approved.
        </p>
        <div>
          <label
            htmlFor="decommission-reason"
            className="mb-2 block text-sm font-medium text-foreground"
          >
            Reason <span className="text-red-700 dark:text-red-400">*</span>
          </label>
          <textarea
            id="decommission-reason"
            rows={3}
            required
            aria-required="true"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Proof of concept finished"
            className="w-full border border-border bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted focus:border-accent focus:outline-none"
          />
        </div>
      </div>
      <div className="flex justify-end gap-3 border-t border-border px-6 py-4">
        <button
          onClick={onClose}
          className="border border-border bg-surface-2 px-6 py-2.5 text-sm font-medium text-foreground transition hover:border-accent"
        >
          Cancel
        </button>
        <button
          onClick={onConfirm}
          disabled={!valid || submitting}
          className="bg-red-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Submitting…" : "Request decommission"}
        </button>
      </div>
    </>
  );
}

function ActionsCard({ sandbox: s }: { sandbox: Sandbox }) {
  const { toast } = useToast();
  const [decommissioning, setDecommissioning] = useState(false);
  const idLabel = s.type === "Subscription" ? "subscription" : "resource group";

  const copyId = async () => {
    if (!s.resourceId) return;
    try {
      await navigator.clipboard.writeText(s.resourceId);
      toast(`Copied ${idLabel} ID to clipboard`, "success");
    } catch {
      toast("Couldn't copy to clipboard", "error");
    }
  };

  return (
    <Card title="Actions">
      <div className="space-y-3">
        {s.resourceId && (
          <p className="truncate font-mono text-xs text-muted" title={s.resourceId}>
            {s.resourceId}
          </p>
        )}
        <button onClick={copyId} disabled={!s.resourceId} className={actionCls}>
          <Copy size={16} className="text-accent" />
          Copy ID
        </button>
        <a
          href={
            s.resourceId
              ? `https://portal.azure.com/#@/resource${s.resourceId}`
              : "https://portal.azure.com"
          }
          target="_blank"
          rel="noopener noreferrer"
          className={actionCls}
        >
          <ExternalLink size={16} className="text-accent" />
          Open in Azure portal
        </a>
        <button
          onClick={() => setDecommissioning(true)}
          disabled={!!s.decommissionPending || !!s.operationInProgress}
          className={actionCls}
        >
          <Power size={16} className="text-red-700 dark:text-red-400" />
          {s.decommissionPending ? "Decommission requested · awaiting approval" : "Request decommission"}
        </button>
      </div>

      <Modal
        open={decommissioning}
        onClose={() => setDecommissioning(false)}
        title="Request decommission"
      >
        <DecommissionForm sandbox={s} onClose={() => setDecommissioning(false)} />
      </Modal>
    </Card>
  );
}

export default function SandboxDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { sandboxes, isLoading } = useSandboxes();
  const [extending, setExtending] = useState(false);

  const sandbox = sandboxes.find((s) => s.id === decodeURIComponent(id));

  if (!sandbox && isLoading) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading sandbox">
        <BackLink />
        <Skeleton className="h-10 w-80 max-w-full" />
        <Skeleton className="h-96" />
      </div>
    );
  }

  if (!sandbox) {
    return (
      <div className="space-y-6">
        <BackLink />
        <div className="mx-auto max-w-lg border border-border bg-surface p-10 text-center shadow-card">
          <Box size={40} className="mx-auto text-muted" />
          <h2 className="mt-4 text-2xl font-bold text-foreground">Sandbox not found</h2>
          <p className="mt-2 text-muted">
            We couldn&apos;t find a sandbox with ID{" "}
            <span className="font-mono text-foreground">{decodeURIComponent(id)}</span>. It may have
            been removed, or the link is incorrect.
          </p>
        </div>
      </div>
    );
  }

  return <SandboxDetail sandbox={sandbox} extending={extending} setExtending={setExtending} />;
}

function SandboxDetail({
  sandbox: s,
  extending,
  setExtending,
}: {
  sandbox: Sandbox;
  extending: boolean;
  setExtending: (open: boolean) => void;
}) {
  const money = useMoney();
  const canExtend =
    (s.status === "Active" || s.status === "Expiring" || s.status === "Expired") && !s.operationInProgress && !s.failedOperation;
  const showActions = s.status === "Active" || s.status === "Expiring" || s.status === "Expired";
  const inProgress =
    s.status === "Provisioning" || s.status === "Decommissioning" || !!s.operationInProgress;
  const noSpend = s.status === "Pending" || s.status === "Rejected";
  const pct = usedPct(s);
  const timeline = buildTimeline(s.history, s.imported);

  const details: [string, React.ReactNode][] = [
    ["Type", s.type],
    ["Region", s.region],
    ["Access role", s.role ?? "Contributor"],
    ["Business unit", s.businessUnit],
    ["Cost centre", s.costCenter],
    ["Owner", s.owner],
    ["Manager", s.managerEmail || "Not recorded"],
    ["Cleanup", s.cleanupFlagged ? `Flagged; eligible from ${s.cleanupEligibleOn}` : "Administrator decision required"],
    ["Pending expiry change", s.pendingExpiry ? `${s.pendingExpiry} (not yet applied)` : "None"],
    [
      "Expiry",
      s.expiry ? (
        <>
          {s.expiry}{" "}
          <span
            className={
              s.status === "Expiring" ? "text-amber-700 dark:text-amber-400" : "text-muted"
            }
          >
            ({s.daysLeft} days left)
          </span>
        </>
      ) : (
        <span className="text-muted">—</span>
      ),
    ],
  ];

  return (
    <div className="space-y-6">
      <BackLink />

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="font-mono text-2xl font-bold text-foreground">{s.name}</h2>
            <StatusBadge status={s.status} />
          </div>
          <p className="mt-1 text-muted">
            {s.id} · {s.workload}
          </p>
        </div>

        {canExtend && (
          <button
            onClick={() => setExtending(true)}
            className="bg-accent-gradient flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white shadow-accent transition hover:brightness-110"
          >
            <CalendarPlus size={16} />
            Request extension
          </button>
        )}
      </div>

      {s.status === "Rejected" && s.rejectionReason && (
        <div className="flex items-start gap-3 border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-700 dark:text-red-400">
          <AlertTriangle size={18} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">Request rejected</p>
            <p className="mt-1">{s.rejectionReason}</p>
          </div>
        </div>
      )}

      {(s.status === "Failed" || s.failedOperation) && s.provisioningNote && (
        <div className="flex items-start gap-3 border border-red-500/30 bg-red-500/10 px-5 py-4 text-sm text-red-700 dark:text-red-400">
          <AlertTriangle size={18} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">Terraform run failed · IT Administrators can retry it</p>
            <p className="mt-1 break-words">{s.provisioningNote}</p>
          </div>
        </div>
      )}

      {inProgress && (
        <div className="flex items-center gap-3 border border-accent/30 bg-accent/10 px-5 py-4 text-sm text-accent-dark dark:text-accent-light">
          <Loader size={18} className="shrink-0 animate-spin" />
          <p>
            {s.status === "Decommissioning"
              ? "Decommissioning: the resource group and its resources are being deleted."
              : s.operationInProgress === "extension"
                ? "Applying your extension: Terraform is updating the expiry date."
                : "Provisioning: Terraform is creating your resource group. This usually takes a few minutes."}
          </p>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
        <div className="space-y-6">
          <Card title="Details">
            <dl className="grid gap-x-8 gap-y-4 text-sm sm:grid-cols-2">
              {details.map(([k, v]) => (
                <div key={k}>
                  <dt className="text-muted">{k}</dt>
                  <dd className="mt-1 break-words text-foreground">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>

          <Card title="Budget">
            {noSpend ? (
              <p className="text-sm text-muted">{money(s.budget)} requested · no spend yet</p>
            ) : !hasComparableCost(s) ? (
              <p className="text-sm text-muted">Cost data unavailable in the budget currency.</p>
            ) : (
              <>
                <div className="flex items-end justify-between">
                  <p className="text-3xl font-bold text-foreground">{money(s.spent, 2)}</p>
                  <p className="text-sm text-muted">of {money(s.budget)}</p>
                </div>
                <div className="mt-4 h-2 overflow-hidden bg-background">
                  <div
                    className={`h-full ${barColor(pct)}`}
                    style={{ width: `${Math.min(pct, 100)}%` }}
                  />
                </div>
                <p className="mt-2 text-xs text-muted">
                  {pct}% used · alerts at 75 / 90 / 100%{s.costStatus === "stale" ? " · refresh delayed" : ""}
                </p>
              </>
            )}
          </Card>

          {hasComparableCost(s) && s.spendHistory && s.spendHistory.length > 0 && (
            <Card title="Spend over time">
              <SpendChart values={s.spendHistory} budget={s.budget} />
            </Card>
          )}

          <Card title="Tags">
            <div className="flex flex-wrap gap-2">
              {Object.entries(s.tags).map(([k, v]) => (
                <span
                  key={k}
                  className="border border-border bg-surface-2 px-2.5 py-1 text-xs text-foreground"
                >
                  <span className="font-semibold">{k}:</span> {v}
                </span>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          {showActions && <ActionsCard sandbox={s} />}

          <Card title="Status timeline">
          <ol className="space-y-5">
            {timeline.map((step, i) => (
              <li key={`${step.label}-${i}`} className="flex gap-3">
                <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 ${dotStyles[step.state]}`} />
                <div className="min-w-0">
                  <p
                    className={`text-sm font-semibold ${
                      step.state === "failed"
                        ? "text-red-700 dark:text-red-400"
                        : step.state === "done"
                          ? "text-foreground"
                          : "text-muted"
                    }`}
                  >
                    {step.label}
                  </p>
                  {step.entry ? (
                    <p className="text-xs text-muted">
                      {step.entry.date} · {step.entry.note}
                    </p>
                  ) : (
                    <p className="text-xs text-muted">
                      {step.state === "skipped" ? "Not applicable" : "Waiting"}
                    </p>
                  )}
                </div>
              </li>
            ))}
          </ol>
          </Card>
        </div>
      </div>

      {canExtend && (
        <ExtensionDialog sandbox={s} open={extending} onClose={() => setExtending(false)} />
      )}
    </div>
  );
}
