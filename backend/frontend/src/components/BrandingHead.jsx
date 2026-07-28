import { useEffect } from "react";

/**
 * Applies dynamic branding (favicon, OG tags, page title) to the document head
 * from site content values loaded at runtime.
 */
export default function BrandingHead({ site }) {
  useEffect(() => {
    if (!site) return;

    // Favicon
    if (site.favicon_url) {
      let link = document.querySelector("link[rel='icon']");
      if (!link) {
        link = document.createElement("link");
        link.rel = "icon";
        document.head.appendChild(link);
      }
      link.href = site.favicon_url;
    }

    // Title (agency + tagline)
    if (site.agency_name) {
      const title = site.tagline ? `${site.agency_name} — ${site.tagline}` : site.agency_name;
      document.title = title;
    }

    // Meta description
    const setMeta = (attr, name, value) => {
      if (!value) return;
      let m = document.querySelector(`meta[${attr}='${name}']`);
      if (!m) {
        m = document.createElement("meta");
        m.setAttribute(attr, name);
        document.head.appendChild(m);
      }
      m.setAttribute("content", value);
    };

    setMeta("name", "description", site.og_description || "");
    setMeta("property", "og:title", site.agency_name || "");
    setMeta("property", "og:description", site.og_description || "");
    setMeta("property", "og:image", site.og_image_url || site.logo_url || "");
    setMeta("property", "og:type", "website");
    setMeta("name", "twitter:card", "summary_large_image");
    setMeta("name", "twitter:title", site.agency_name || "");
    setMeta("name", "twitter:description", site.og_description || "");
    setMeta("name", "twitter:image", site.og_image_url || site.logo_url || "");
  }, [site]);

  return null;
}
