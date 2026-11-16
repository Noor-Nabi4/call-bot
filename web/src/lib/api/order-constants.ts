/** Order lifecycle constants shared by UI and tests (no HTTP client). */

export type OrderStatus =
  | "DRAFT"
  | "PENDING"
  | "CONFIRMED"
  | "PROCESSING"
  | "SHIPPED"
  | "DELIVERED"
  | "CANCELLED"
  | "REFUNDED";

export const ORDER_STATUSES: OrderStatus[] = [
  "DRAFT",
  "PENDING",
  "CONFIRMED",
  "PROCESSING",
  "SHIPPED",
  "DELIVERED",
  "CANCELLED",
  "REFUNDED",
];

/** Forward transitions (excluding cancel/refund specials). */
export const ORDER_FORWARD_TRANSITIONS: Record<string, OrderStatus[]> = {
  DRAFT: ["PENDING"],
  PENDING: ["CONFIRMED"],
  CONFIRMED: ["PROCESSING"],
  PROCESSING: ["SHIPPED"],
  SHIPPED: ["DELIVERED"],
  DELIVERED: [],
  CANCELLED: [],
  REFUNDED: [],
};

export const ORDER_CANCELLABLE = new Set([
  "DRAFT",
  "PENDING",
  "CONFIRMED",
  "PROCESSING",
  "SHIPPED",
]);
