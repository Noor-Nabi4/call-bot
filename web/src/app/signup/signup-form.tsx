"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { signup as signupApi } from "@/lib/api";
import { signup as copy } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";
import {
  resolveInitialTimezone,
  timezoneOptionsForSelect,
} from "@/lib/timezones";

const OPS =
  process.env.NEXT_PUBLIC_OPS_URL?.replace(/\/$/, "") ||
  "http://localhost:3001";

const PLAN_OPTIONS = [
  { key: "starter", name: "Starter", price: "$99", detail: "250 min" },
  {
    key: "growth",
    name: "Growth",
    price: "$249",
    detail: "800 min",
    popular: true,
  },
  { key: "pro", name: "Pro", price: "$499", detail: "2k min" },
] as const;

type PlanKey = (typeof PLAN_OPTIONS)[number]["key"];

type SignupFormValues = {
  plan_key: PlanKey;
  business_name: string;
  slug: string;
  timezone: string;
  name: string;
  email: string;
  password: string;
};

const fieldClass =
  "mt-1 w-full border-0 border-b border-line bg-transparent px-0 py-2 text-sm text-ink outline-none transition-colors placeholder:text-muted/60 focus:border-teal";

const selectClass = `${fieldClass} cursor-pointer appearance-none bg-[length:0.65rem] bg-[right_0_center] bg-no-repeat pr-4`;

const selectChevron = {
  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%235c6f67' d='M1 1l5 5 5-5'/%3E%3C/svg%3E")`,
} as const;

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

function resolveInitialPlan(raw: string | null): PlanKey {
  const plan = (raw || "growth").toLowerCase();
  return PLAN_OPTIONS.some((p) => p.key === plan)
    ? (plan as PlanKey)
    : "growth";
}

