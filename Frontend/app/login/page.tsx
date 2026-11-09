"use client";

import { useEffect } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { InteractionStatus } from "@azure/msal-browser";
import { Check, GitBranch, IndianRupee, Lock, Shield } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useRole } from "@/hooks/useRole";
import LOGO_SRC from "@/public/assets/S&MXencia.png";

const features = [
  {
    icon: Check,
    title: "Self-service requests",
    text: "Submit justification, budget and duration, routed to IT for approval.",
  },
  {
    icon: GitBranch,
    title: "Terraform-provisioned",
    text: "GitHub pipelines create, tag and secure every sandbox with full traceability.",
  },
  {
    icon: Shield,
    title: "Governed by default",
    text: "Azure Policy, mandatory tags and RBAC isolation at the Sandbox Management Group.",
  },
  {
    icon: IndianRupee,
    title: "Budget aware",
    text: "₹500 default budget with 75 / 90 / 100% email alerts and expiry reminders.",
  },
];

export default function LoginPage() {
  const { isAuthenticated, inProgress, login } = useAuth();
  const router = useRouter();
  const { isAdmin } = useRole();

  useEffect(() => {
    if (isAuthenticated) router.replace(isAdmin ? "/admin" : "/dashboard");
  }, [isAuthenticated, isAdmin, router]);

  const busy = inProgress !== InteractionStatus.None;

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      {/* LEFT: branding panel */}
      <section className="relative hidden flex-col justify-between overflow-hidden bg-background p-14 lg:flex">
        <div className="pointer-events-none absolute -top-40 -left-40 h-[28rem] w-[28rem] rounded-full bg-accent opacity-25 blur-3xl" />
        <div className="pointer-events-none absolute -right-32 bottom-0 h-96 w-96 rounded-full bg-accent-dark opacity-10 blur-3xl" />

        <div className="relative">
          <Image
            src={LOGO_SRC}
            alt="S&MXencia"
            width={180}
            height={48}
            priority
            style={{ width: "180px", height: "auto" }}
          />
        </div>

        <div className="relative max-w-xl">
          <h1 className="text-5xl font-bold leading-tight text-foreground">
            Governed Azure sandboxes, on demand.
          </h1>
          <p className="mt-6 text-base leading-relaxed text-muted">
            Request an isolated Azure subscription or resource group for
            experimentation. Approval, provisioning, governance, budgets and
            lifecycle are automated end-to-end.
          </p>

          <ul className="mt-10 space-y-6">
            {features.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-surface text-accent">
                  <Icon size={18} />
                </div>
                <div>
                  <p className="font-semibold text-foreground">{title}</p>
                  <p className="text-sm text-muted">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-sm text-muted">
          Azure Sandbox Platform · Phase 1 (MVP)
        </p>
      </section>

      {/* RIGHT: sign-in */}
      <section className="flex items-center justify-center bg-cream px-6 py-12">
        <div className="w-full max-w-md">
          {/* logo shown only on mobile, where the left panel is hidden */}
          <div className="mb-10 lg:hidden">
            <Image
              src={LOGO_SRC}
              alt="S&MXencia"
              width={160}
              height={44}
              style={{ width: "160px", height: "auto" }}
            />
          </div>

          <h2 className="text-3xl font-bold text-[#121212]">Sign in</h2>
          <p className="mt-2 text-muted">
            Use your Harris account to continue.
          </p>

          <button
            onClick={login}
            disabled={busy}
            className="bg-accent-gradient mt-8 flex w-full items-center justify-center gap-2 rounded-full px-6 py-3.5 font-medium text-white shadow-accent transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Lock size={16} />
            {busy ? "Please wait..." : "Sign in with Microsoft"}
          </button>

          <p className="mt-6 text-center text-xs text-muted">
            Secured by Microsoft Entra ID
          </p>
        </div>
      </section>
    </main>
  );
}
