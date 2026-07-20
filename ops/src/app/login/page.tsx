"use client";

import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { login } from "@/lib/api";
import { Button, Field, Input, ErrorState } from "@/components/ui";
import { login as copy } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";

type LoginFormValues = {
  tenant_slug: string;
  email: string;
  password: string;
};

export default function LoginPage() {
  const router = useRouter();
  const {
    register,
    handleSubmit,
    setError,
    clearErrors,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    defaultValues: {
      tenant_slug: "",
      email: "",
      password: "",
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    clearErrors("root");
    try {
      const { user } = await login({
        email: values.email,
        password: values.password,
        tenant_slug: values.tenant_slug,
      });
      if (user.role === "technician") router.replace("/tech");
      else router.replace("/dashboard");
    } catch (err) {
      setError("root", {
        message: safeUserError(err, copy.failedMessage),
      });
    }
  });

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 py-12">
      <div className="ops-login-stage fixed inset-0 -z-10" aria-hidden />
      <form
        onSubmit={onSubmit}
        noValidate
        className="relative z-[1] w-full max-w-md rounded-xl border border-white/15 bg-white/95 p-6 shadow-[var(--shadow-elevated)] backdrop-blur-sm sm:p-8"
      >
        <p className="font-heading text-2xl font-semibold tracking-[-0.03em] text-ink">
          {copy.brand}
        </p>
        <h1 className="mt-3 font-heading text-2xl font-semibold tracking-tight text-ink">
          {copy.heading}
        </h1>
        <p className="mt-1 text-sm text-text-secondary">{copy.supporting}</p>

        <div className="mt-6 grid gap-3">
          <Field
            label={copy.businessId}
            error={errors.tenant_slug?.message}
          >
            <Input
              {...register("tenant_slug", {
                required: "Business ID is required",
                setValueAs: (value: string) => value.trim().toLowerCase(),
              })}
              autoComplete="organization"
              placeholder="your-business"
            />
          </Field>
          <Field label={copy.email} error={errors.email?.message}>
            <Input
              type="email"
              {...register("email", {
                required: "Email is required",
                pattern: {
                  value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                  message: "Enter a valid email",
                },
              })}
              autoComplete="username"
            />
          </Field>
          <Field label={copy.password} error={errors.password?.message}>
            <Input
              type="password"
              {...register("password", {
                required: "Password is required",
              })}
              autoComplete="current-password"
            />
          </Field>
        </div>

        {errors.root?.message ? (
          <ErrorState
            className="mt-4"
            title={copy.failedTitle}
            message={errors.root.message}
          />
        ) : null}

        <Button
          type="submit"
          disabled={isSubmitting}
          className="mt-6 w-full"
          size="lg"
        >
          {isSubmitting ? copy.submitting : copy.submit}
        </Button>
      </form>
    </div>
  );
}
