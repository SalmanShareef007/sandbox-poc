export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type TokenGetter = () => Promise<string | null>;

interface ApiOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
}

function errorDetail(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  // FastAPI validation errors: [{ loc, msg }]
  if (Array.isArray(detail)) {
    const messages = detail
      .map((d) => (typeof d?.msg === "string" ? d.msg.replace(/^Value error, /, "") : null))
      .filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  return fallback;
}

/** Calls the FastAPI backend with the signed-in user's API access token. */
export async function apiFetch<T>(
  getToken: TokenGetter,
  path: string,
  { method = "GET", body }: ApiOptions = {}
): Promise<T> {
  let token: string | null;
  try {
    token = await getToken();
  } catch (err) {
    throw new ApiError(
      err instanceof Error ? err.message : "Could not acquire an API access token.",
      0
    );
  }
  // null means MSAL is redirecting to Microsoft for interaction
  if (!token) throw new ApiError("Redirecting to Microsoft sign-in…", 0);

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/v1${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(`Cannot reach the API at ${API_BASE_URL}. Check that the backend is running.`, 0);
  }

  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    // empty or non-JSON body
  }

  if (!res.ok) throw new ApiError(errorDetail(data, `${res.status} ${res.statusText}`.trim()), res.status);

  return data as T;
}
