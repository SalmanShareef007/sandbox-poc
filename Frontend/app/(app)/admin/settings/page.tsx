"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw, Save } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { apiFetch } from "@/lib/api";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import { useToast } from "@/components/providers/ToastProvider";

interface Subscription {
  id: string;
  name: string;
}

export default function SettingsPage() {
  const { getApiToken } = useAuth();
  const { configuration, refresh } = useSandboxes();
  const { toast } = useToast();
  const tokenRef = useRef(getApiToken);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { tokenRef.current = getApiToken; });
  const load = useCallback(async () => {
    try {
      setSubscriptions(await apiFetch<Subscription[]>(() => tokenRef.current(), "/admin/subscriptions"));
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to read subscriptions.");
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const currentId = configuration?.subscriptionId ?? "";
  const choice = selected ?? currentId;
  const choices = currentId && !subscriptions.some((item) => item.id === currentId)
    ? [{ id: currentId, name: configuration?.subscriptionName || currentId }, ...subscriptions]
    : subscriptions;
  const pending = configuration?.subscriptionChangePending ?? false;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-foreground">Settings</h2>
      <section className="space-y-5 border border-border bg-surface p-6">
        <h3 className="font-semibold">Sandbox subscription</h3>
        <dl className="grid gap-3 text-sm sm:grid-cols-2"><div><dt className="text-muted">Current subscription</dt><dd className="mt-1 break-words">{configuration?.subscriptionName || currentId || "Not configured"}</dd></div><div><dt className="text-muted">Subscription ID</dt><dd className="mt-1 break-all font-mono">{currentId || "Not configured"}</dd></div></dl>
        <form className="space-y-4" onSubmit={async (event) => {
          event.preventDefault();
          if (!choice || saving || pending) return;
          setSaving(true);
          try {
            await apiFetch(() => tokenRef.current(), "/admin/subscription", { method: "PUT", body: { subscriptionId: choice } });
            await refresh();
            toast(choice === currentId ? "Subscription is already selected" : "Subscription change queued for worker safety checks", "info");
          } catch (cause) { toast(cause instanceof Error ? cause.message : "Subscription change failed", "error"); }
          finally { setSaving(false); }
        }}>
          <label className="block space-y-2 text-sm font-medium">Subscription<select value={choice} onChange={(event) => setSelected(event.target.value)} disabled={loading || saving || pending} className="w-full border border-border bg-background px-4 py-3 text-sm text-foreground focus:border-accent focus:outline-none"><option value="">{loading ? "Loading subscriptions..." : "Select subscription"}</option>{choices.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.id})</option>)}</select></label>
          <p className="text-sm text-muted">Existing resources cannot be moved by changing this setting. Active work or nonempty Terraform state blocks a change.</p>
          {pending && <p role="status" className="text-sm text-muted">Awaiting worker validation. New sandbox requests are paused.</p>}
          {(error || configuration?.subscriptionChangeError) && <p role="alert" className="break-words text-sm text-red-700 dark:text-red-400">{error || configuration?.subscriptionChangeError}</p>}
          <div className="flex flex-wrap gap-3">
            <button type="submit" disabled={!subscriptions.some((item) => item.id === choice) || loading || saving || pending} className="bg-accent-gradient inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"><Save size={16} />{saving ? "Saving..." : "Save subscription"}</button>
            <button type="button" disabled={loading || saving} onClick={() => { setLoading(true); void load(); void refresh(); }} className="inline-flex items-center gap-2 border border-border px-5 py-2.5 text-sm disabled:opacity-50"><RefreshCw size={16} />Refresh</button>
          </div>
        </form>
      </section>
    </div>
  );
}