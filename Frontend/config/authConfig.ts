import { Configuration } from "@azure/msal-browser";

export const msalConfig: Configuration = {
  auth: {
    clientId: process.env.NEXT_PUBLIC_CLIENT_ID!,
    authority: `https://login.microsoftonline.com/${process.env.NEXT_PUBLIC_TENANT_ID}`,
    redirectUri: process.env.NEXT_PUBLIC_REDIRECT_URI,
    postLogoutRedirectUri: process.env.NEXT_PUBLIC_REDIRECT_URI,
  },
  cache: { cacheLocation: "sessionStorage" },
};

export const loginRequest = {
  scopes: ["openid", "profile", "User.Read"],
};

export const apiRequest = {
  scopes: [process.env.NEXT_PUBLIC_API_SCOPE!],
};

export const graphRequest = {
  scopes: ["User.Read"],
};