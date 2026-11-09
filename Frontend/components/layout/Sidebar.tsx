"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import LOGO_SRC from "@/public/assets/S&MXencia.png";
import { isActivePath, navSections, type NavItemDef } from "@/components/layout/navItems";
import { useRole } from "@/hooks/useRole";

export function NavItem({ href, label, icon: Icon, exact }: NavItemDef) {
  const pathname = usePathname();
  const active = isActivePath(pathname, href, exact);

  return (
    <Link
      href={href}
      className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition ${
        active
          ? "bg-accent-gradient text-white shadow-accent"
          : "text-muted hover:bg-surface-2 hover:text-foreground"
      }`}
    >
      <Icon size={18} />
      {label}
    </Link>
  );
}

export function NavSections() {
  const { isAdmin, ready } = useRole();
  if (!ready) return null;

  return (
    <>
      {navSections(isAdmin).map((section, i) => (
        <div key={section.title}>
          <p
            className={`${i === 0 ? "mt-6" : "mt-8"} mb-2 px-4 text-xs font-semibold tracking-wider text-muted`}
          >
            {section.title}
          </p>
          <nav className="space-y-1" aria-label={section.title.toLowerCase()}>
            {section.items.map((item) => (
              <NavItem key={item.href} {...item} />
            ))}
          </nav>
        </div>
      ))}
    </>
  );
}

export default function Sidebar() {
  return (
    <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-border bg-surface p-4 md:flex">
      <div className="px-2 py-4">
        <Image
          src={LOGO_SRC}
          alt="S&MXencia"
          width={160}
          height={44}
          priority
          className="h-10 w-auto"
          style={{ width: "auto" }}
        />
      </div>

      <NavSections />

      <p className="mt-auto px-4 pb-2 text-xs text-muted">
        Phase 1 · Notify-only budgets &amp; expiry
      </p>
    </aside>
  );
}