"use client";

import { InteractionRequiredAuthError } from "@azure/msal-browser";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import { apiRequest, graphRequest, loginRequest } from "@/config/authConfig";

export function useAuth() {
  const { instance, accounts, inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const account = instance.getActiveAccount() ?? accounts[0] ?? null;

  const login = () => instance.loginRedirect(loginRequest);

  const logout = () =>
    instance.logoutRedirect({ account: account ?? undefined });

  const getToken = async (scopes: string[]) => {
    if (!account) throw new Error("No signed-in account");
    try {
      const res = await instance.acquireTokenSilent({ scopes, account });
      return res.accessToken;
    } catch (err) {
      if (err instanceof InteractionRequiredAuthError) {
        await instance.acquireTokenRedirect({ scopes, account });
        return null; // the page redirects away to Microsoft
      }
      throw err;
    }
  };

  const getApiToken = () => getToken(apiRequest.scopes); // for FastAPI
  const getGraphToken = () => getToken(graphRequest.scopes); // for Graph

  return {
    account,
    isAuthenticated,
    inProgress,
    login,
    logout,
    getApiToken,
    getGraphToken,
  };
}