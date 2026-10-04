"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { signup as signupApi } from "@/lib/marketing-api";
import { track } from "@/lib/analytics";
import { signup as copy } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";
import { opsLoginUrl } from "@/lib/site-urls";
import {
  resolveInitialTimezone,
  timezoneOptionsForSelect,
} from "@/lib/timezones";

const PLAN_OPTIONS = [
  { key: "starter", name: "Starter", price: "$99", detail: "250 min / mo" },
  {
    key: "growth",
    name: "Growth",
    price: "$249",
    detail: "800 min / mo",
    popular: true,
  },
  { key: "pro", name: "Pro", price: "$499", detail: "2,000 min / mo" },
] as const;

type PlanKey = (typeof PLAN_OPTIONS)[number]["key"];
type Step = 0 | 1 | 2 | 3;

type SignupFormValues = {
  plan_key: PlanKey;
  business_name: string;
  slug: string;
  timezone: string;
  industry: string;
  name: string;
  email: string;
  password: string;
};

const fieldClass =
  "mt-1.5 w-full rounded-[var(--radius-md)] border border-line bg-surface px-3.5 py-2.5 text-sm text-ink outline-none transition-colors placeholder:text-muted/60 focus:border-teal";

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

const STEPS = [
  copy.stepBusiness,
  copy.stepIndustry,
  copy.stepPlan,
  copy.stepAccount,
] as const;

