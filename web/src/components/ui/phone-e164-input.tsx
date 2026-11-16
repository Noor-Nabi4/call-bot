"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import {
  dialCodeForCountry,
  dialOptionsForSelect,
  joinPhoneE164,
  optionForCountry,
  splitPhoneE164,
} from "@/lib/phone-dial-codes";
import { countryFlagEmoji } from "@/lib/geo-options";

const controlBase =
  "h-9 rounded-[var(--radius-md)] border border-border bg-surface px-3 text-sm text-text-primary transition-[border-color,box-shadow] duration-150 focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand-soft disabled:bg-surface-muted disabled:text-text-muted";

type PhoneE164InputProps = {
  value: string;
  onChange: (e164: string) => void;
  onBlur?: () => void;
  disabled?: boolean;
  /** Prefer this ISO country when parsing / defaulting dial code. */
  countryIso?: string | null;
  className?: string;
  id?: string;
};

export function PhoneE164Input({
  value,
  onChange,
  onBlur,
  disabled,
  countryIso,
  className,
  id,
}: PhoneE164InputProps) {
  const seed = useMemo(
    () => splitPhoneE164(value, countryIso),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seed key
    [value, countryIso],
  );
  const [iso, setIso] = useState(seed.iso);
  const [dial, setDial] = useState(seed.dial);
  const [national, setNational] = useState(seed.national);
  const lastEmitted = useRef(joinPhoneE164(seed.dial, seed.national));

  useEffect(() => {
    const incoming = value || "";
    if (incoming === lastEmitted.current) return;
    const next = splitPhoneE164(incoming, countryIso);
    setIso(next.iso);
    setDial(next.dial);
    setNational(next.national);
    lastEmitted.current = joinPhoneE164(next.dial, next.national);
  }, [value, countryIso]);

  useEffect(() => {
    if (national.trim()) return;
    const preferred = optionForCountry(countryIso);
    if (preferred.iso === iso && preferred.dial === dial) return;
    setIso(preferred.iso);
    setDial(preferred.dial);
  }, [countryIso, national, iso, dial]);

  const options = useMemo(() => dialOptionsForSelect(iso, dial), [iso, dial]);

  function emit(nextDial: string, nextNational: string) {
    const e164 = joinPhoneE164(nextDial, nextNational);
    lastEmitted.current = e164;
    onChange(e164);
  }

  return (
    <div
      className={cn(
        "grid w-full grid-cols-[6.75rem_minmax(0,1fr)] gap-2",
        className,
      )}
    >
      <select
        id={id ? `${id}-dial` : undefined}
        aria-label="Country code"
        className={cn(controlBase, "w-full min-w-0")}
        disabled={disabled}
        value={`${iso}:${dial}`}
        onChange={(e) => {
          const [nextIso, nextDial] = e.target.value.split(":");
          const isoCode = nextIso || optionForCountry(countryIso).iso;
          const dialCode = nextDial || dialCodeForCountry(isoCode);
          setIso(isoCode);
          setDial(dialCode);
          emit(dialCode, national);
        }}
        onBlur={onBlur}
      >
        {options.map((opt) => (
          <option key={`${opt.iso}-${opt.dial}`} value={`${opt.iso}:${opt.dial}`}>
            {countryFlagEmoji(opt.iso)} +{opt.dial}
          </option>
        ))}
      </select>
      <input
        id={id}
        type="tel"
        inputMode="tel"
        autoComplete="tel-national"
        className={cn(
          controlBase,
          "w-full min-w-0 placeholder:text-text-muted",
        )}
        disabled={disabled}
        value={national}
        placeholder="Phone number"
        onChange={(e) => {
          const nextNational = e.target.value;
          setNational(nextNational);
          emit(dial, nextNational);
        }}
        onBlur={onBlur}
      />
    </div>
  );
}
