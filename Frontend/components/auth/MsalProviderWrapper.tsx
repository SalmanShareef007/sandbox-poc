"use client";

import { useEffect, useState } from "react";
import { PublicClientApplication } from "@azure/msal-browser";
import { MsalProvider } from "@azure/msal-react";
import {msalConfig} from "@/config/authConfig";

export default function MsalProviderWrapper({
  children,
}: {
  children: React.ReactNode;
}) {
  const [instance, setInstance] = useState<PublicClientApplication | null>(null);

  useEffect(() => {
    const init = async () => {
      const pca = new PublicClientApplication(msalConfig);
      await pca.initialize();

      // Completes the login after Microsoft redirects back to your app
      const result = await pca.handleRedirectPromise();
      if (result?.account) {
        pca.setActiveAccount(result.account);
      } else {
        const accounts = pca.getAllAccounts();
        if (accounts.length > 0) pca.setActiveAccount(accounts[0]);
      }

      setInstance(pca);
    };

    init();
  }, []);

  if (!instance) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-accent" />
    </div>
  );
}

  return <MsalProvider instance={instance}>{children}</MsalProvider>;
}