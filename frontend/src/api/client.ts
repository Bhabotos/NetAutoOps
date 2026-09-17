export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

let getToken: () => string | null = () => null;
let onUnauthorized: () => void = () => {};

/** Wired up once by AuthProvider on mount -- lets this module (which isn't a
 * React component and can't use hooks) read the current token and react to
 * a 401 from anywhere, including a background React Query refetch. */
export function configureApiClient(options: { getToken: () => string | null; onUnauthorized: () => void }) {
  getToken = options.getToken;
  onUnauthorized = options.onUnauthorized;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /** Skip attaching the Authorization header (only /auth/login needs this). */
  skipAuth?: boolean;
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      // FastAPI/Pydantic 422 validation errors: a list of {loc, msg, ...}.
      return data.detail.map((item: { msg?: string }) => item.msg).join("; ");
    }
    return response.statusText;
  } catch {
    return response.statusText || "Request failed";
  }
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };

  if (!options.skipAuth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Network error: the API is unreachable");
  }

  if (response.status === 401) {
    onUnauthorized();
    throw new ApiError(401, await parseErrorDetail(response));
  }

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
