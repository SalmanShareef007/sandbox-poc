import type { SandboxStatus } from "@/lib/types";

const styles: Record<SandboxStatus, string> = {
  Active: "bg-emerald-500/10 text-emerald-700 border-emerald-500/30 dark:text-emerald-400",
  Expiring: "bg-amber-500/10 text-amber-700 border-amber-500/30 dark:text-amber-400",
  Pending: "bg-accent/10 text-accent-dark border-accent/30 dark:text-accent-light",
  Provisioning: "bg-accent/10 text-accent-dark border-accent/30 dark:text-accent-light",
  Failed: "bg-red-500/10 text-red-700 border-red-500/30 dark:text-red-400",
  Rejected: "bg-red-500/10 text-red-700 border-red-500/30 dark:text-red-400",
  Expired: "bg-surface-2 text-muted border-border",
  Decommissioning: "bg-amber-500/10 text-amber-700 border-amber-500/30 dark:text-amber-400",
  Decommissioned: "bg-surface-2 text-muted border-border",
};

export default function StatusBadge({ status }: { status: SandboxStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${styles[status]}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {status}
    </span>
  );
}