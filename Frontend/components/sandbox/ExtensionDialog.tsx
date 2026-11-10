"use client";

import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import Modal from "@/components/ui/Modal";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import { useToast } from "@/components/providers/ToastProvider";
import type { Sandbox } from "@/lib/types";

const MIN_REASON = 10;

const inputCls =
  "w-full border border-border bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted focus:border-accent focus:outline-none";

interface ExtensionDialogProps {
  sandbox: Pick<Sandbox, "id" | "name" | "expiryDate">;
  open: boolean;
  onClose: () => void;
}

export default function ExtensionDialog({ sandbox, open, onClose }: ExtensionDialogProps) {
  return (
    <Modal open={open} onClose={onClose} title="Request extension">
      <ExtensionForm sandbox={sandbox} onClose={onClose} />
    </Modal>
  );
}

function ExtensionForm({
  sandbox,
  onClose,
}: {
  sandbox: Pick<Sandbox, "id" | "name" | "expiryDate">;
  onClose: () => void;
}) {
  const { requestExtension, configuration } = useSandboxes();
  const { toast } = useToast();
  const options = configuration?.extensionDays.filter((days) => days <= configuration.maxExtensionDays) ?? [];
  const [daysChoice, setDays] = useState<number | null>(null);
  const days = daysChoice ?? options[0] ?? 30;
  const [mode, setMode] = useState<"duration" | "date">("duration");
  const [requestedExpiry, setRequestedExpiry] = useState("");
  const [openedAt] = useState(() => Date.now());
  const [reason, setReason] = useState("");
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const length = reason.trim().length;
  const base = Date.parse(`${sandbox.expiryDate}T00:00:00Z`);
  const minDate = new Date(Math.max(Number.isFinite(base) ? base + 86400000 : 0, openedAt + 86400000)).toISOString().slice(0, 10);
  const maxDate = Number.isFinite(base) ? new Date(base + (configuration?.maxExtensionDays ?? 60) * 86400000).toISOString().slice(0, 10) : "";
  const valid = length >= MIN_REASON && (mode === "duration" ? options.includes(days) : !!requestedExpiry && requestedExpiry >= minDate && requestedExpiry <= maxDate);

  const onSubmit = async () => {
    if (!valid || submitting) return;
    setSubmitting(true);
    const ok = await requestExtension(sandbox.id, mode === "duration" ? days : null, reason.trim(), mode === "date" ? requestedExpiry : undefined);
    setSubmitting(false);
    if (!ok) return;
    toast(`Extension requested for ${sandbox.name}`, "success");
    setDone(true);
  };

  if (done) {
    return (
      <div className="p-6 text-center">
        <CheckCircle2 size={40} className="mx-auto text-emerald-700 dark:text-emerald-400" />
        <p className="mt-3 font-semibold text-foreground">Extension requested</p>
        <p className="mt-1 text-sm text-muted">
          An extension for <span className="font-mono text-foreground">{sandbox.name}</span>{" "}
          has been sent to IT Administrators for approval.
        </p>
        <button
          onClick={onClose}
          className="bg-accent-gradient mt-6 px-6 py-2.5 text-sm font-medium text-white shadow-accent transition hover:brightness-110"
        >
          Done
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-5 p-6">
        <p className="text-sm text-muted">
          Extend <span className="font-mono text-foreground">{sandbox.name}</span>
        </p>

        <div>
          <fieldset className="mb-4 flex gap-5 text-sm">
            <legend className="mb-2 font-medium">Extension</legend>
            <label className="flex items-center gap-2"><input type="radio" name="extension-mode" checked={mode === "duration"} onChange={() => setMode("duration")} />Extra days</label>
            <label className="flex items-center gap-2"><input type="radio" name="extension-mode" checked={mode === "date"} disabled={!sandbox.expiryDate} onChange={() => setMode("date")} />Expiry date</label>
          </fieldset>
          {mode === "date" ? (
            <label className="block text-sm font-medium">Requested expiry date<input type="date" min={minDate} max={maxDate} value={requestedExpiry} onChange={(event) => setRequestedExpiry(event.target.value)} className={`${inputCls} mt-2`} /></label>
          ) : <>
          <p className="mb-2 text-sm font-medium text-foreground">Extra days</p>
          <div className="grid grid-cols-2 gap-3">
            {options.map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDays(d)}
                className={`border p-3 text-sm font-medium transition ${
                  days === d
                    ? "border-accent bg-accent/10 text-foreground"
                    : "border-border bg-background text-muted hover:border-muted"
                }`}
              >
                {d} days
              </button>
            ))}
          </div>
          </>}
        </div>

        <div>
          <label htmlFor="extension-reason" className="mb-2 block text-sm font-medium text-foreground">
            Reason
          </label>
          <textarea
            id="extension-reason"
            rows={3}
            className={inputCls}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Why do you need more time?"
          />
          <p
            className={`mt-1.5 text-xs ${
              valid ? "text-muted" : "text-amber-700 dark:text-amber-400"
            }`}
          >
            Minimum {MIN_REASON} characters ({length}/{MIN_REASON})
          </p>
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
          onClick={onSubmit}
          disabled={!valid || submitting}
          className="bg-accent-gradient px-6 py-2.5 text-sm font-medium text-white shadow-accent transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Submitting…" : "Submit"}
        </button>
      </div>
    </>
  );
}
