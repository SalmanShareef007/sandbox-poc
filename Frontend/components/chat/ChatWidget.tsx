"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Bot, MessageCircle, RotateCcw, Send, X } from "lucide-react";
import { useSandboxes } from "@/components/providers/SandboxProvider";
import { useRole } from "@/hooks/useRole";
import type { Sandbox } from "@/lib/types";

interface ChatAction {
  label: string;
  href: string;
}

interface Message {
  id: number;
  role: "user" | "bot";
  text: string;
  actions?: ChatAction[];
}

type Reply = Pick<Message, "text" | "actions">;

const welcome: Message = {
  id: 0,
  role: "bot",
  text: "Hi! I'm your Sandbox assistant. Ask me about your sandboxes, budgets or requests.",
};

const openSandboxes: ChatAction = { label: "Open My sandboxes", href: "/sandboxes" };

const suggestions = [
  "What is my budget status?",
  "Which sandbox expires soon?",
  "How do I request a sandbox?",
  "What are my pending requests?",
];

function sandboxReply(input: string, sandboxes: Sandbox[]): Reply {
  const q = input.toLowerCase();

  if (q.includes("help") || q.includes("faq") || q.includes("contact")) {
    return {
      text: "The Help page answers common questions about budgets, expiry, approvals and tags. For anything else, contact sandbox-admins@company.com.",
      actions: [{ label: "Open Help", href: "/help" }],
    };
  }

  if (q.includes("budget") || q.includes("spend")) {
    const live = sandboxes.filter((s) => s.status === "Active" || s.status === "Expiring");
    const lines = live.map(
      (s) => s.spent === null
        ? `${s.name}: cost data unavailable`
        : `${s.name}: ${s.costCurrency ?? "USD"} ${s.spent.toFixed(2)} spent; budget ${s.budgetCurrency ?? "USD"} ${s.budget}`
    );
    return {
      text: lines.length ? `Latest reported month-to-date costs:\n${lines.join("\n")}` : "No active sandboxes have reported costs.",
      actions: [openSandboxes],
    };
  }

  if (q.includes("expire") || q.includes("expiry") || q.includes("extension")) {
    const s = sandboxes.find((x) => x.status === "Expiring");
    return s
      ? {
          text: `${s.name} expires in ${s.daysLeft} days (${s.expiry}). You can request an extension from its sandbox page.`,
          actions: [{ label: "Open the sandbox", href: `/sandboxes/${s.id}` }],
        }
      : { text: "None of your sandboxes are expiring soon." };
  }

  if (q.includes("pending") || q.includes("approval")) {
    const p = sandboxes.filter((s) => s.status === "Pending");
    return {
      text: p.length
        ? `You have ${p.length} pending request(s): ${p.map((s) => s.name).join(", ")}. They are waiting for IT approval.`
        : "You have no pending requests.",
      actions: [openSandboxes],
    };
  }

  if (q.includes("request") || q.includes("create") || q.includes("new")) {
    return {
      text: "Submit a resource-group sandbox request with your business unit, cost centre, workload, budget and duration for administrator approval.",
      actions: [{ label: "Open New request", href: "/requests/new" }],
    };
  }

  return {
    text: "I can help with budgets, expiry dates, pending requests, and how to request a sandbox. Try one of the suggestions below.",
  };
}

export default function ChatWidget() {
  const { sandboxes } = useSandboxes();
  const { isAdmin, ready } = useRole();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [messages, setMessages] = useState<Message[]>([welcome]);
  const endRef = useRef<HTMLDivElement>(null);
  const replyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typing, open]);

  useEffect(() => () => {
    if (replyTimer.current) clearTimeout(replyTimer.current);
  }, []);

  const send = (text: string) => {
    const value = text.trim();
    if (!value || typing) return;

    setMessages((m) => [...m, { id: Date.now(), role: "user", text: value }]);
    setInput("");
    setTyping(true);

    replyTimer.current = setTimeout(() => {
      setMessages((m) => [...m, { id: Date.now() + 1, role: "bot", ...sandboxReply(value, sandboxes) }]);
      setTyping(false);
      replyTimer.current = null;
    }, 700);
  };

  const clearChat = () => {
    if (replyTimer.current) clearTimeout(replyTimer.current);
    replyTimer.current = null;
    setTyping(false);
    setInput("");
    setMessages([welcome]);
  };

  if (!ready || isAdmin) return null;

  return (
    <>
      {/* Chat panel */}
      {open && (
        <div className="fixed right-6 bottom-24 z-30 flex h-[32rem] w-[22rem] max-w-[calc(100vw-3rem)] flex-col border border-border bg-surface shadow-card">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <div className="bg-accent-gradient flex h-8 w-8 items-center justify-center text-white">
                <Bot size={16} />
              </div>
              <div className="leading-tight">
                <p className="text-sm font-semibold text-foreground">Sandbox assistant</p>
                <p className="text-xs text-muted">Sandbox status</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={clearChat}
                aria-label="Clear chat"
                title="Clear chat"
                className="p-1 text-muted transition hover:text-foreground"
              >
                <RotateCcw size={16} />
              </button>
              <button
                onClick={() => setOpen(false)}
                aria-label="Close chat"
                className="p-1 text-muted transition hover:text-foreground"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
              >
                <p
                  className={`max-w-[85%] whitespace-pre-line px-3 py-2 text-sm ${
                    m.role === "user"
                      ? "bg-accent-gradient text-white"
                      : "border border-border bg-surface-2 text-foreground"
                  }`}
                >
                  {m.text}
                </p>
                {m.actions && m.actions.length > 0 && (
                  <div className="mt-2 flex max-w-[85%] flex-wrap gap-2">
                    {m.actions.map((a) => (
                      <Link
                        key={a.href + a.label}
                        href={a.href}
                        onClick={() => setOpen(false)}
                        className="border border-accent/40 bg-accent/10 px-2.5 py-1 text-xs font-medium text-accent-dark transition hover:border-accent dark:text-accent-light"
                      >
                        {a.label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {typing && (
              <div className="flex justify-start">
                <p className="border border-border bg-surface-2 px-3 py-2 text-sm text-muted">
                  Typing...
                </p>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {messages.length === 1 && (
            <div className="flex flex-wrap gap-2 px-4 pb-3">
              {suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="border border-border bg-background px-2.5 py-1 text-xs text-foreground transition hover:border-accent"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          <div className="flex gap-2 border-t border-border p-3">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send(input)}
              placeholder="Ask something..."
              className="min-w-0 flex-1 border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted focus:border-accent focus:outline-none"
            />
            <button
              onClick={() => send(input)}
              disabled={!input.trim() || typing}
              aria-label="Send"
              className="bg-accent-gradient flex w-10 items-center justify-center text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      )}

      {/* Floating button */}
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Open assistant"
        className="bg-accent-gradient fixed right-6 bottom-6 z-30 flex h-14 w-14 items-center justify-center text-white shadow-accent transition hover:brightness-110"
      >
        {open ? <X size={24} /> : <MessageCircle size={24} />}
      </button>
    </>
  );
}