/** Structured API failure — preserves HTTP status and domain `code` when present. */

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function isBookingConflict(err: unknown): boolean {
  if (!(err instanceof ApiError)) return false;
  if (err.status === 409) return true;
  return (
    err.code === "slot_conflict" ||
    err.code === "appointment_conflict" ||
    err.code === "idempotency_conflict"
  );
}
