import type { SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

let client: Promise<SupabaseClient> | null = null;

export const supabaseConfigured = () => Boolean(url && key);

/** Read-only client (publishable key, RLS select policies), loaded on first use so pages that arrive with their
 *  data never download it. Null when the env isn't configured. */
export function supabase(): Promise<SupabaseClient> | null {
  if (!url || !key) return null;
  client ??= import("@supabase/supabase-js").then(({ createClient }) => createClient(url, key, { auth: { persistSession: false } }));
  return client;
}
