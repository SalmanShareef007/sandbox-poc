"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import { useToast } from "@/components/providers/ToastProvider";
import StatusBadge from "@/components/ui/StatusBadge";

export default function AdminSandboxDetail() {
  const { id } = useParams<{ id: string }>();
  const { adminRequests, isLoading, decommissionRequested } = useSandboxes();
  const { toast } = useToast();
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const sandbox = adminRequests.find((item) => item.id === decodeURIComponent(id));

  if (!sandbox) return <p>{isLoading ? "Loading sandbox..." : "Sandbox not found."}</p>;
  const canRequest = ["Active", "Expiring", "Expired"].includes(sandbox.status) &&
    !sandbox.operationInProgress && !sandbox.decommissionPending;

  return (
    <div className="space-y-6">
      <Link href="/admin/sandboxes" className="text-sm text-accent">Back to all sandboxes</Link>
      <section className="space-y-4 border border-border bg-surface p-6">
        <h2 className="font-mono text-xl font-bold">{sandbox.name}</h2>
        <StatusBadge status={sandbox.status} />
        <p>Owner: {sandbox.owner}</p>
        <p>Region: {sandbox.region} · Access: {sandbox.role}</p>
        <p>Expiry: {sandbox.expiry ?? "Not set"}</p>
        <p>Budget: {sandbox.budget} {sandbox.budgetCurrency} · Cost: {sandbox.spent ?? "Unavailable"} {sandbox.costCurrency}</p>
        {sandbox.decommissionPending && <p>Decommission: {sandbox.decommissionSource === "admin-consent" && !sandbox.decommissionOwnerAccepted ? "Awaiting owner agreement" : "Awaiting administrator decision"}</p>}
      </section>
      {canRequest && (
        <section className="space-y-3 border border-border bg-surface p-6">
          <h3 className="font-semibold">Request decommission</h3>
          <p className="text-sm text-muted">Once the owner agrees, you can approve cleanup in Approvals.</p>
          <label htmlFor="decommission-message" className="block text-sm">Message to owner</label>
          <textarea id="decommission-message" value={message} onChange={(event) => setMessage(event.target.value)} className="w-full border border-border bg-background p-3" rows={3} />
          <button disabled={busy || !message.trim()} className="bg-red-600 px-4 py-2 text-white disabled:opacity-50" onClick={async () => {
            setBusy(true);
            const ok = await decommissionRequested(sandbox.id, message.trim());
            setBusy(false);
            if (ok) { setMessage(""); toast("Request sent to the sandbox owner.", "success"); }
          }}>Send request</button>
        </section>
      )}
    </div>
  );
}
