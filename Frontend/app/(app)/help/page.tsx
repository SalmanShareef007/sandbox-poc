"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

const CONTACT = "sandbox-admins@company.com";

const faqs: { q: string; a: React.ReactNode }[] = [
  {
    q: "How do sandboxes work?",
    a: "A sandbox is a resource group for experimentation in the shared sandbox subscription. IT Administrators approve requests before provisioning with Contributor access, mandatory tags and budget alerts. Deletion requires administrator approval.",
  },
  {
    q: "Subscription or resource group?",
    a: "In this phase every sandbox is a resource group inside the shared sandbox subscription, created in the region you choose. Dedicated subscriptions under the Sandbox Management Group will come in a later phase.",
  },
  {
    q: "What are the budget rules?",
    a: "You may request less than the configured maximum budget, but neither a request nor an approval can exceed it. Budget alerts use the configured thresholds and administrator recipients. They are notifications, not spending caps. Billing data can be delayed or temporarily unavailable.",
  },
  {
    q: "When does a sandbox expire, and can I extend it?",
    a: "Choose a configured duration or request an extension to a future expiry date. Users, managers and administrators receive configured expiry reminders. Expired resources keep running during grace and until an administrator flags cleanup. A pending extension blocks deletion; approval cancels earlier cleanup flags. The expiry tag changes only after the infrastructure update succeeds.",
  },
  {
    q: "How does approval work?",
    a: "IT Administrators review requests. Approval queues provisioning; the sandbox becomes Active after successful completion. Decisions appear in notifications and the sandbox timeline. Email delivery depends on the configured notification service.",
  },
  {
    q: "Which tags are mandatory?",
    a: "New requests include Owner, BusinessUnit, CostCenter, Environment, ExpiryDate, Manager and ManagedBy tags. The original resource-group policy audits Owner, BusinessUnit, CostCenter, Environment, ExpiryDate and ManagedBy without blocking deployments. It is not assigned across the subscription or tenant.",
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
