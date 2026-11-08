import { getCloudflareContext } from "@opennextjs/cloudflare";
import { handleContact } from "../../../server/handlers.ts";

export async function POST(request: Request): Promise<Response> {
  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    // Malformed JSON is treated as an empty body, which the handler rejects with 400.
  }
  const result = await handleContact(body, { db: getCloudflareContext().env.DB, log: console.error });
  return Response.json(result.body, { status: result.status });
}
