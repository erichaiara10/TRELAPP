import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/**
 * Fetch editable per-page content from /api/page/{slug}.
 * Returns { sections, loading }. Defaults are already merged server-side,
 * so callers get a fully-populated `sections` object even if never edited.
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
