import type { Metadata } from "next";
import { Montserrat } from "next/font/google";
import MsalProviderWrapper from "@/components/auth/MsalProviderWrapper";
import "./globals.css";

const montserrat = Montserrat({
  subsets: ["latin"],
  variable: "--font-montserrat",
});

export const metadata: Metadata = {
  title: "Azure Sandbox",
  description: "Governed Azure sandbox workspace",
};
export const instant = false;

// Runs before paint so the saved theme applies without a flash.
const themeScript = `
(function () {
  try {
    var t = localStorage.getItem("theme");
    if (!t) t = "light";
    document.documentElement.setAttribute("data-theme", t);
  } catch (e) {}
})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={montserrat.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <MsalProviderWrapper>{children}</MsalProviderWrapper>
      </body>
    </html>
  );
}