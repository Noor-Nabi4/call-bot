/** ISO 3166-1 alpha-2 → ITU calling code (no leading +). */

export type DialCodeOption = {
  iso: string;
  dial: string;
  name: string;
};

/** Curated dial codes for business profile phone entry. */
export const DIAL_CODE_OPTIONS: DialCodeOption[] = [
  { iso: "US", dial: "1", name: "United States" },
  { iso: "CA", dial: "1", name: "Canada" },
  { iso: "GB", dial: "44", name: "United Kingdom" },
  { iso: "AU", dial: "61", name: "Australia" },
  { iso: "NZ", dial: "64", name: "New Zealand" },
  { iso: "IE", dial: "353", name: "Ireland" },
  { iso: "DE", dial: "49", name: "Germany" },
  { iso: "FR", dial: "33", name: "France" },
  { iso: "ES", dial: "34", name: "Spain" },
  { iso: "IT", dial: "39", name: "Italy" },
  { iso: "NL", dial: "31", name: "Netherlands" },
  { iso: "BE", dial: "32", name: "Belgium" },
  { iso: "CH", dial: "41", name: "Switzerland" },
  { iso: "AT", dial: "43", name: "Austria" },
  { iso: "SE", dial: "46", name: "Sweden" },
  { iso: "NO", dial: "47", name: "Norway" },
  { iso: "DK", dial: "45", name: "Denmark" },
  { iso: "FI", dial: "358", name: "Finland" },
  { iso: "PL", dial: "48", name: "Poland" },
  { iso: "PT", dial: "351", name: "Portugal" },
  { iso: "AE", dial: "971", name: "United Arab Emirates" },
  { iso: "SA", dial: "966", name: "Saudi Arabia" },
  { iso: "QA", dial: "974", name: "Qatar" },
  { iso: "KW", dial: "965", name: "Kuwait" },
  { iso: "BH", dial: "973", name: "Bahrain" },
  { iso: "OM", dial: "968", name: "Oman" },
  { iso: "PK", dial: "92", name: "Pakistan" },
  { iso: "IN", dial: "91", name: "India" },
  { iso: "BD", dial: "880", name: "Bangladesh" },
  { iso: "LK", dial: "94", name: "Sri Lanka" },
  { iso: "NP", dial: "977", name: "Nepal" },
  { iso: "CN", dial: "86", name: "China" },
  { iso: "JP", dial: "81", name: "Japan" },
  { iso: "KR", dial: "82", name: "South Korea" },
  { iso: "SG", dial: "65", name: "Singapore" },
  { iso: "MY", dial: "60", name: "Malaysia" },
  { iso: "ID", dial: "62", name: "Indonesia" },
  { iso: "TH", dial: "66", name: "Thailand" },
  { iso: "PH", dial: "63", name: "Philippines" },
  { iso: "VN", dial: "84", name: "Vietnam" },
  { iso: "HK", dial: "852", name: "Hong Kong" },
  { iso: "TW", dial: "886", name: "Taiwan" },
  { iso: "BR", dial: "55", name: "Brazil" },
  { iso: "MX", dial: "52", name: "Mexico" },
  { iso: "AR", dial: "54", name: "Argentina" },
  { iso: "CL", dial: "56", name: "Chile" },
  { iso: "CO", dial: "57", name: "Colombia" },
  { iso: "ZA", dial: "27", name: "South Africa" },
  { iso: "NG", dial: "234", name: "Nigeria" },
  { iso: "KE", dial: "254", name: "Kenya" },
  { iso: "EG", dial: "20", name: "Egypt" },
  { iso: "TR", dial: "90", name: "Turkey" },
  { iso: "IL", dial: "972", name: "Israel" },
  { iso: "RU", dial: "7", name: "Russia" },
];

const BY_ISO = new Map(DIAL_CODE_OPTIONS.map((o) => [o.iso, o]));

/** Longest dial first so +971 matches before +9. */
const BY_DIAL_DESC = [...DIAL_CODE_OPTIONS].sort(
  (a, b) => b.dial.length - a.dial.length,
);

export function dialCodeForCountry(iso: string | null | undefined): string {
  const code = (iso || "").trim().toUpperCase();
  return BY_ISO.get(code)?.dial || "1";
}

export function optionForCountry(iso: string | null | undefined): DialCodeOption {
  const code = (iso || "").trim().toUpperCase();
  return BY_ISO.get(code) || DIAL_CODE_OPTIONS[0]!;
}

export function digitsOnly(raw: string): string {
  return (raw || "").replace(/\D/g, "");
}

export type PhoneParts = {
  iso: string;
  dial: string;
  national: string;
};

/**
 * Split an E.164 (or loose) phone into dial + national parts.
 * Prefers `preferredIso` when the number matches that country's dial code.
 */
export function splitPhoneE164(
  raw: string | null | undefined,
  preferredIso?: string | null,
): PhoneParts {
  const trimmed = (raw || "").trim();
  const preferred = optionForCountry(preferredIso);
  if (!trimmed) {
    return { iso: preferred.iso, dial: preferred.dial, national: "" };
  }

  let digits = digitsOnly(trimmed);
  if (trimmed.startsWith("00")) {
    digits = digits.slice(2);
  }

  if (preferred.dial && digits.startsWith(preferred.dial)) {
    return {
      iso: preferred.iso,
      dial: preferred.dial,
      national: digits.slice(preferred.dial.length).replace(/^0+/, ""),
    };
  }

  for (const opt of BY_DIAL_DESC) {
    if (digits.startsWith(opt.dial) && digits.length > opt.dial.length) {
      return {
        iso: opt.iso,
        dial: opt.dial,
        national: digits.slice(opt.dial.length).replace(/^0+/, ""),
      };
    }
  }

  // No + / unknown dial — treat whole value as national under preferred country.
  return {
    iso: preferred.iso,
    dial: preferred.dial,
    national: digits.replace(/^0+/, ""),
  };
}

/** Compose E.164 from dial code + national number. Empty national → "". */
export function joinPhoneE164(dial: string, national: string): string {
  const d = digitsOnly(dial);
  const n = digitsOnly(national).replace(/^0+/, "");
  if (!n) return "";
  if (!d) return n.startsWith("+") ? n : `+${n}`;
  return `+${d}${n}`;
}

export function dialOptionsForSelect(
  currentIso: string,
  currentDial: string,
): DialCodeOption[] {
  const iso = currentIso.toUpperCase();
  if (BY_ISO.has(iso)) return DIAL_CODE_OPTIONS;
  // Preserve unknown dial so existing numbers still edit.
  return [
    { iso: iso || "XX", dial: currentDial || "1", name: `+${currentDial || "1"}` },
    ...DIAL_CODE_OPTIONS,
  ];
}
