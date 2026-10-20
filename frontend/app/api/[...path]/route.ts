import { proxy } from "../../../lib/proxy";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
async function handle(request: Request, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, (await context.params).path.join("/"));
}
export const GET = handle;
export const POST = handle;
