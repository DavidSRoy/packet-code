import { getCloudflareContext } from "@opennextjs/cloudflare";
import { INTERSECTIONS } from "../../../server/intersection-index.ts";
import { handleSignup } from "../../../server/handlers.ts";

export async function POST(request: Request): Promise<Response> {
  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    // Malformed JSON is treated as an empty body, which the handler rejects with 400.
  }
  const result = await handleSignup(body, {
    db: getCloudflareContext().env.DB,
    fetchFn: fetch,
    intersections: INTERSECTIONS,
    log: console.error,
  });
  return Response.json(result.body, { status: result.status });
}
