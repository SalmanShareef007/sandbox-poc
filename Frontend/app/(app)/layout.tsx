import AuthGuard from "@/components/auth/AuthGuard";
import Sidebar from "@/components/layout/Sidebar";
import Topbar from "@/components/layout/Topbar";
import ChatWidget from "@/components/chat/ChatWidget";
import { SandboxProvider } from "@/components/providers/SandboxProvider";
import { ToastProvider } from "@/components/providers/ToastProvider";
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <ToastProvider>
        <SandboxProvider>
          <div className="flex min-h-screen bg-background">
            <Sidebar />
            <div className="flex min-w-0 flex-1 flex-col">
              <Topbar />
              <main className="flex-1 p-8">{children}</main>
            </div>
            <ChatWidget />
          </div>
        </SandboxProvider>
      </ToastProvider>
    </AuthGuard>
  );
}