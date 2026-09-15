/**
 * Thin typed fetch wrapper. Every screen goes through here rather than
 * calling `fetch` directly.
 *
 * Points at the real LendAI backend (see ../../backend). Override with
 * VITE_API_BASE_URL (e.g. in a local .env) to point at a locally-running
 * backend instead of the deployed one.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "https://lendaibackend-three.vercel.app";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

function extractErrorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const b = body as Record<string, unknown>;
    // FastAPI's HTTPException responses use "detail" (string, or a list of
    // Pydantic validation error objects for 422s); this API's own custom
    // exception handlers use "message".
    if (typeof b.message === "string") return b.message;
    if (typeof b.detail === "string") return b.detail;
    if (Array.isArray(b.detail)) {
      return b.detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
        .join("; ");
    }
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      // Omit Content-Type for FormData: the browser must set it itself
      // (multipart/form-data with a generated boundary) -- setting it
      // here would produce a boundary-less header and FastAPI would fail
      // to parse the multipart body.
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = extractErrorMessage(body, message);
    } catch {
      // ignore parse failure, fall back to statusText
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  postForm: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
};

export { ApiError };