export default function SignupForm() {
  const params = useSearchParams();
  const canceled = params.get("canceled") === "1";
  const initialPlan = resolveInitialPlan(params.get("plan"));
  const initialTimezone = resolveInitialTimezone();

  const {
    register,
    handleSubmit,
    setValue,
    setError,
    clearErrors,
    watch,
    getFieldState,
    formState: { errors, isSubmitting, isSubmitSuccessful },
  } = useForm<SignupFormValues>({
    defaultValues: {
      plan_key: initialPlan,
      business_name: "",
      slug: "",
      timezone: initialTimezone,
      name: "",
      email: "",
      password: "",
    },
    mode: "onSubmit",
  });

  const planKey = watch("plan_key");
  const timezone = watch("timezone");
  const selectedPlan =
    PLAN_OPTIONS.find((p) => p.key === planKey) ?? PLAN_OPTIONS[1];
  const timezoneOptions = useMemo(
    () => timezoneOptionsForSelect(timezone),
    [timezone],
  );

  const businessNameRegister = register("business_name", {
    required: "Business name is required",
    minLength: { value: 1, message: "Business name is required" },
    maxLength: { value: 255, message: "Business name is too long" },
  });

  const onSubmit = handleSubmit(async (values) => {
    clearErrors("root");
    try {
      const { checkout_url } = await signupApi({
        business_name: values.business_name,
        slug: values.slug,
        timezone: values.timezone,
        name: values.name,
        email: values.email,
        password: values.password,
        plan_key: values.plan_key,
      });
      window.location.assign(checkout_url);
    } catch (err) {
      setError("root", {
        message: safeUserError(err, copy.failedMessage),
      });
    }
  });

  const rootError = errors.root?.message;
  const busy = isSubmitting || isSubmitSuccessful;

  return (
    <main
      id="main-content"
      className="grid h-[100svh] overflow-hidden lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]"
    >
      <aside className="relative isolate hidden overflow-hidden lg:block">
        <div className="hero-stage" aria-hidden="true">
          <div className="hero-glow" />
        </div>
        <div className="relative z-[1] flex h-full flex-col justify-between px-10 py-8 xl:px-12">
          <p className="font-display text-2xl font-semibold tracking-[-0.03em] text-[#f3f8f5]">
            <Link href="/" className="text-inherit no-underline">
              {copy.brand}
            </Link>
          </p>
          <div className="max-w-sm">
            <h2 className="font-display m-0 text-[clamp(1.75rem,2.5vw,2.35rem)] font-semibold leading-[1.05] tracking-[-0.03em] text-[#f3f8f5]">
              {copy.asideTitle}
            </h2>
            <p className="mt-3 m-0 text-sm leading-relaxed text-[#afc2ba]">
              {copy.asideBody}
            </p>
            <div className="mt-6 border-t border-[rgba(185,225,210,0.2)] pt-4">
              <p className="m-0 font-mono text-[10px] tracking-[0.14em] text-[#71f0ca] uppercase">
                Selected
              </p>
              <p className="mt-1 m-0 font-display text-xl font-semibold text-[#f3f8f5]">
                {selectedPlan.name}{" "}
                <span className="text-[#afc2ba]">{selectedPlan.price}/mo</span>
              </p>
            </div>
          </div>
        </div>
      </aside>

      <section className="flex h-[100svh] min-h-0 flex-col overflow-y-auto bg-paper text-ink">
        <header className="flex shrink-0 items-center justify-between gap-4 px-5 py-4 sm:px-8 lg:px-10">
          <p className="font-display text-xl font-semibold tracking-[-0.03em] lg:hidden">
            <Link href="/" className="text-inherit no-underline">
              {copy.brand}
            </Link>
          </p>
          <nav
            aria-label="Account"
            className="ml-auto flex items-center gap-4 text-sm"
          >
            <Link
              href="/#pricing"
              className="font-medium text-muted hover:text-ink"
            >
              {copy.comparePlans}
            </Link>
            <a
              href={`${OPS}/login`}
              className="font-medium text-muted hover:text-ink"
            >
              Sign in
            </a>
          </nav>
        </header>

        <div className="mx-auto w-full max-w-lg flex-1 px-5 pb-6 sm:px-8 lg:px-10 lg:pb-8">
          <h1 className="font-display m-0 text-2xl font-semibold tracking-[-0.03em] sm:text-[1.65rem]">
            {copy.heading}
          </h1>
          <p className="mt-1.5 m-0 text-sm text-muted">{copy.supporting}</p>

          {canceled ? (
            <p
              className="mt-3 border-l-2 border-teal pl-2.5 text-xs text-muted"
              role="status"
            >
              {copy.canceled}
            </p>
          ) : null}

          <form onSubmit={onSubmit} className="mt-5 grid gap-5" noValidate>
            <fieldset className="m-0 border-0 p-0">
              <legend className="mb-2 block text-xs font-medium uppercase tracking-wide text-muted">
                {copy.plan}
              </legend>
              <input
                type="hidden"
                {...register("plan_key", { required: true })}
              />
              <div
                className="grid grid-cols-3 gap-2"
                role="radiogroup"
                aria-label={copy.plan}
              >
                {PLAN_OPTIONS.map((plan) => {
                  const selected = planKey === plan.key;
                  return (
                    <button
                      key={plan.key}
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      onClick={() =>
                        setValue("plan_key", plan.key, {
                          shouldDirty: true,
                          shouldValidate: true,
                        })
                      }
                      className={
                        selected
                          ? "rounded-md border-2 border-teal bg-fog px-2 py-2.5 text-left"
                          : "rounded-md border border-line bg-transparent px-2 py-2.5 text-left hover:border-teal/40"
                      }
                    >
                      <span className="block text-xs font-semibold text-ink">
                        {plan.name}
                      </span>
                      <span className="mt-0.5 block font-display text-base font-semibold leading-none text-ink">
                        {plan.price}
                      </span>
                      <span className="mt-0.5 block text-[10px] text-muted">
                        {plan.detail}
                        {"popular" in plan && plan.popular ? " · ★" : ""}
                      </span>
                    </button>
                  );
                })}
              </div>
            </fieldset>

            <fieldset className="m-0 grid gap-3 border-0 p-0 sm:grid-cols-2">
              <legend className="sr-only">Business</legend>
              <label className="block text-xs font-medium text-ink sm:col-span-2">
                {copy.businessName}
                <input
                  {...businessNameRegister}
                  onChange={(e) => {
                    void businessNameRegister.onChange(e);
                    if (!getFieldState("slug").isDirty) {
                      setValue("slug", slugify(e.target.value), {
                        shouldValidate: false,
                      });
                    }
                  }}
                  className={fieldClass}
                  autoComplete="organization"
                  placeholder="Acme HVAC"
                />
                {errors.business_name ? (
                  <span className="mt-1 block text-[11px] text-[#9b2c2c]">
                    {errors.business_name.message}
                  </span>
                ) : null}
              </label>

              <label className="block text-xs font-medium text-ink">
                {copy.businessId}
                <input
                  {...register("slug", {
                    required: "Business ID is required",
                    pattern: {
                      value: /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
                      message: "Use lowercase letters, numbers, and hyphens",
                    },
                    minLength: {
                      value: 2,
                      message: "Business ID must be at least 2 characters",
                    },
                    maxLength: {
                      value: 64,
                      message: "Business ID must be 64 characters or fewer",
                    },
                    setValueAs: (value: string) => slugify(value),
                  })}
                  className={`${fieldClass} font-mono`}
                  autoComplete="organization"
                  placeholder="acme-hvac"
                />
                {errors.slug ? (
                  <span className="mt-1 block text-[11px] text-[#9b2c2c]">
                    {errors.slug.message}
                  </span>
                ) : null}
              </label>

              <label className="block text-xs font-medium text-ink">
                {copy.timezone}
                <select
                  {...register("timezone", {
                    required: "Timezone is required",
                  })}
                  className={selectClass}
                  style={selectChevron}
                >
                  {timezoneOptions.map((zone) => (
                    <option key={zone.value} value={zone.value}>
                      {zone.label}
                    </option>
                  ))}
                </select>
                {errors.timezone ? (
                  <span className="mt-1 block text-[11px] text-[#9b2c2c]">
                    {errors.timezone.message}
                  </span>
                ) : null}
              </label>
            </fieldset>

            <fieldset className="m-0 grid gap-3 border-0 p-0 sm:grid-cols-2">
              <legend className="sr-only">Account</legend>
              <label className="block text-xs font-medium text-ink sm:col-span-2">
                {copy.yourName}
                <input
                  {...register("name", {
                    required: "Name is required",
                    minLength: { value: 1, message: "Name is required" },
                    maxLength: {
                      value: 255,
                      message: "Name is too long",
                    },
                  })}
                  className={fieldClass}
                  autoComplete="name"
                />
                {errors.name ? (
                  <span className="mt-1 block text-[11px] text-[#9b2c2c]">
                    {errors.name.message}
                  </span>
                ) : null}
              </label>

              <label className="block text-xs font-medium text-ink">
                {copy.email}
                <input
                  type="email"
                  {...register("email", {
                    required: "Email is required",
                    pattern: {
                      value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                      message: "Enter a valid email",
                    },
                  })}
                  className={fieldClass}
                  autoComplete="email"
                />
                {errors.email ? (
                  <span className="mt-1 block text-[11px] text-[#9b2c2c]">
                    {errors.email.message}
                  </span>
                ) : null}
              </label>

              <label className="block text-xs font-medium text-ink">
                {copy.password}
                <input
                  type="password"
                  {...register("password", {
                    required: "Password is required",
                    minLength: {
                      value: 8,
                      message: "Password must be at least 8 characters",
                    },
                  })}
                  className={fieldClass}
                  autoComplete="new-password"
                  placeholder="8+ characters"
                />
                {errors.password ? (
                  <span className="mt-1 block text-[11px] text-[#9b2c2c]">
                    {errors.password.message}
                  </span>
                ) : null}
              </label>
            </fieldset>

            {rootError ? (
              <p className="m-0 text-xs text-[#9b2c2c]" role="alert">
                <span className="font-semibold">{copy.failedTitle}. </span>
                {rootError}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={busy}
              className="inline-flex items-center justify-center rounded-md bg-[#45d6ac] px-5 py-3 text-sm font-semibold text-[#07120f] transition-colors hover:bg-[#71f0ca] disabled:opacity-60"
            >
              {busy ? copy.submitting : copy.submit}
            </button>

            <p className="m-0 text-center text-xs text-muted lg:hidden">
              <a href={`${OPS}/login`} className="font-medium text-teal">
                {copy.signIn}
              </a>
            </p>
          </form>
        </div>
      </section>
    </main>
  );
}
