"use client";

import { Suspense, useId, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CircleCheck, ExternalLink, Inbox, Loader, Power, RefreshCw, X } from "lucide-react";
import Modal from "@/components/ui/Modal";
import Tabs, { type TabItem } from "@/components/ui/Tabs";
import StatusBadge from "@/components/ui/StatusBadge";
import EmptyState from "@/components/ui/EmptyState";
import Skeleton from "@/components/ui/Skeleton";
import ReasonDialog from "@/components/admin/ReasonDialog";
import { useMoney, sameEmail, SELF_APPROVAL_MESSAGE } from "@/components/admin/format";
import { useRole } from "@/hooks/useRole";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import { useToast } from "@/components/providers/ToastProvider";
import { useAuth } from "@/hooks/useAuth";
import { parseDemoDate } from "@/lib/dates";
import type { Sandbox, SandboxStatus } from "@/lib/types";

type TabKey = "pending" | "decommission" | "provisioning" | "failed" | "decided";

const DECIDED: SandboxStatus[] = ["Active", "Expiring", "Expired", "Rejected", "Decommissioned"];

const matchers: Record<TabKey, (s: Sandbox) => boolean> = {
  pending: (s) => s.status === "Pending",
  decommission: (s) => !!s.decommissionPending && !s.cleanupFlagged,
  provisioning: (s) =>
    s.status === "Provisioning" || s.status === "Decommissioning" || !!s.operationInProgress,
  failed: (s) => s.status === "Failed" || !!s.failedOperation,
  decided: (s) => DECIDED.includes(s.status),
};

const tabLabels: Record<TabKey, string> = {
  pending: "Pending",
  decommission: "Decommission",
  provisioning: "In progress",
  failed: "Failed",
  decided: "Decided",
};

const emptyText: Record<TabKey, string> = {
  pending: "There are no requests waiting for approval.",
  decommission: "There are no decommission requests waiting for approval.",
  provisioning: "No Terraform runs are in progress right now.",
  failed: "No Terraform runs have failed.",
  decided: "No requests have been decided yet.",
};

const retryLabels: Record<NonNullable<Sandbox["failedOperation"]>, string> = {
  provision: "Retry provisioning",
  extension: "Retry extension",
  decommission: "Retry decommission",
};

const isTabKey = (value: string | null): value is TabKey =>
  value !== null && value in matchers;

const btnPrimary =
  "bg-accent-gradient px-5 py-2.5 text-sm font-medium text-white shadow-accent transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50";
const btnSecondary =
  "border border-border bg-surface-2 px-5 py-2.5 text-sm font-medium text-foreground transition hover:border-accent disabled:cursor-not-allowed disabled:opacity-50";

export default function ApprovalsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96" />}>
      <Approvals />
    </Suspense>
  );
}

