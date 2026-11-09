"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

const CONTACT = "sandbox-admins@company.com";

const faqs: { q: string; a: React.ReactNode }[] = [
  {
    q: "How do sandboxes work?",
    a: "A sandbox is an isolated Azure environment for experimentation. You submit a request, IT Administrators approve it, and Terraform provisions it with mandatory tags, the access role you chose (Contributor or Owner), and budget alerts. When it is no longer needed, it is decommissioned after admin approval.",
  },
  {
    q: "Subscription or resource group?",
    a: "In this phase every sandbox is a resource group inside the shared sandbox subscription, created in the region you choose. Dedicated subscriptions under the Sandbox Management Group will come in a later phase.",
  },
  {
    q: "What are the budget rules?",
    a: "Each sandbox gets a default budget of ₹500 (budgets are in INR, the subscription's billing currency). You receive email alerts when spend reaches 75%, 90% and 100% of the budget. In Phase 1, budgets are notify-only and resources are not stopped automatically. Larger budgets need extra justification and may require director approval.",
  },
  {
    q: "When does a sandbox expire, and can I extend it?",
    a: "You choose a duration of 30, 60 or 90 days when you request a sandbox. You get a reminder 7 days before expiry. For Active or Expiring sandboxes, open the sandbox and choose Request extension to ask for 30 or 60 more days with a short reason.",
  },
  {
    q: "How does approval work?",
    a: "New requests are routed to IT Administrators. If a request is approved, provisioning starts automatically and the sandbox becomes Active when it is ready. If it is rejected, you receive an email and can see the reason on the sandbox page.",
  },
  {
    q: "Which tags are mandatory?",
    a: "Every sandbox is tagged with Owner, BusinessUnit, CostCenter, Environment, ExpiryDate and ManagedBy. Azure Policy enforces these tags, so do not remove or change them.",
  },
  {
    q: "Who do I contact?",
    a: (
      <>
        Email the sandbox administrators at{" "}
        <a href={`mailto:${CONTACT}`} className="text-accent hover:text-accent-light">
          {CONTACT}
        </a>{" "}
        for access issues, policy exceptions or anything not covered here.
      </>
    ),
  },
];

export default function HelpPage() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <section className="border border-border bg-surface shadow-card">
      <div className="border-b border-border px-6 py-4">
        <h3 className="font-semibold text-foreground">Frequently asked questions</h3>
      </div>

      <ul className="divide-y divide-border">
        {faqs.map(({ q, a }, i) => {
          const expanded = open === i;
          const panelId = `faq-panel-${i}`;
          const buttonId = `faq-button-${i}`;
          return (
            <li key={q}>
              <h4>
                <button
                  id={buttonId}
                  onClick={() => setOpen(expanded ? null : i)}
                  aria-expanded={expanded}
                  aria-controls={panelId}
                  className="flex w-full items-center justify-between gap-4 px-6 py-4 text-left text-sm font-medium text-foreground transition hover:bg-surface-2/50"
                >
                  {q}
                  <ChevronDown
                    size={18}
                    className={`shrink-0 text-muted transition-transform ${expanded ? "rotate-180" : ""}`}
                  />
                </button>
              </h4>
              <div
                id={panelId}
                role="region"
                aria-labelledby={buttonId}
                hidden={!expanded}
                className="px-6 pb-5 text-sm leading-relaxed text-muted"
              >
                {a}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
