"use client";

import { useId, useState } from "react";
import Modal from "@/components/ui/Modal";

interface ReasonDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  intro: React.ReactNode;
  confirmLabel: string;
  onConfirm: (reason: string) => void;
  minLength?: number;
}

export default function ReasonDialog({ open, onClose, title, ...form }: ReasonDialogProps) {
  return (
    <Modal open={open} onClose={onClose} title={title}>
      <ReasonForm onClose={onClose} {...form} />
    </Modal>
  );
}

function ReasonForm({
  onClose,
  intro,
  confirmLabel,
  onConfirm,
  minLength = 10,
}: Omit<ReasonDialogProps, "open" | "title">) {
  const id = useId();
  const [reason, setReason] = useState("");
  const length = reason.trim().length;
  const valid = length >= minLength;

  return (
    <>
      <div className="space-y-4 p-6">
        <div className="text-sm text-muted">{intro}</div>
        <div>
          <label htmlFor={id} className="mb-2 block text-sm font-medium text-foreground">
            Reason <span className="text-red-700 dark:text-red-400">*</span>
          </label>
          <textarea
            id={id}
            rows={4}
            required
            aria-required="true"
            aria-describedby={`${id}-count`}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Explain the decision. This is emailed to the requestor."
            className="w-full border border-border bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted focus:border-accent focus:outline-none"
          />
          <p
            id={`${id}-count`}
            className={`mt-1.5 text-xs ${valid ? "text-muted" : "text-amber-700 dark:text-amber-400"}`}
          >
            Minimum {minLength} characters ({length}/{minLength})
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
          onClick={() => valid && onConfirm(reason.trim())}
          disabled={!valid}
          className="bg-red-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {confirmLabel}
        </button>
      </div>
    </>
  );
}