function Approvals() {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get("tab");
  const {
    adminRequests: all,
    isLoading,
    rejectRequest,
    retryProvisioning,
    approveDecommission,
    rejectDecommission,
  } = useSandboxes();
  const { toast } = useToast();
  const { account } = useAuth();

  const [tab, setTab] = useState<TabKey>(isTabKey(initialTab) ? initialTab : "pending");
  const [approving, setApproving] = useState<Sandbox | null>(null);
  const [rejecting, setRejecting] = useState<Sandbox | null>(null);
  const [decommissioning, setDecommissioning] = useState<Sandbox | null>(null);
  const [keeping, setKeeping] = useState<Sandbox | null>(null);
  const [busy, setBusy] = useState(false);

  const tabs: TabItem<TabKey>[] = (Object.keys(matchers) as TabKey[]).map((key) => ({
    value: key,
    label: tabLabels[key],
    count: all.filter(matchers[key]).length,
  }));

  const rows = all.filter(matchers[tab]);
  if (tab === "pending") {
    rows.sort(
      (a, b) =>
        parseDemoDate(a.requestedOn ?? "").getTime() - parseDemoDate(b.requestedOn ?? "").getTime()
    );
  }

  const onRetry = async (s: Sandbox) => {
    if (await retryProvisioning(s.id)) toast(`Terraform run restarted for ${s.name}`, "info");
  };

  const onDecommission = async () => {
    if (!decommissioning || busy) return;
    setBusy(true);
    const ok = await approveDecommission(decommissioning.id);
    setBusy(false);
    if (!ok) return;
    toast(`Cleanup flagged for ${decommissioning.name}.`, "info");
    setDecommissioning(null);
  };

  return (
    <section className="border border-border bg-surface shadow-card">
      <div className="border-b border-border px-6 pt-2">
        <Tabs tabs={tabs} value={tab} onChange={setTab} label="Request status" />
      </div>

      {isLoading ? (
        <div className="space-y-4 p-6" aria-busy="true" aria-label="Loading requests">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState icon={Inbox} title={`No ${tabLabels[tab].toLowerCase()} requests`} text={emptyText[tab]} />
      ) : (
        <div className="space-y-4 p-6">
          {rows.map((s) => (
            <RequestCard
              key={s.id}
              sandbox={s}
              isOwn={sameEmail(s.requestorEmail, account?.username)}
              onApprove={() => setApproving(s)}
              onReject={() => setRejecting(s)}
              onRetry={() => onRetry(s)}
              onApproveDecommission={() => setDecommissioning(s)}
              onRejectDecommission={() => setKeeping(s)}
            />
          ))}
        </div>
      )}

      <Modal open={approving !== null} onClose={() => setApproving(null)} title="Approve request">
        {approving && <ApproveForm sandbox={approving} onClose={() => setApproving(null)} />}
      </Modal>

      <Modal
        open={decommissioning !== null}
        onClose={() => setDecommissioning(null)}
        title="Approve cleanup"
      >
        {decommissioning && (
          <>
            <div className="space-y-3 p-6 text-sm text-muted">
              <p>
                Flag{" "}
                <span className="font-mono text-foreground">{decommissioning.name}</span> and every
                resource inside it for cleanup for {decommissioning.requestorName}?
              </p>
              <p>
                The budget and resource group are deleted, then the sandbox is removed from Terraform
                state when eligible after the expiry grace period. Pending extensions block cleanup. Deletion cannot be undone.
              </p>
            </div>
            <div className="flex justify-end gap-3 border-t border-border px-6 py-4">
              <button onClick={() => setDecommissioning(null)} className={btnSecondary}>
                Cancel
              </button>
              <button
                onClick={onDecommission}
                disabled={busy}
                className="bg-red-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? "Flagging…" : "Flag cleanup"}
              </button>
            </div>
          </>
        )}
      </Modal>

      <ReasonDialog
        open={keeping !== null}
        onClose={() => setKeeping(null)}
        title="Reject decommission"
        confirmLabel="Keep sandbox"
        intro={
          keeping && (
            <>
              Keep <span className="font-mono text-foreground">{keeping.name}</span> running. The
              reason is shown in the sandbox timeline.
            </>
          )
        }
        onConfirm={async (reason) => {
          if (!keeping) return;
          if (await rejectDecommission(keeping.id, reason)) {
            toast(`Decommission rejected. ${keeping.name} stays active.`, "info");
            setKeeping(null);
          }
        }}
      />

      <ReasonDialog
        open={rejecting !== null}
        onClose={() => setRejecting(null)}
        title="Reject request"
        confirmLabel="Reject request"
        intro={
          rejecting && (
            <>
              Reject <span className="font-mono text-foreground">{rejecting.name}</span> requested by{" "}
              {rejecting.requestorName}. They will see your reason on the sandbox page.
            </>
          )
        }
        onConfirm={async (reason) => {
          if (!rejecting) return;
          if (await rejectRequest(rejecting.id, reason)) {
            toast(`Rejected ${rejecting.name}. ${rejecting.requestorName} will see the reason.`, "info");
            setRejecting(null);
          }
        }}
      />
    </section>
  );
}

