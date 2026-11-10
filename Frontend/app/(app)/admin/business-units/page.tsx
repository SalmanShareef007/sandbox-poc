"use client";

import { useRef, useState } from "react";
import { Pencil, Plus, Save, Search, Upload, X } from "lucide-react";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import { useToast } from "@/components/providers/ToastProvider";
import type { BusinessUnit } from "@/lib/types";

const inputCls = "w-full border border-border bg-background px-4 py-3 text-sm text-foreground focus:border-accent focus:outline-none";

export default function BusinessUnitsPage() {
  const { adminBusinessUnits, saveBusinessUnit, importBusinessUnits, isLoading } = useSandboxes();
  const { toast } = useToast();
  const [editing, setEditing] = useState<string | undefined>();
  const [name, setName] = useState("");
  const [shortCode, setShortCode] = useState("");
  const [centers, setCenters] = useState("");
  const [active, setActive] = useState(true);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const nameInput = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const rows = adminBusinessUnits.filter((unit) => unit.name.toLowerCase().includes(query.toLowerCase()) || unit.shortCode.toLowerCase().includes(query.toLowerCase()) || unit.costCenters.some((center) => center.toLowerCase().includes(query.toLowerCase())));

  const reset = () => { setEditing(undefined); setName(""); setShortCode(""); setCenters(""); setActive(true); };
  const edit = (unit: BusinessUnit) => {
    setEditing(unit.id); setName(unit.name); setShortCode(unit.shortCode); setCenters(unit.costCenters.join("\n")); setActive(unit.active);
    nameInput.current?.focus();
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-foreground">Business units</h2>
      <form className="space-y-4 border border-border bg-surface p-6" onSubmit={async (event) => {
        event.preventDefault();
        if (busy || !name.trim() || !shortCode.trim()) return;
        setBusy(true);
        const saved = await saveBusinessUnit({ name: name.trim(), shortCode: shortCode.trim(), costCenters: centers.split(/\r?\n/).map((value) => value.trim()).filter(Boolean), active }, editing);
        setBusy(false);
        if (saved) { toast("Business unit saved", "success"); reset(); }
      }}>
        <div className="grid gap-5 md:grid-cols-2">
          <label className="space-y-2 text-sm font-medium">Business unit name<input ref={nameInput} value={name} onChange={(event) => setName(event.target.value)} required maxLength={120} className={inputCls} /></label>
          <label className="space-y-2 text-sm font-medium">Short code<input value={shortCode} onChange={(event) => setShortCode(event.target.value)} required minLength={1} maxLength={12} pattern="[A-Za-z][A-Za-z0-9]{0,11}" className={inputCls} placeholder="FIN" /></label>
          <label className="space-y-2 text-sm font-medium">Cost centres<textarea value={centers} onChange={(event) => setCenters(event.target.value)} rows={3} className={inputCls} placeholder={"CC-001\nCC-002"} /></label>
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />Active</label>
        <div className="flex flex-wrap gap-3">
          <button type="submit" disabled={busy || !name.trim() || !shortCode.trim()} className="bg-accent-gradient inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50">{editing ? <Save size={16} /> : <Plus size={16} />}{editing ? "Save changes" : "Add business unit"}</button>
          {editing && <button type="button" onClick={reset} className="inline-flex items-center gap-2 border border-border px-5 py-2.5 text-sm"><X size={16} />Cancel</button>}
          <button type="button" disabled={busy} onClick={() => fileInput.current?.click()} className="inline-flex items-center gap-2 border border-border px-5 py-2.5 text-sm disabled:opacity-50"><Upload size={16} />Import JSON</button>
          <input ref={fileInput} type="file" accept=".json,application/json" className="hidden" onChange={async (event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            setBusy(true);
            try {
              if (file.size > 2_000_000) throw new Error("Import file must be smaller than 2 MB.");
              const payload: unknown = JSON.parse(await file.text());
              if (!Array.isArray(payload)) throw new Error("Import must contain an array of business units.");
              if (await importBusinessUnits(payload)) toast("Business units imported", "success");
            } catch (error) {
              toast(error instanceof Error ? error.message : "Import failed", "error");
            } finally { setBusy(false); event.target.value = ""; }
          }} />
        </div>
      </form>
      <section className="border border-border bg-surface">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border p-5">
          <p className="text-sm text-muted">{rows.length} business units</p>
          <label className="relative"><Search size={16} className="absolute top-3 left-3 text-muted" /><input aria-label="Search business units" value={query} onChange={(event) => setQuery(event.target.value)} className={`${inputCls} pl-9`} placeholder="Search business units..." /></label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[600px] text-left text-sm">
            <thead className="border-b border-border text-muted"><tr><th className="px-5 py-3">Business unit</th><th className="px-5 py-3">Short code</th><th className="px-5 py-3">Cost centres</th><th className="px-5 py-3">Status</th><th className="px-5 py-3"><span className="sr-only">Actions</span></th></tr></thead>
            <tbody className="divide-y divide-border">
              {rows.map((unit) => <tr key={unit.id}><td className="px-5 py-4">{unit.name}</td><td className="px-5 py-4 font-mono">{unit.shortCode.toUpperCase()}</td><td className="max-w-md break-words px-5 py-4">{unit.costCenters.join(", ") || "None"}</td><td className="px-5 py-4">{unit.active ? "Active" : "Inactive"}</td><td className="px-5 py-4"><button title={`Edit ${unit.name}`} aria-label={`Edit ${unit.name}`} disabled={busy} onClick={() => edit(unit)} className="p-2 text-accent"><Pencil size={16} /></button></td></tr>)}
              {!rows.length && <tr><td colSpan={5} className="p-6 text-center text-muted">{isLoading ? "Loading..." : "No business units"}</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}