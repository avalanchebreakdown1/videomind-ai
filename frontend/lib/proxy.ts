const uuid = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}";
export function allowedRoute(path: string, method: string): boolean {
  return method === "GET" && (path === "health" || new RegExp(`^jobs/${uuid}(?:/(?:transcript|document|verification|document-source))?$`).test(path)) ||
    method === "POST" && (path === "jobs" || new RegExp(`^jobs/${uuid}/cancel$`).test(path));
}

export function backendOrigin(value = process.env.VIDEOMIND_API_URL || "http://127.0.0.1:8000"): string {
  const url = new URL(value);
  if (url.protocol !== "http:" || !["127.0.0.1", "[::1]"].includes(url.hostname) ||
      url.username || url.password || url.search || url.hash || url.pathname !== "/") {
    throw new Error("VIDEOMIND_API_URL must be a loopback HTTP origin");
  }
  return url.origin;
}

export function mutationAllowed(request: Request): boolean {
  if (request.headers.get("sec-fetch-site") === "cross-site") return false;
  const origin = request.headers.get("origin");
  try {
    // Next's internal URL may use localhost even when the browser used 127.0.0.1.
    // Match the actual, explicitly loopback Host; never trust forwarded headers.
    const url = new URL(request.url);
    const actual = new URL(`${url.protocol}//${request.headers.get("host") || url.host}`);
    if (!["localhost", "127.0.0.1", "[::1]"].includes(actual.hostname) || actual.pathname !== "/" || actual.username || actual.password) return false;
    return !origin || origin === actual.origin;
  } catch { return false; }
}

const error = (status: number, code: string, message: string) => Response.json({ error: { code, message } }, { status });
export async function proxy(request: Request, path: string): Promise<Response> {
  if (!allowedRoute(path, request.method)) return error(404, "not_found", "This endpoint is unavailable.");
  if (!mutationAllowed(request)) return error(403, "invalid_origin", "Cross-origin requests are not allowed.");
  const maxBytes = 256 * 1024 * 1024 + 65536;
  if (Number(request.headers.get("content-length")) > maxBytes) return error(413, "source_too_large", "The upload is too large.");
  let tooLarge = false;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  try {
    const query = new URL(request.url).search;
    let total = 0;
    const body = request.method === "POST" && request.body ? request.body.pipeThrough(new TransformStream({
      transform(chunk: Uint8Array, controller) {
        total += chunk.byteLength;
        if (total > maxBytes) { tooLarge = true; controller.error(new Error("Upload limit")); }
        else controller.enqueue(chunk);
      },
    })) : undefined;
    const options: RequestInit & { duplex?: "half" } = {
      method: request.method, headers, body, duplex: body ? "half" : undefined,
      cache: "no-store", redirect: "manual", signal: AbortSignal.timeout(60000),
    };
    const response = await fetch(`${backendOrigin()}/api/v1/${path}${query}`, options);
    if (response.status >= 300 && response.status < 400) return error(502, "invalid_response", "The backend returned an unexpected redirect.");
    const outgoing = new Headers({ "Cache-Control": "no-store" });
    for (const key of ["content-type", "content-disposition"]) {
      const value = response.headers.get(key); if (value) outgoing.set(key, value);
    }
    return new Response(response.body, { status: response.status, headers: outgoing });
  } catch {
    return tooLarge ? error(413, "source_too_large", "The upload is too large.") :
      error(503, "backend_unavailable", "Cannot reach the processing service. Check that the backend is running and try again.");
  }
}