function RequestCard({
  sandbox: s,
  isOwn,
  onApprove,
  onReject,
  onRetry,
  onApproveDecommission,
  onRejectDecommission,
}: {
  sandbox: Sandbox;
  isOwn: boolean;
  onApprove: () => void;
  onReject: () => void;
  onRetry: () => void;
  onApproveDecommission: () => void;
  onRejectDecommission: () => void;
}) {
  const money = useMoney();
  const details: [string, React.ReactNode][] = [
    ["Type", s.type],
    [
      "Requestor",
      <>
        {s.requestorName}
        <span className="block text-xs text-muted">{s.requestorEmail}</span>
      </>,
    ],
    ["Business unit", s.businessUnit],
    ["Cost centre", s.costCenter],
    ["Manager", s.managerEmail || "Not recorded"],
    ["Workload", s.workload],
    ["Region", s.region],
    ["Access role", s.role ?? "Contributor"],
    ["Requested budget", money(s.budget)],
    ["Duration", s.durationDays ? `${s.durationDays} days` : "—"],
    ["Requested", s.requestedOn ?? "—"],
  ];

  return (
    <article className="border border-border bg-surface-2/40" aria-labelledby={`req-${s.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-5 py-4">
        <div>
          <h3 id={`req-${s.id}`} className="font-mono text-foreground">
            {s.name}
          </h3>
          <p className="mt-0.5 text-xs text-muted">{s.id}</p>
        </div>
        <StatusBadge status={s.status} />
      </div>

      <div className="space-y-4 p-5">
        <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {details.map(([k, v]) => (
            <div key={k}>
              <dt className="text-xs text-muted">{k}</dt>
              <dd className="mt-0.5 break-words text-foreground">{v}</dd>
            </div>
          ))}
        </dl>

        <div className="space-y-3 text-sm">
          <div>
            <p className="text-xs text-muted">Description</p>
            <p className="mt-0.5 text-foreground">{s.description}</p>
          </div>
          <div>
            <p className="text-xs text-muted">Business justification</p>
            <p className="mt-0.5 text-foreground">{s.justification}</p>
          </div>
        </div>

        {(s.status === "Failed" || s.failedOperation) && s.provisioningNote && (
          <div className="border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-400">
            {s.provisioningNote}
          </div>
        )}

        {s.decommissionPending && (
          <div className="border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-700 dark:text-amber-400">
            <p className="font-semibold">
              Decommission requested{s.decommissionRequestedBy ? ` by ${s.decommissionRequestedBy}` : ""}
            </p>
            {s.decommissionReason && <p className="mt-1">{s.decommissionReason}</p>}
          </div>
        )}

        {s.status === "Rejected" && s.decisionReason && (
          <div className="border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-400">
            <p className="font-semibold">Rejection reason</p>
            <p className="mt-1">{s.decisionReason}</p>
          </div>
        )}
      </div>

      <CardFooter
        sandbox={s}
        isOwn={isOwn}
        onApprove={onApprove}
        onReject={onReject}
        onRetry={onRetry}
        onApproveDecommission={onApproveDecommission}
        onRejectDecommission={onRejectDecommission}
      />
    </article>
  );
}

function PipelineLink({ url }: { url?: string }) {
  if (!url) return null;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 text-sm font-medium text-accent hover:text-accent-light"
    >
      View pipeline run
      <ExternalLink size={14} aria-hidden="true" />
    </a>
  );
}

function CardFooter({
  sandbox: s,
  isOwn,
  onApprove,
  onReject,
  onRetry,
  onApproveDecommission,
  onRejectDecommission,
}: {
  sandbox: Sandbox;
  isOwn: boolean;
  onApprove: () => void;
  onReject: () => void;
  onRetry: () => void;
  onApproveDecommission: () => void;
  onRejectDecommission: () => void;
}) {
  const footerCls =
    "flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4";

  if (s.status === "Pending") {
    return (
      <div className={footerCls}>
        <p className="text-sm text-muted">{isOwn ? SELF_APPROVAL_MESSAGE : ""}</p>
        <div className="flex gap-3">
          <button onClick={onReject} disabled={isOwn} className={`${btnSecondary} inline-flex items-center gap-2`}>
            <X size={16} aria-hidden="true" />
            Reject
          </button>
          <button onClick={onApprove} disabled={isOwn} className={`${btnPrimary} inline-flex items-center gap-2`}>
            <CircleCheck size={16} aria-hidden="true" />
            Approve
          </button>
        </div>
      </div>
    );
  }

  if (s.status === "Provisioning" || s.status === "Decommissioning" || s.operationInProgress) {
    const label =
      s.status === "Decommissioning"
        ? "Decommissioning: deleting resource group"
        : s.operationInProgress === "extension"
          ? "Terraform apply running: updating expiry"
          : "Terraform apply running";
    return (
      <div className={footerCls}>
        <p className="inline-flex items-center gap-2 text-sm text-foreground">
          <Loader size={16} className="animate-spin text-accent" aria-hidden="true" />
          {label}
        </p>
        <PipelineLink url={s.pipelineRunUrl} />
      </div>
    );
  }

  if (s.decommissionPending) {
    return (
      <div className={footerCls}>
        <p className="text-sm text-muted">{s.cleanupFlagged ? `Cleanup flagged; eligible from ${s.cleanupEligibleOn}.` : "Flags the resource group and its resources for cleanup after any expiry grace period."}</p>
        <div className="flex gap-3">
          <button onClick={onRejectDecommission} className={`${btnSecondary} inline-flex items-center gap-2`}>
            <X size={16} aria-hidden="true" />
            Keep sandbox
          </button>
          <button
            onClick={onApproveDecommission}
            disabled={isOwn || s.cleanupFlagged}
            className="inline-flex items-center gap-2 bg-red-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-red-700"
          >
            <Power size={16} aria-hidden="true" />
            {s.cleanupFlagged ? "Cleanup flagged" : "Approve cleanup"}
          </button>
        </div>
      </div>
    );
  }

  if (s.status === "Failed" || s.failedOperation) {
    return (
      <div className={footerCls}>
        <PipelineLink url={s.pipelineRunUrl} />
        <button onClick={onRetry} className={`${btnPrimary} ml-auto inline-flex items-center gap-2`}>
          <RefreshCw size={16} aria-hidden="true" />
          {retryLabels[s.failedOperation ?? "provision"]}
        </button>
      </div>
    );
  }

  if (s.decisionBy) {
    return (
      <div className={footerCls}>
        <p className="text-sm text-muted">
          {s.status === "Rejected" ? "Rejected" : "Approved"} by{" "}
          <span className="text-foreground">{s.decisionBy}</span>
        </p>
      </div>
    );
  }

  return null;
}

function ApproveForm({ sandbox, onClose }: { sandbox: Sandbox; onClose: () => void }) {
  const money = useMoney();
  const { budgetCurrency } = useRole();
  const { approveRequest, configuration } = useSandboxes();
  const { toast } = useToast();
  const inputId = useId();
  const [budget, setBudget] = useState(String(sandbox.budget));
  const [submitting, setSubmitting] = useState(false);

  const amount = Number(budget);
  const maxBudget = configuration?.maxBudget ?? 0;
  const valid = Number.isFinite(amount) && amount > 0 && amount <= maxBudget;

  const onConfirm = async () => {
    if (!valid || submitting) return;
    setSubmitting(true);
    const ok = await approveRequest(sandbox.id, amount);
    setSubmitting(false);
    if (!ok) return;
    toast(`Approved ${sandbox.name}. Terraform provisioning has started.`, "success");
    onClose();
  };

  return (
    <>
      <div className="space-y-4 p-6">
        <p className="text-sm text-muted">
          Approve <span className="font-mono text-foreground">{sandbox.name}</span> for{" "}
          {sandbox.requestorName} with the <span className="text-foreground">{sandbox.role ?? "Contributor"}</span>{" "}
          role in {sandbox.region}. Terraform provisioning starts automatically.
        </p>
        <div>
          <label htmlFor={inputId} className="mb-2 block text-sm font-medium text-foreground">
            Approved budget ({budgetCurrency})
          </label>
          <input
            id={inputId}
            type="number"
            min={1}
            max={maxBudget}
            step="0.01"
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
            aria-invalid={!valid}
            aria-describedby={`${inputId}-hint`}
            className="w-full border border-border bg-background px-4 py-3 text-sm text-foreground focus:border-accent focus:outline-none"
          />
          <p id={`${inputId}-hint`} className="mt-1.5 text-xs text-muted">
            Maximum {money(maxBudget)}. Requested: {money(sandbox.budget)}.
          </p>
          {!valid && (
            <p role="alert" className="mt-1 text-xs text-red-700 dark:text-red-400">
              Budget must be greater than 0 and at most {money(maxBudget)}.
            </p>
          )}
        </div>
      </div>
      <div className="flex justify-end gap-3 border-t border-border px-6 py-4">
        <button onClick={onClose} className={btnSecondary}>
          Cancel
        </button>
        <button onClick={onConfirm} disabled={!valid || submitting} className={btnPrimary}>
          {submitting ? "Approving…" : "Confirm"}
        </button>
      </div>
    </>
  );
}
