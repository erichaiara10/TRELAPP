import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/**
 * Fetch editable per-page content from /api/page/{slug}.
 * Returns { sections, loading }. The home page is intentionally returned
 * without static defaults so staff-managed content remains authoritative.
 */
export function usePage(slug) {
  const [sections, setSections] = useState({});
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    api.get(`/page/${slug}`)
      .then((r) => setSections(r.data?.sections || {}))
      .catch(() => setSections({}))
      .finally(() => setLoading(false));
  }, [slug]);
  return { sections, loading };
}
