import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

/**
 * Shared, tiny in-memory cache of property types so multiple components on the
 * same page don't refetch. Refreshes explicitly when a new type is added or
 * removed.
 */
let _cache = null;
let _pending = null;
const _subs = new Set();
const _notify = () => _subs.forEach((fn) => fn(_cache));

async function _load() {
  if (_pending) return _pending;
  _pending = api.get("/property-types").then((r) => {
    _cache = Array.isArray(r.data) ? r.data : [];
    _pending = null;
    _notify();
    return _cache;
  }).catch(() => {
    _cache = [];
    _pending = null;
    _notify();
    return _cache;
  });
  return _pending;
}

export function usePropertyTypes() {
  const [types, setTypes] = useState(_cache || []);
  useEffect(() => {
    _subs.add(setTypes);
    if (_cache === null) _load();
    return () => _subs.delete(setTypes);
  }, []);
  const refresh = useCallback(async () => {
    _cache = null;
    await _load();
  }, []);
  return { types, refresh };
}

export function findTypeByName(types, name) {
  return (types || []).find((t) => t.name === name) || null;
}

export function isPortionScheme(types, name) {
  const t = findTypeByName(types, name);
  return t?.legal_scheme === "portion";
}
