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

export default function LoginClient() {
  const { isAuthenticated, inProgress, login } = useAuth();
  const router = useRouter();
  const { isAdmin } = useRole();

  useEffect(() => {
    if (isAuthenticated) router.replace(isAdmin ? "/admin" : "/dashboard");
  }, [isAuthenticated, isAdmin, router]);

  const busy = inProgress !== InteractionStatus.None;

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.05fr_0.95fr]">
      <section className="hidden flex-col justify-between bg-[#161616] px-7 py-8 sm:px-12 lg:flex lg:px-14 lg:py-12">
        <div className="flex flex-wrap items-center justify-between gap-5">
          <div className="inline-flex items-center bg-white px-2 py-2">
            <Image
              src={LOGO_SRC}
              alt="S&MXencia"
              width={180}
              height={48}
              priority
              className="h-9 w-auto"
              style={{ width: "auto" }}
            />
          </div>
          <p className="text-[11px] font-bold tracking-[0.18em] text-accent uppercase">
            Saints &amp; Masters × Xencia
          </p>
        </div>

        <div className="my-12 max-w-xl">
          <p className="text-xs font-bold tracking-[0.2em] text-accent uppercase">
            Cloud sandbox workspace
          </p>
          <h1 className="mt-4 text-4xl leading-tight font-bold text-white xl:text-5xl">
            Governed Azure sandboxes, on demand.
          </h1>
          <p className="mt-5 max-w-lg text-base leading-relaxed text-[#b8b8b8]">
            Request an isolated Azure subscription or resource group for
            experimentation. Approval, provisioning, governance, budgets and
            lifecycle are automated end-to-end.
          </p>

          <ul className="mt-9 grid gap-x-8 gap-y-6 sm:grid-cols-2">
            {features.map(({ icon: Icon, title, text }, index) => {
              const iconTone = [
                "bg-accent text-white",
                "bg-brand-cyan text-[#161616]",
                "bg-brand-lime text-[#161616]",
                "bg-brand-magenta text-white",
              ][index];

              return (
                <li key={title} className="flex gap-3">
                  <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${iconTone}`}>
                    <Icon size={17} />
                  </div>
                  <div>
                    <p className="font-semibold text-white">{title}</p>
                    <p className="mt-1 text-sm leading-relaxed text-[#b8b8b8]">{text}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2" aria-label="Brand colors">
            <span className="h-2.5 w-2.5 rounded-full bg-accent" />
            <span className="h-2.5 w-2.5 rounded-full bg-brand-cyan" />
            <span className="h-2.5 w-2.5 rounded-full bg-brand-lime" />
            <span className="h-2.5 w-2.5 rounded-full bg-brand-magenta" />
          </div>
          <p className="text-xs text-[#a3a3a3]">Azure Sandbox Platform · Phase 1</p>
        </div>
      </section>

      <section className="flex min-h-[50vh] items-center justify-center bg-surface px-6 py-12 lg:min-h-screen">
        <div className="w-full max-w-md">
          <div className="mb-10 lg:hidden">
            <div className="inline-flex items-center bg-white px-2 py-2">
              <Image
                src={LOGO_SRC}
                alt="S&MXencia"
                width={160}
                height={44}
                className="h-9 w-auto"
                style={{ width: "auto" }}
              />
            </div>
          </div>

          <p className="text-xs font-bold tracking-[0.18em] text-accent uppercase">
            Secure access
          </p>
          <h2 className="mt-3 text-3xl font-bold text-foreground">Sign in</h2>
          <p className="mt-2 text-muted">Use your Harris account to continue.</p>

          <button
            onClick={login}
            disabled={busy}
            className="mt-8 flex w-full items-center justify-center gap-2 rounded-md bg-accent px-6 py-3.5 font-semibold text-white shadow-accent transition hover:bg-accent-dark disabled:cursor-not-allowed disabled:opacity-60"
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