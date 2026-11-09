"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import LOGO_SRC from "@/public/assets/S&MXencia.png";
import { NavSections } from "@/components/layout/Sidebar";

export default function MobileNav() {
  const pathname = usePathname();
  // Tied to the path it was opened on, so any route change closes the drawer.
  const [openedOn, setOpenedOn] = useState<string | null>(null);
  const open = openedOn === pathname;
  const close = () => setOpenedOn(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpenedOn(null);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        onClick={() => setOpenedOn(pathname)}
        aria-label="Open menu"
        aria-expanded={open}
        className="p-2 text-muted transition hover:bg-surface-2 hover:text-foreground md:hidden"
      >
        <Menu size={22} />
      </button>

      <div
        className={`fixed inset-0 z-40 md:hidden ${open ? "" : "pointer-events-none"}`}
        aria-hidden={!open}
      >
        <div
          onClick={close}
          className={`absolute inset-0 bg-black/60 transition-opacity ${
            open ? "opacity-100" : "opacity-0"
          }`}
        />
        <aside
          className={`absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col border-r border-border bg-surface p-4 shadow-card transition-transform ${
            open ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="flex items-center justify-between px-2 py-4">
            <Image
              src={LOGO_SRC}
              alt="S&MXencia"
              width={160}
              height={44}
              className="h-10 w-auto"
              style={{ width: "auto" }}
            />
            <button
              onClick={close}
              aria-label="Close menu"
              className="p-2 text-muted transition hover:text-foreground"
            >
              <X size={20} />
            </button>
          </div>

          <NavSections />
        </aside>
      </div>
    </>
  );
}
