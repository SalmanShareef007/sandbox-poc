# Azure Sandbox Frontend

For the complete local API/frontend/worker testing procedure, see the
[local testing guide](../docs/local-testing.md).

Next.js interface for sandbox requests, administrator approvals, extensions,
decommissioning, notifications, and reported Azure costs. Application data comes
from the backend API; shared response types are defined in [lib/types.ts](lib/types.ts).

## Local Development

Use a supported Node.js LTS version; the deployment image uses Node.js 24.
Configure the public settings shown in [.env.example](.env.example) in your local
environment. Do not put passwords, client secrets, or database URLs in frontend
settings.

From the Frontend directory:

```powershell
npm ci
npm run dev
```

Open http://localhost:3000/login. Start the backend separately and register the
exact local redirect URI in the Entra SPA application.

| Setting | Purpose |
| --- | --- |
| `NEXT_PUBLIC_CLIENT_ID` | Entra SPA application ID |
| `NEXT_PUBLIC_TENANT_ID` | Entra tenant ID |
| `NEXT_PUBLIC_REDIRECT_URI` | Registered SPA redirect URL |
| `NEXT_PUBLIC_API_SCOPE` | Exposed delegated API scope |
| `NEXT_PUBLIC_API_BASE_URL` | Backend origin, without `/api/v1` |

Navigation uses verified roles from the API. Administrator actions are also
authorized by the backend; hiding a page is not an authorization boundary.

## Checks

```powershell
npm run lint
npm run build
```

## Deployment

The Dockerfile builds Linux standalone output and serves it on port 3000.
Supply all five public settings as Docker build arguments using the hosted API
URL and registered HTTPS redirect URL. These settings are embedded at build time;
changing runtime environment variables does not update an existing browser bundle.

For code-based hosting, build with `npm run build` and start with `npm start`.
See the [backend deployment guide](../Backend/README.md) for API configuration,
worker operation, and release safeguards.