export default function SignupForm() {
  const params = useSearchParams();
  const canceled = params.get("canceled") === "1";
  const initialPlan = resolveInitialPlan(params.get("plan"));
  const initialTimezone = resolveInitialTimezone();
  const [step, setStep] = useState<Step>(0);

  const {
    register,
    handleSubmit,
    setValue,
    setError,
    clearErrors,
    trigger,
    watch,
    formState: { errors, isSubmitting, isSubmitSuccessful },
  } = useForm<SignupFormValues>({
    defaultValues: {
      plan_key: initialPlan,
      business_name: "",
      slug: "",
      timezone: initialTimezone,
      industry: "home_services",
      name: "",
      email: "",
      password: "",
    },
    mode: "onSubmit",
  });

  const planKey = watch("plan_key");
  const timezone = watch("timezone");
  const industry = watch("industry");
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

  async function goNext() {
    clearErrors("root");
    let valid = false;
    if (step === 0) {
      valid = await trigger(["business_name", "slug", "timezone"]);
    } else if (step === 1) {
      valid = await trigger(["industry"]);
    } else if (step === 2) {
      valid = await trigger(["plan_key"]);
    }
    if (!valid) return;
    const next = (step + 1) as Step;
    setStep(next);
    track("signup_step", { step: STEPS[next] });
  }

  function goBack() {
    if (step === 0) return;
    setStep((step - 1) as Step);
  }

  const onSubmit = handleSubmit(async (values) => {
    clearErrors("root");
    track("signup_submit", {
      plan: values.plan_key,
      industry: values.industry,
    });
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
      track("signup_error");
      setError("root", {
        message: safeUserError(err, copy.failedMessage),
      });
    }
  });

  return (
    <div className="min-h-[100svh] bg-bg">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4 px-6 py-4 sm:px-8">
          <Link href="/" className="inline-flex items-center no-underline" aria-label={copy.brand}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/branding/logo-light.svg"
              alt={copy.brand}
              width={148}
              height={32}
              className="h-7 w-auto"
            />
          </Link>
          <Link
            href={opsLoginUrl()}
            className="text-sm font-medium text-muted transition-colors hover:text-ink"
          >
            Sign in
          </Link>
        </div>
      </header>

      <main className="mx-auto grid w-full max-w-5xl gap-10 px-6 py-10 sm:px-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-14 lg:py-14">
        <aside className="hidden lg:block">
          <p className="m-0 inline-flex rounded-full bg-teal-soft px-3 py-1 text-[11px] font-semibold tracking-[0.1em] text-teal-deep uppercase">
            Onboarding
          </p>
          <h1 className="font-display mt-4 m-0 text-[clamp(1.8rem,3vw,2.4rem)] font-semibold leading-[1.1] tracking-[-0.04em] text-ink">
            {copy.asideTitle}
          </h1>
          <p className="mt-4 m-0 text-base leading-relaxed text-muted">
            {copy.asideBody}
          </p>
          <ol className="mt-10 m-0 list-none space-y-3 p-0">
            {STEPS.map((label, index) => {
              const active = index === step;
              const done = index < step;
              return (
                <li
                  key={label}
                  className={`flex items-center gap-3 rounded-[var(--radius-md)] px-3 py-2.5 text-sm ${
                    active
                      ? "bg-teal-soft font-semibold text-teal-deep"
                      : done
                        ? "text-ink"
                        : "text-muted"
                  }`}
                >
                  <span
                    className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                      active || done
                        ? "bg-teal text-white"
                        : "bg-bg text-muted"
                    }`}
                  >
                    {done ? "✓" : index + 1}
                  </span>
                  {label}
                </li>
              );
            })}
          </ol>
        </aside>

        <section className="card-surface p-6 sm:p-8">
          <div className="mb-6 lg:hidden">
            <p className="m-0 text-xs font-semibold tracking-[0.1em] text-teal uppercase">
              Step {step + 1} of {STEPS.length}
            </p>
            <h1 className="font-display mt-2 m-0 text-2xl font-semibold tracking-[-0.03em] text-ink">
              {STEPS[step]}
            </h1>
          </div>

          <div className="mb-8 hidden lg:block">
            <h2 className="font-display m-0 text-2xl font-semibold tracking-[-0.03em] text-ink">
              {copy.heading}
            </h2>
            <p className="mt-2 m-0 text-sm text-muted">{copy.supporting}</p>
          </div>

          {canceled ? (
            <p
              className="mb-5 rounded-[var(--radius-md)] border border-line bg-bg px-3 py-2 text-sm text-muted"
              role="status"
            >
              {copy.canceled}
            </p>
          ) : null}

          <form onSubmit={onSubmit} className="grid gap-5" noValidate>
            {step === 0 ? (
              <>
                <label className="block text-sm font-medium text-ink">
                  {copy.businessName}
                  <input
                    className={fieldClass}
                    autoComplete="organization"
                    {...businessNameRegister}
                    onChange={(event) => {
                      businessNameRegister.onChange(event);
                      setValue("slug", slugify(event.target.value), {
                        shouldValidate: true,
                      });
                    }}
                  />
                  {errors.business_name ? (
                    <span className="mt-1 block text-xs text-red-600">
                      {errors.business_name.message}
                    </span>
                  ) : null}
                </label>
                <label className="block text-sm font-medium text-ink">
                  {copy.businessId}
                  <input
                    className={fieldClass}
                    autoComplete="off"
                    {...register("slug", {
                      required: "Workspace ID is required",
                      pattern: {
                        value: /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
                        message: copy.businessIdHint,
                      },
                    })}
                  />
                  <span className="mt-1 block text-xs text-muted">
                    {copy.businessIdHint}
                  </span>
                  {errors.slug ? (
                    <span className="mt-1 block text-xs text-red-600">
                      {errors.slug.message}
                    </span>
                  ) : null}
                </label>
                <label className="block text-sm font-medium text-ink">
                  {copy.timezone}
                  <select className={fieldClass} {...register("timezone")}>
                    {timezoneOptions.map((tz) => (
                      <option key={tz.value} value={tz.value}>
                        {tz.label}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            ) : null}

            {step === 1 ? (
              <fieldset className="m-0 border-0 p-0">
                <legend className="text-sm font-medium text-ink">
                  {copy.industry}
                </legend>
                <p className="mt-1 m-0 text-xs text-muted">{copy.industryHint}</p>
                <div className="mt-4 grid gap-2 sm:grid-cols-2">
                  {copy.industries.map((item) => {
                    const selected = industry === item.key;
                    return (
                      <label
                        key={item.key}
                        className={`cursor-pointer rounded-[var(--radius-md)] border px-3 py-3 text-sm transition-colors ${
                          selected
                            ? "border-teal bg-teal-soft font-semibold text-teal-deep"
                            : "border-line bg-surface text-ink hover:border-teal/40"
                        }`}
                      >
                        <input
                          type="radio"
                          value={item.key}
                          className="sr-only"
                          {...register("industry", { required: true })}
                        />
                        {item.label}
                      </label>
                    );
                  })}
                </div>
              </fieldset>
            ) : null}

            {step === 2 ? (
              <fieldset className="m-0 border-0 p-0">
                <legend className="text-sm font-medium text-ink">{copy.plan}</legend>
                <div className="mt-4 grid gap-3">
                  {PLAN_OPTIONS.map((plan) => {
                    const selected = planKey === plan.key;
                    return (
                      <label
                        key={plan.key}
                        className={`flex cursor-pointer items-center justify-between gap-3 rounded-[var(--radius-lg)] border px-4 py-4 transition-colors ${
                          selected
                            ? "border-teal bg-teal-soft shadow-[var(--shadow-sm)]"
                            : "border-line bg-surface hover:border-teal/40"
                        }`}
                      >
                        <span>
                          <span className="flex items-center gap-2">
                            <span className="font-semibold text-ink">
                              {plan.name}
                            </span>
                            {"popular" in plan && plan.popular ? (
                              <span className="rounded-full bg-teal px-2 py-0.5 text-[10px] font-semibold tracking-wide text-white uppercase">
                                Popular
                              </span>
                            ) : null}
                          </span>
                          <span className="mt-1 block text-sm text-muted">
                            {plan.detail}
                          </span>
                        </span>
                        <span className="font-display text-xl font-semibold text-ink">
                          {plan.price}
                          <span className="ml-1 text-sm font-medium text-muted">
                            /mo
                          </span>
                        </span>
                        <input
                          type="radio"
                          value={plan.key}
                          className="sr-only"
                          {...register("plan_key", {
                            onChange: () => {
                              track("pricing_plan_select", {
                                plan: plan.key,
                                source: "signup",
                              });
                            },
                          })}
                        />
                      </label>
                    );
                  })}
                </div>
                <p className="mt-3 m-0 text-sm text-muted">
                  Selected: {selectedPlan.name}.{" "}
                  <Link href="/pricing" className="font-medium text-teal">
                    {copy.comparePlans}
                  </Link>
                </p>
              </fieldset>
            ) : null}

            {step === 3 ? (
              <>
                <label className="block text-sm font-medium text-ink">
                  {copy.yourName}
                  <input
                    className={fieldClass}
                    autoComplete="name"
                    {...register("name", {
                      required: "Name is required",
                      minLength: { value: 1, message: "Name is required" },
                    })}
                  />
                  {errors.name ? (
                    <span className="mt-1 block text-xs text-red-600">
                      {errors.name.message}
                    </span>
                  ) : null}
                </label>
                <label className="block text-sm font-medium text-ink">
                  {copy.email}
                  <input
                    type="email"
                    className={fieldClass}
                    autoComplete="email"
                    {...register("email", {
                      required: "Email is required",
                      pattern: {
                        value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                        message: "Enter a valid work email",
                      },
                    })}
                  />
                  {errors.email ? (
                    <span className="mt-1 block text-xs text-red-600">
                      {errors.email.message}
                    </span>
                  ) : null}
                </label>
                <label className="block text-sm font-medium text-ink">
                  {copy.password}
                  <input
                    type="password"
                    className={fieldClass}
                    autoComplete="new-password"
                    {...register("password", {
                      required: "Password is required",
                      minLength: {
                        value: 8,
                        message: copy.passwordHint,
                      },
                    })}
                  />
                  <span className="mt-1 block text-xs text-muted">
                    {copy.passwordHint}
                  </span>
                  {errors.password ? (
                    <span className="mt-1 block text-xs text-red-600">
                      {errors.password.message}
                    </span>
                  ) : null}
                </label>
              </>
            ) : null}

            {errors.root ? (
              <div
                className="rounded-[var(--radius-md)] border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
                role="alert"
              >
                <p className="m-0 font-semibold">{copy.failedTitle}</p>
                <p className="mt-1 m-0">{errors.root.message}</p>
              </div>
            ) : null}

            <div className="mt-2 flex flex-wrap items-center gap-3">
              {step > 0 ? (
                <button
                  type="button"
                  onClick={goBack}
                  className="inline-flex items-center justify-center rounded-[var(--radius-md)] border border-line bg-surface px-5 py-2.5 text-sm font-semibold text-ink transition-colors hover:border-teal/40"
                >
                  {copy.back}
                </button>
              ) : null}
              {step < 3 ? (
                <button
                  type="button"
                  onClick={goNext}
                  className="inline-flex items-center justify-center rounded-[var(--radius-md)] bg-teal px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-bright"
                >
                  {copy.continue}
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={isSubmitting || isSubmitSuccessful}
                  className="inline-flex items-center justify-center rounded-[var(--radius-md)] bg-teal px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-bright disabled:opacity-70"
                >
                  {isSubmitting || isSubmitSuccessful
                    ? copy.submitting
                    : copy.submit}
                </button>
              )}
            </div>
          </form>

          <p className="mt-6 m-0 text-sm text-muted">
            <Link href={opsLoginUrl()} className="font-medium text-teal">
              {copy.signIn}
            </Link>
          </p>
        </section>
      </main>
    </div>
  );
}
