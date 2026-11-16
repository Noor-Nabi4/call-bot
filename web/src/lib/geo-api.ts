/** Backend geo catalog client (public /geo + admin organization geo). */

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export type GeoCatalogItem = { key: string; name: string };

export type GeoCatalog = {
  countries: GeoCatalogItem[];
  currencies: GeoCatalogItem[];
  timezones: GeoCatalogItem[];
};

export type GeoRegionList = {
  country: string;
  regions: GeoCatalogItem[];
};

export async function fetchGeoCatalog(
  options?: { signal?: AbortSignal },
): Promise<GeoCatalog> {
  const res = await fetch(`${API}/geo/catalog`, {
    method: "GET",
    credentials: "omit",
    cache: "no-store",
    signal: options?.signal,
  });
  if (!res.ok) {
    throw new Error("Could not load geo catalog");
  }
  const data = (await res.json()) as Partial<GeoCatalog>;
  return {
    countries: Array.isArray(data.countries) ? data.countries : [],
    currencies: Array.isArray(data.currencies) ? data.currencies : [],
    timezones: Array.isArray(data.timezones) ? data.timezones : [],
  };
}

export async function fetchGeoRegions(
  country: string,
  options?: { signal?: AbortSignal; credentials?: RequestCredentials },
): Promise<GeoRegionList> {
  const code = country.trim().toUpperCase();
  const params = new URLSearchParams({ country: code });
  const res = await fetch(`${API}/geo/regions?${params.toString()}`, {
    method: "GET",
    credentials: options?.credentials ?? "omit",
    cache: "no-store",
    signal: options?.signal,
  });
  if (!res.ok) {
    throw new Error("Could not load regions");
  }
  const data = (await res.json()) as Partial<GeoRegionList>;
  return {
    country: typeof data.country === "string" ? data.country : code,
    regions: Array.isArray(data.regions) ? data.regions : [],
  };
}

export async function fetchOrgGeoRegions(
  country: string,
  options?: { signal?: AbortSignal },
): Promise<GeoRegionList> {
  const code = country.trim().toUpperCase();
  const params = new URLSearchParams({ country: code });
  const res = await fetch(
    `${API}/api/admin/organization/geo/regions?${params.toString()}`,
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      signal: options?.signal,
    },
  );
  if (!res.ok) {
    throw new Error("Could not load regions");
  }
  const data = (await res.json()) as Partial<GeoRegionList>;
  return {
    country: typeof data.country === "string" ? data.country : code,
    regions: Array.isArray(data.regions) ? data.regions : [],
  };
}
