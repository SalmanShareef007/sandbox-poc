"use client";

import { useMemo, useState } from "react";
import { Download, Wallet } from "lucide-react";
import EmptyState from "@/components/ui/EmptyState";
import Skeleton from "@/components/ui/Skeleton";
import { barColor, hasApprovedBudget, money } from "@/components/admin/format";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import { monthLabel } from "@/lib/dates";

// Demo-only multipliers so earlier months show smaller, plausible totals.
const MONTH_SCALE = [1, 0.84, 0.69];

interface UnitRow {
  unit: string;
  count: number;
  budget: number;
  spend: number;
}

interface CostCentreRow {
  costCenter: string;
  unit: string;
  count: number;
  spend: number;
}

const selectCls =
  "border border-border bg-background px-4 py-2.5 text-sm text-foreground focus:border-accent focus:outline-none";

// Prefix cells that spreadsheet apps would treat as formulas.
const csvCell = (value: string | number) => {
  const text = String(value);
  const safe = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text;
  return `"${safe.replace(/"/g, '""')}"`;
};

function downloadCsv(filename: string, rows: (string | number)[][]) {
  const csv = rows.map((r) => r.map(csvCell).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export default function CostsPage() {
  const { adminRequests: all, isLoading } = useSandboxes();

  const months = useMemo(() => {
    const now = new Date();
    return MONTH_SCALE.map((scale, i) => ({
      label: monthLabel(new Date(now.getFullYear(), now.getMonth() - i, 1)),
      scale,
    }));
  }, []);
  const [monthIndex, setMonthIndex] = useState(0);
  const month = months[monthIndex];

  const billed = all.filter(hasApprovedBudget);
  const spendOf = (spent: number) => Math.round(spent * month.scale * 100) / 100;

  const totalSpend = billed.reduce((sum, s) => sum + spendOf(s.spent), 0);
  const totalBudget = billed.reduce((sum, s) => sum + s.budget, 0);
  const utilization = totalBudget ? Math.round((totalSpend / totalBudget) * 100) : 0;

  const byUnit = Object.values(
    billed.reduce<Record<string, UnitRow>>((acc, s) => {
      const row = (acc[s.businessUnit] ??= { unit: s.businessUnit, count: 0, budget: 0, spend: 0 });
      row.count += 1;
      row.budget += s.budget;
      row.spend += spendOf(s.spent);
      return acc;
    }, {})
  ).sort((a, b) => b.spend - a.spend);

  const byCostCentre = Object.values(
    billed.reduce<Record<string, CostCentreRow>>((acc, s) => {
      const row = (acc[s.costCenter] ??= {
        costCenter: s.costCenter,
        unit: s.businessUnit,
        count: 0,
        spend: 0,
      });
      row.count += 1;
      row.spend += spendOf(s.spent);
      return acc;
    }, {})
  ).sort((a, b) => b.spend - a.spend);

  const exportCsv = () => {
    downloadCsv(`sandbox-costs-by-cost-centre-${month.label.replace(" ", "-").toLowerCase()}.csv`, [
      ["Cost centre", "Business unit", "Sandboxes", "Spend (INR)"],
      ...byCostCentre.map((r) => [r.costCenter, r.unit, r.count, r.spend.toFixed(2)]),
    ]);
  };

  if (isLoading) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading costs">
        <div className="grid gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <Skeleton className="h-72" />
        <Skeleton className="h-72" />
      </div>
    );
  }

  const summary = [
    { label: "Total spend", value: money(totalSpend) },
    { label: "Approved budget", value: money(totalBudget) },
    { label: "Utilization", value: `${utilization}%` },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <label className="flex flex-col gap-1.5 text-xs font-medium text-muted">
          Month
          <select
            className={selectCls}
            value={monthIndex}
            onChange={(e) => setMonthIndex(Number(e.target.value))}
          >
            {months.map((m, i) => (
              <option key={m.label} value={i}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <p className="text-xs text-muted">
          Cost data refreshes daily. Azure Cost Management data can lag by up to 24 hours.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {summary.map((s) => (
          <div key={s.label} className="border border-border bg-surface p-5 shadow-card">
            <p className="text-sm text-muted">{s.label}</p>
            <p className="mt-2 text-3xl font-bold text-foreground">{s.value}</p>
            <p className="mt-1 text-xs text-muted">{month.label}</p>
          </div>
        ))}
      </div>

      <section className="border border-border bg-surface shadow-card">
        <div className="border-b border-border px-6 py-4">
          <h3 className="font-semibold text-foreground">By business unit</h3>
        </div>
        {byUnit.length === 0 ? (
          <EmptyState icon={Wallet} title="No cost data" text="Approved sandboxes will appear here." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-muted">
                  <th scope="col" className="px-6 py-3 font-semibold">Business unit</th>
                  <th scope="col" className="px-6 py-3 text-right font-semibold">Sandboxes</th>
                  <th scope="col" className="px-6 py-3 text-right font-semibold">Approved budget</th>
                  <th scope="col" className="px-6 py-3 text-right font-semibold">Spend</th>
                  <th scope="col" className="px-6 py-3 font-semibold">Utilization</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {byUnit.map((r) => {
                  const pct = r.budget ? Math.round((r.spend / r.budget) * 100) : 0;
                  return (
                    <tr key={r.unit}>
                      <td className="px-6 py-4 text-foreground">{r.unit}</td>
                      <td className="px-6 py-4 text-right text-foreground">{r.count}</td>
                      <td className="px-6 py-4 text-right text-foreground">{money(r.budget)}</td>
                      <td className="px-6 py-4 text-right font-medium text-foreground">
                        {money(r.spend, 2)}
                      </td>
                      <td className="w-64 px-6 py-4">
                        <div className="h-2 overflow-hidden bg-background">
                          <div
                            className={`h-full ${barColor(pct)}`}
                            style={{ width: `${Math.min(pct, 100)}%` }}
                          />
                        </div>
                        <p className="mt-1.5 text-xs text-muted">{pct}%</p>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="border border-border bg-surface shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-6 py-4">
          <h3 className="font-semibold text-foreground">By cost centre</h3>
          <button
            onClick={exportCsv}
            disabled={byCostCentre.length === 0}
            className="inline-flex items-center gap-2 border border-border bg-surface-2 px-4 py-2 text-sm font-medium text-foreground transition hover:border-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download size={16} aria-hidden="true" />
            Export CSV
          </button>
        </div>
        {byCostCentre.length === 0 ? (
          <EmptyState icon={Wallet} title="No cost data" text="Approved sandboxes will appear here." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[600px] text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-muted">
                  <th scope="col" className="px-6 py-3 font-semibold">Cost centre</th>
                  <th scope="col" className="px-6 py-3 font-semibold">Business unit</th>
                  <th scope="col" className="px-6 py-3 text-right font-semibold">Sandboxes</th>
                  <th scope="col" className="px-6 py-3 text-right font-semibold">Spend</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {byCostCentre.map((r) => (
                  <tr key={r.costCenter}>
                    <td className="px-6 py-4 font-mono text-foreground">{r.costCenter}</td>
                    <td className="px-6 py-4 text-foreground">{r.unit}</td>
                    <td className="px-6 py-4 text-right text-foreground">{r.count}</td>
                    <td className="px-6 py-4 text-right font-medium text-foreground">
                      {money(r.spend, 2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
