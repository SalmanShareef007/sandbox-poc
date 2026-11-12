"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import { useToast } from "@/components/providers/ToastProvider";
import { useMoney } from "@/components/admin/format";
import { useRole } from "@/hooks/useRole";

const workloads = [
  "Compute / Virtual Machines",
  "Containers / AKS",
  "Web Apps & APIs",
  "Data & Analytics",
  "Networking",
  "AI / Machine Learning",
];

// Mirrors the backend: Terraform key is <unit>-<firstname>-<nnn>.
const slug = (value: string, length: number) => value.toLowerCase().replace(/[^a-z0-9]/g, "").slice(0, length);

const inputCls =
  "w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted focus:border-accent focus:outline-none";

const isoDate = (d: Date) => d.toISOString().slice(0, 10);
const prettyDate = (d: Date) =>
  d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div title={hint}>
      <label className="mb-2 block text-sm font-medium text-foreground">
        {label} <span className="text-red-500" aria-hidden="true">*</span>
      </label>
      {children}
      {hint && <p className="mt-1.5 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export default function NewRequestPage() {
  const money = useMoney();
  const { budgetCurrency } = useRole();
  const router = useRouter();
  const { account } = useAuth();
  const { sandboxes, addRequest, configuration, isLoading, error } = useSandboxes();
  const { toast } = useToast();
  const email = account?.username ?? "";
  const firstName = slug(account?.name?.split(" ")[0] ?? "", 12) || "user";

  // Only resource-group sandboxes are provisioned in this phase.
  const [businessUnit, setBusinessUnit] = useState("");
  const [costCenter, setCostCenter] = useState("");
  const [managerEmail, setManagerEmail] = useState("");
  const managerInput = useRef<HTMLInputElement>(null);
  const [workload, setWorkload] = useState(workloads[0]);
  const [regionChoice, setRegion] = useState("");
  const [roleChoice, setRole] = useState("");
  const [description, setDescription] = useState("");
  const [justification, setJustification] = useState("");
  const [budget, setBudget] = useState<string | null>(null);
  const [durationChoice, setDuration] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submittedName, setSubmittedName] = useState<string | null>(null);
  const businessUnits = configuration?.businessUnits ?? [];
  const regions = configuration?.regions ?? [];
  const accessRoles = configuration?.roles ?? [];
  const durations = configuration?.durations ?? [];
  const maxBudget = configuration?.maxBudget ?? 0;
  const region = regionChoice || regions[0] || "";
  const role = roleChoice || (accessRoles.includes("Contributor") ? "Contributor" : accessRoles[0]) || "";
  const duration = durationChoice ?? durations[0] ?? 30;
  const costCenters = configuration?.costCenterMode === "shared" ? configuration.sharedCostCenters : businessUnits.find((unit) => unit.name === businessUnit)?.costCenters ?? [];

  const expiry = new Date();
  expiry.setDate(expiry.getDate() + duration);

  const shortCode = businessUnits.find((unit) => unit.name === businessUnit)?.shortCode || "sbx";
  const prefix = `rg-sandbox-${shortCode}-${firstName}-`;
  const seq = String(sandboxes.filter((s) => s.name.startsWith(prefix)).length + 1).padStart(3, "0");
  const name = `${prefix}${seq}`;

  const budgetNum = Number(budget ?? "");
  const budgetOver = Number.isFinite(budgetNum) && budgetNum > maxBudget;
  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(managerEmail.trim());

  const missingFields = () => {
    const missing: string[] = [];
    if (!businessUnits.some((unit) => unit.name === businessUnit)) missing.push("Business unit");
    if (!costCenter.trim()) missing.push("Cost centre");
    if (!managerEmail.trim()) missing.push("Manager email");
    else if (!emailOk) missing.push("Manager email (enter a valid address)");
    if (!workload) missing.push("Intended workload");
    if (!region) missing.push("Region");
    if (!role) missing.push("Access role");
    if (!description.trim()) missing.push("Workload description");
    if (justification.trim().length < 20) missing.push("Business justification (minimum 20 characters)");
    if (!budget?.trim() || !(budgetNum > 0)) missing.push(`Estimated budget (greater than ${money(0)})`);
    if (!duration) missing.push("Duration");
    return missing;
  };

  const valid = missingFields().length === 0 && !budgetOver;

  const onSubmit = async () => {
    if (submitting || configuration?.subscriptionChangePending) return;
    const missing = missingFields();
    if (missing.length) {
      toast(`Please complete: ${missing.join(", ")}.`, "error");
      return;
    }
    if (budgetOver) {
      toast(`Budget cannot exceed the maximum of ${money(maxBudget)}. You entered ${money(budgetNum, 2)}.`, "error");
      return;
    }
    setSubmitting(true);
    const created = await addRequest({
      businessUnit,
      costCenter: costCenter.trim(),
      managerEmail: managerEmail.trim(),
      workload,
      region,
      role,
      budget: budgetNum,
      durationDays: duration,
      description: description.trim(),
      justification: justification.trim(),
    });
    setSubmitting(false);
    if (!created) return;
    setSubmittedName(created.name);
    toast(`Request ${created.name} submitted for approval`, "success");
  };

  if (isLoading || !configuration) return <p role="status" className="p-6 text-sm text-muted">{error ?? "Loading request configuration..."}</p>;

  if (submittedName) {
    return (
      <div className="mx-auto max-w-lg rounded-card border border-border bg-surface p-10 text-center shadow-card">
        <CheckCircle2 size={48} className="mx-auto text-emerald-700 dark:text-emerald-400" />
        <h2 className="mt-4 text-2xl font-bold text-foreground">Request submitted</h2>
        <p className="mt-2 text-muted">
          <span className="font-mono text-foreground">{submittedName}</span> has been routed to IT
          Administrators for approval.
        </p>
        <button
          onClick={() => router.push("/sandboxes")}
          className="bg-accent-gradient mt-8 rounded-full px-6 py-3 font-medium text-white shadow-accent transition hover:brightness-110"
        >
          Go to My sandboxes
        </button>
      </div>
    );
  }

  const tags = [
    ["Owner", email],
    ["BusinessUnit", businessUnit],
    ["CostCenter", costCenter || "—"],
    ["Environment", configuration.environment],
    ["ExpiryDate", isoDate(expiry)],
    ["ManagedBy", "Sandbox-POC"],
    ["Manager", managerEmail || "—"],
  ];

  const steps = [
    ["Submitted", "Request routed to IT Administrators"],
    ["Approval", "Approved → automated provisioning. Rejected → reason shown on the sandbox page."],
    ["Provisioning", `Terraform: resource group, mandatory tags policy, ${role} role, budget alerts`],
    ["In use", "Budget alerts and expiry reminders; expired sandboxes require approval before deletion"],
  ];

  return (
    <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
      {/* FORM */}
      <section className="rounded-card border border-border bg-surface shadow-card">
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h3 className="font-semibold text-foreground">Sandbox request</h3>
          <span className="text-xs text-muted">All fields are required</span>
        </div>

        <div className="space-y-6 p-6">
          <Field label="Sandbox type" hint="Dedicated subscriptions will be available in a later phase">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-accent bg-accent/10 p-4 text-left">
                <p className="text-sm font-semibold text-foreground">Resource group</p>
                <p className="mt-1 text-xs text-muted">Under shared sandbox subscription</p>
              </div>
            </div>
          </Field>

          <div className="grid gap-6 sm:grid-cols-2">
            <Field label="Business unit">
              <select className={inputCls} value={businessUnit} onChange={(e) => { setBusinessUnit(e.target.value); setCostCenter(""); }}>
                <option value="">{businessUnits.length ? "Select business unit" : "No business units configured"}</option>
                {businessUnits.map((unit) => <option key={unit.id} value={unit.name}>{unit.name}</option>)}
              </select>
            </Field>
            <Field label="Cost centre">
              {configuration.costCenterMode === "free_text" ? (
                <input className={inputCls} value={costCenter} maxLength={80} onChange={(e) => setCostCenter(e.target.value)} />
              ) : (
                <select className={inputCls} value={costCenter} onChange={(e) => setCostCenter(e.target.value)}>
                  <option value="">Select cost centre</option>
                  {costCenters.map((center) => <option key={center}>{center}</option>)}
                </select>
              )}
            </Field>
            <Field label="Manager email">
              <input ref={managerInput} type="email" required maxLength={254} className={inputCls} value={managerEmail} onChange={(event) => setManagerEmail(event.target.value)} />
            </Field>
            <Field label="Intended workload">
              <select className={inputCls} value={workload} onChange={(e) => setWorkload(e.target.value)}>
                {workloads.map((w) => <option key={w}>{w}</option>)}
              </select>
            </Field>
            <Field label="Region" hint="Validated against the configured allowed regions">
              <select className={inputCls} value={region} onChange={(e) => setRegion(e.target.value)}>
                {regions.map((r) => <option key={r}>{r}</option>)}
              </select>
            </Field>
            <Field label="Access role" hint={role === "Owner" ? "Owner can grant access within this resource group." : "Azure role granted to you on the resource group"}>
              <select className={inputCls} value={role} onChange={(e) => setRole(e.target.value)}>
                {accessRoles.map((r) => <option key={r}>{r}</option>)}
              </select>
            </Field>
          </div>

          <Field label="Workload description">
            <input
              className={inputCls}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. AKS cluster to test service mesh options"
            />
          </Field>

          <Field
            label="Business justification"
            hint={`Minimum 20 characters (${justification.trim().length}/20)`}
          >
            <textarea
              rows={4}
              className={inputCls}
              value={justification}
              onChange={(e) => setJustification(e.target.value)}
              placeholder="What are you trying to learn or validate, and why does it matter?"
            />
          </Field>

          <div className="grid gap-6 sm:grid-cols-2">
            <Field label={`Estimated budget (${budgetCurrency})`} hint={`Maximum ${money(maxBudget)}`}>
              <input
                type="number"
                min={1}
                max={maxBudget}
                step="0.01"
                required
                title={`Enter an amount up to ${money(maxBudget)}`}
                aria-invalid={budgetOver}
                className={`${inputCls} ${budgetOver ? "border-red-500 focus:border-red-500" : ""}`}
                value={budget ?? ""}
                placeholder={`Up to ${money(maxBudget)}`}
                onChange={(e) => setBudget(e.target.value)}
              />
              {budgetOver && (
                <p role="alert" className="mt-1.5 text-xs font-medium text-red-600 dark:text-red-400">
                  Budget cannot exceed {money(maxBudget)}.
                </p>
              )}
            </Field>
            <Field label="Duration" hint={`Expiry date: ${prettyDate(expiry)}`}>
              <select className={inputCls} value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
                {durations.map((d) => <option key={d} value={d}>{d} days</option>)}
              </select>
            </Field>
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-border px-6 py-4">
          <Link
            href="/dashboard"
            className="rounded-full border border-border bg-surface-2 px-6 py-2.5 text-sm font-medium text-foreground transition hover:border-accent"
          >
            Cancel
          </Link>
          <button
            onClick={onSubmit}
            disabled={submitting || configuration.subscriptionChangePending}
            title={valid ? "Send this request to IT Administrators" : "Some required fields are missing. Click to see which."}
            className="bg-accent-gradient rounded-full px-6 py-2.5 text-sm font-medium text-white shadow-accent transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Submitting…" : "Submit for approval"}
          </button>
        </div>
      </section>

      {/* PREVIEW */}
      <div className="space-y-6">
        <section className="rounded-card border border-border bg-surface shadow-card">
          <div className="border-b border-border px-6 py-4">
            <h3 className="font-semibold text-foreground">Preview</h3>
          </div>
          <dl className="space-y-3 p-6 text-sm">
            {[
              ["Name", <span key="n" className="font-mono">{name}</span>],
              ["Scope", "Resource group in shared subscription"],
              ["Subscription", configuration.subscriptionName || configuration.subscriptionId],
              ["Region", region],
              ["Role", `${role} (${email})`],
              ["Budget", `${money(budgetNum || 0)} · alerts ${configuration.budgetAlertThresholds.join("/")}%`],
              ["Expiry", prettyDate(expiry)],
            ].map(([k, v], i) => (
              <div key={i} className="flex justify-between gap-4">
                <dt className="text-muted">{k}</dt>
                <dd className="text-right text-foreground">{v}</dd>
              </div>
            ))}
          </dl>
          <div className="border-t border-border p-6">
            <p className="mb-3 text-xs font-semibold tracking-wider text-muted">MANDATORY TAGS</p>
            <div className="flex flex-wrap gap-2">
              {tags.map(([k, v]) => (
                <span key={k} className="rounded-lg border border-border bg-surface-2 px-2.5 py-1 text-xs text-foreground">
                  <span className="font-semibold">{k}:</span> {v}
                </span>
              ))}
            </div>
          </div>
        </section>

        <section className="rounded-card border border-border bg-surface shadow-card">
          <div className="border-b border-border px-6 py-4">
            <h3 className="font-semibold text-foreground">What happens next</h3>
          </div>
          <ul className="space-y-5 p-6">
            {steps.map(([title, text]) => (
              <li key={title} className="flex gap-3">
                <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent" />
                <div>
                  <p className="text-sm font-semibold text-foreground">{title}</p>
                  <p className="text-xs text-muted">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}