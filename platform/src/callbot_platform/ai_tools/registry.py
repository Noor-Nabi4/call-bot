"""AI tool registry — schemas, policy matrix, and handler binding."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from callbot_platform.ai_tools.policy import TimeoutClass


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AddressArgs(StrictModel):
    line1: str
    line2: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = Field(default=None, alias="postalCode")
    country: str | None = None


class FindCustomerArgs(StrictModel):
    phone: str | None = None
    email: str | None = None


class CreateCustomerArgs(StrictModel):
    first_name: str = Field(alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    phone: str
    email: str | None = None
    address: AddressArgs | None = None


class GetCustomerContextArgs(StrictModel):
    customer_id: str = Field(alias="customerId")


class SearchServicesArgs(StrictModel):
    query: str
    limit: int | None = Field(default=5, ge=1, le=10)


class GetServicePriceArgs(StrictModel):
    service_id: str = Field(alias="serviceId")
    quantity: float | None = Field(default=None, ge=0)
    effective_at: str | None = Field(default=None, alias="effectiveAt")


class CheckAvailabilityArgs(StrictModel):
    service_id: str = Field(alias="serviceId")
    location_id: str | None = Field(default=None, alias="locationId")
    preferred_date: str | None = Field(default=None, alias="preferredDate")
    preferred_start_date: str | None = Field(default=None, alias="preferredStartDate")
    preferred_end_date: str | None = Field(default=None, alias="preferredEndDate")
    preferred_time_start: str | None = Field(default=None, alias="preferredTimeStart")
    preferred_time_end: str | None = Field(default=None, alias="preferredTimeEnd")
    technician_id: str | None = Field(default=None, alias="technicianId")
    emergency: bool | None = False
    limit: int | None = Field(default=5, ge=1, le=10)


class CreateJobArgs(StrictModel):
    customer_id: str = Field(alias="customerId")
    location_id: str | None = Field(default=None, alias="locationId")
    service_id: str | None = Field(default=None, alias="serviceId")
    description: str
    priority: str | None = None
    notes: str | None = None


class CreateAppointmentArgs(StrictModel):
    customer_id: str = Field(alias="customerId")
    job_id: str = Field(alias="jobId")
    service_id: str | None = Field(default=None, alias="serviceId")
    location_id: str | None = Field(default=None, alias="locationId")
    technician_id: str | None = Field(default=None, alias="technicianId")
    starts_at: str = Field(alias="startsAt")
    ends_at: str = Field(alias="endsAt")
    timezone: str
    notes: str | None = None


class CreateBookingArgs(StrictModel):
    """Authoritative voice booking — job + appointment in one orchestration."""

    customer_id: str = Field(alias="customerId")
    service_id: str = Field(alias="serviceId")
    starts_at: str = Field(alias="startsAt")
    ends_at: str = Field(alias="endsAt")
    timezone: str
    location_id: str | None = Field(default=None, alias="locationId")
    technician_id: str | None = Field(default=None, alias="technicianId")
    description: str | None = None
    priority: str | None = None
    notes: str | None = None
    emergency: bool | None = False


class SendSmsArgs(StrictModel):
    customer_id: str = Field(alias="customerId")
    message: str
    purpose: str


class SearchProductsArgs(StrictModel):
    query: str
    attributes: dict[str, str] | None = None
    category_id: str | None = Field(default=None, alias="categoryId")
    limit: int | None = Field(default=5, ge=1, le=10)


class GetProductArgs(StrictModel):
    product_id: str = Field(alias="productId")
    variant_id: str | None = Field(default=None, alias="variantId")


class CheckInventoryArgs(StrictModel):
    variant_id: str = Field(alias="variantId")
    location_id: str | None = Field(default=None, alias="locationId")


class GetProductPriceArgs(StrictModel):
    variant_id: str = Field(alias="variantId")
    quantity: float | None = Field(default=None, ge=0)
    effective_at: str | None = Field(default=None, alias="effectiveAt")


class FindOrdersArgs(StrictModel):
    customer_id: str | None = Field(default=None, alias="customerId")
    order_number: str | None = Field(default=None, alias="orderNumber")
    status: str | None = None
    limit: int | None = Field(default=5, ge=1, le=10)


class GetOrderStatusArgs(StrictModel):
    order_id: str | None = Field(default=None, alias="orderId")
    order_number: str | None = Field(default=None, alias="orderNumber")


class CreateOrderItemArgs(StrictModel):
    variant_id: str = Field(alias="variantId")
    quantity: int = Field(ge=1)


class CreateOrderArgs(StrictModel):
    customer_id: str = Field(alias="customerId")
    items: list[CreateOrderItemArgs]
    notes: str | None = None


class FindEstimatesArgs(StrictModel):
    customer_id: str | None = Field(default=None, alias="customerId")
    estimate_number: str | None = Field(default=None, alias="estimateNumber")
    status: str | None = None
    limit: int | None = Field(default=5, ge=1, le=10)


class GetEstimateArgs(StrictModel):
    estimate_id: str = Field(alias="estimateId")


class UpdateCustomerArgs(StrictModel):
    customer_id: str = Field(alias="customerId")
    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    email: str | None = None


class RescheduleAppointmentArgs(StrictModel):
    appointment_id: str = Field(alias="appointmentId")
    starts_at: str = Field(alias="startsAt")
    ends_at: str = Field(alias="endsAt")
    timezone: str


class CancelAppointmentArgs(StrictModel):
    appointment_id: str = Field(alias="appointmentId")
    reason: str | None = None


class SearchKnowledgeArgs(StrictModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int | None = Field(default=5, ge=1, le=10, alias="topK")
    source_type: str | None = Field(default=None, alias="sourceType")
    category: str | None = None


class CreatePaymentLinkArgs(StrictModel):
    invoice_id: str = Field(alias="invoiceId")
    amount: str | None = None


class SendPaymentLinkSmsArgs(StrictModel):
    payment_id: str = Field(alias="paymentId")


class SendPaymentLinkEmailArgs(StrictModel):
    payment_id: str = Field(alias="paymentId")


class GetPaymentStatusArgs(StrictModel):
    payment_id: str | None = Field(default=None, alias="paymentId")
    invoice_id: str | None = Field(default=None, alias="invoiceId")


class ListMembershipPlansArgs(StrictModel):
    status: str | None = None


class GetCustomerMembershipArgs(StrictModel):
    customer_id: str = Field(alias="customerId")


class SubscribeMembershipArgs(StrictModel):
    customer_id: str = Field(alias="customerId")
    plan_id: str = Field(alias="planId")
    billing_interval: str = Field(alias="billingInterval")


class CancelMembershipArgs(StrictModel):
    membership_id: str = Field(alias="membershipId")
    immediate: bool | None = False


class ChangeMembershipPlanArgs(StrictModel):
    membership_id: str = Field(alias="membershipId")
    target_plan_id: str = Field(alias="targetPlanId")
    billing_interval: str | None = Field(default=None, alias="billingInterval")


class RequestHumanArgs(StrictModel):
    reason: str
    summary: str


ToolHandler = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    args_model: type[BaseModel]
    tool_group: str
    permissions: tuple[str, ...]
    mutation: bool
    confirmation_required: bool
    idempotency_required: bool
    timeout_class: TimeoutClass = TimeoutClass.STANDARD_READ
    description: str = ""
    # Optional extra domain permissions checked only for included result slices.
    context_permissions: dict[str, str] = field(default_factory=dict)


TOOL_SPECS: dict[str, ToolSpec] = {
    "find_customer": ToolSpec(
        name="find_customer",
        args_model=FindCustomerArgs,
        tool_group="crm",
        permissions=("customers.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.FAST_READ,
    ),
    "create_customer": ToolSpec(
        name="create_customer",
        args_model=CreateCustomerArgs,
        tool_group="crm",
        permissions=("customers.create",),
        mutation=True,
        confirmation_required=True,
        idempotency_required=True,
        timeout_class=TimeoutClass.MUTATION,
    ),
    "get_customer_context": ToolSpec(
        name="get_customer_context",
        args_model=GetCustomerContextArgs,
        tool_group="crm",
        permissions=("customers.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.STANDARD_READ,
        context_permissions={
            "activeJobs": "jobs.read",
            "upcomingAppointments": "appointments.read",
            "recentOrders": "orders.read",
            "openEstimates": "estimates.read",
        },
    ),
    "search_services": ToolSpec(
        name="search_services",
        args_model=SearchServicesArgs,
        tool_group="crm",
        permissions=("services.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.STANDARD_READ,
    ),
    "get_service_price": ToolSpec(
        name="get_service_price",
        args_model=GetServicePriceArgs,
        tool_group="crm",
        permissions=("services.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.FAST_READ,
    ),
    "check_availability": ToolSpec(
        name="check_availability",
        args_model=CheckAvailabilityArgs,
        tool_group="scheduling",
        permissions=("appointments.availability.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.AVAILABILITY,
    ),
    "create_job": ToolSpec(
        name="create_job",
        args_model=CreateJobArgs,
        tool_group="crm",
        permissions=("jobs.create",),
        mutation=True,
        confirmation_required=True,
        idempotency_required=True,
        timeout_class=TimeoutClass.MUTATION,
    ),
    "create_appointment": ToolSpec(
        name="create_appointment",
        args_model=CreateAppointmentArgs,
        tool_group="scheduling",
        permissions=("appointments.create",),
        mutation=True,
        confirmation_required=True,
        idempotency_required=True,
        timeout_class=TimeoutClass.MUTATION,
    ),
    "create_booking": ToolSpec(
        name="create_booking",
        args_model=CreateBookingArgs,
        tool_group="scheduling",
        permissions=("jobs.create", "appointments.create"),
        mutation=True,
        confirmation_required=True,
        idempotency_required=True,
        timeout_class=TimeoutClass.MUTATION,
    ),
    "send_sms": ToolSpec(
        name="send_sms",
        args_model=SendSmsArgs,
        tool_group="sms",
        permissions=("ai.tools_sms",),
        mutation=True,
        confirmation_required=True,  # policy: confirm by default
        idempotency_required=True,
        timeout_class=TimeoutClass.EXTERNAL_PROVIDER,
    ),
    "search_products": ToolSpec(
        name="search_products",
        args_model=SearchProductsArgs,
        tool_group="crm",
        permissions=("products.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.STANDARD_READ,
    ),
    "get_product": ToolSpec(
        name="get_product",
        args_model=GetProductArgs,
        tool_group="crm",
        permissions=("products.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.FAST_READ,
    ),
    "check_inventory": ToolSpec(
        name="check_inventory",
        args_model=CheckInventoryArgs,
        tool_group="crm",
        permissions=("inventory.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.FAST_READ,
    ),
    "get_product_price": ToolSpec(
        name="get_product_price",
        args_model=GetProductPriceArgs,
        tool_group="crm",
        permissions=("products.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.FAST_READ,
    ),
    "find_orders": ToolSpec(
        name="find_orders",
        args_model=FindOrdersArgs,
        tool_group="crm",
        permissions=("orders.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.STANDARD_READ,
    ),
    "get_order_status": ToolSpec(
        name="get_order_status",
        args_model=GetOrderStatusArgs,
        tool_group="crm",
        permissions=("orders.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.FAST_READ,
    ),
    "create_order": ToolSpec(
        name="create_order",
        args_model=CreateOrderArgs,
        tool_group="crm",
        permissions=("orders.create",),
        mutation=True,
        confirmation_required=True,
        idempotency_required=True,
        timeout_class=TimeoutClass.MUTATION,
    ),
    "find_estimates": ToolSpec(
        name="find_estimates",
        args_model=FindEstimatesArgs,
        tool_group="crm",
        permissions=("estimates.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.STANDARD_READ,
    ),
    "get_estimate": ToolSpec(
        name="get_estimate",
        args_model=GetEstimateArgs,
        tool_group="crm",
        permissions=("estimates.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.STANDARD_READ,
    ),
    "update_customer": ToolSpec(
        name="update_customer",
        args_model=UpdateCustomerArgs,
        tool_group="crm",
        permissions=("customers.update",),
        mutation=True,
        confirmation_required=True,
        idempotency_required=True,
        timeout_class=TimeoutClass.MUTATION,
        description="Update controlled customer fields after confirmation.",
    ),
    "reschedule_appointment": ToolSpec(
        name="reschedule_appointment",
        args_model=RescheduleAppointmentArgs,
        tool_group="scheduling",
        permissions=("appointments.update",),
        mutation=True,
        confirmation_required=True,
        idempotency_required=True,
        timeout_class=TimeoutClass.MUTATION,
        description="Reschedule via AppointmentService with conflict revalidation.",
    ),
    "cancel_appointment": ToolSpec(
        name="cancel_appointment",
        args_model=CancelAppointmentArgs,
        tool_group="scheduling",
        permissions=("appointments.cancel",),
        mutation=True,
        confirmation_required=True,
        idempotency_required=True,
        timeout_class=TimeoutClass.MUTATION,
        description="Cancel appointment via AppointmentService lifecycle.",
    ),
    "request_human": ToolSpec(
        name="request_human",
        args_model=RequestHumanArgs,
        tool_group="handoff",
        permissions=("ai.tools_handoff",),
        mutation=True,
        confirmation_required=False,
        idempotency_required=True,
        timeout_class=TimeoutClass.EXTERNAL_PROVIDER,
    ),
    "search_knowledge": ToolSpec(
        name="search_knowledge",
        args_model=SearchKnowledgeArgs,
        tool_group="knowledge",
        permissions=("ai.tools_knowledge",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.STANDARD_READ,
        description=(
            "Search tenant knowledge (FAQs, policies, business info, product descriptions). "
            "Informational only — never use for inventory, prices, appointments, or orders."
        ),
    ),
    "create_payment_link": ToolSpec(
        name="create_payment_link",
        args_model=CreatePaymentLinkArgs,
        tool_group="payments",
        permissions=("payments.create",),
        mutation=True,
        confirmation_required=True,
        idempotency_required=True,
        timeout_class=TimeoutClass.EXTERNAL_PROVIDER,
        description=(
            "Create a secure Stripe Checkout payment link for an invoice. "
            "Never collect card data; send the customer to Stripe-hosted checkout."
        ),
    ),
    "send_payment_link_sms": ToolSpec(
        name="send_payment_link_sms",
        args_model=SendPaymentLinkSmsArgs,
        tool_group="payments",
        permissions=("payments.create",),
        mutation=True,
        confirmation_required=True,
        idempotency_required=True,
        timeout_class=TimeoutClass.EXTERNAL_PROVIDER,
        description="SMS the Stripe checkout URL to the invoice customer's phone on file.",
    ),
    "send_payment_link_email": ToolSpec(
        name="send_payment_link_email",
        args_model=SendPaymentLinkEmailArgs,
        tool_group="payments",
        permissions=("payments.create",),
        mutation=True,
        confirmation_required=True,
        idempotency_required=True,
        timeout_class=TimeoutClass.EXTERNAL_PROVIDER,
        description="Email the Stripe checkout URL to the invoice customer's email on file.",
    ),
    "get_payment_status": ToolSpec(
        name="get_payment_status",
        args_model=GetPaymentStatusArgs,
        tool_group="payments",
        permissions=("payments.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.FAST_READ,
        description="Read payment status/amount for an invoice or payment id (no card data).",
    ),
    "list_membership_plans": ToolSpec(
        name="list_membership_plans",
        args_model=ListMembershipPlansArgs,
        tool_group="memberships",
        permissions=("memberships.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.FAST_READ,
        description="List membership plans (prices, included services, discounts).",
    ),
    "get_customer_membership": ToolSpec(
        name="get_customer_membership",
        args_model=GetCustomerMembershipArgs,
        tool_group="memberships",
        permissions=("memberships.read",),
        mutation=False,
        confirmation_required=False,
        idempotency_required=False,
        timeout_class=TimeoutClass.FAST_READ,
        description="Get a customer's current open membership and benefits (not from RAG).",
    ),
    "subscribe_membership": ToolSpec(
        name="subscribe_membership",
        args_model=SubscribeMembershipArgs,
        tool_group="memberships",
        permissions=("memberships.create",),
        mutation=True,
        confirmation_required=True,
        idempotency_required=True,
        timeout_class=TimeoutClass.EXTERNAL_PROVIDER,
        description=(
            "Subscribe a customer to an ACTIVE plan. Creates invoice + optional "
            "Stripe Checkout link. Never collect card data."
        ),
    ),
    "cancel_membership": ToolSpec(
        name="cancel_membership",
        args_model=CancelMembershipArgs,
        tool_group="memberships",
        permissions=("memberships.update",),
        mutation=True,
        confirmation_required=True,
        idempotency_required=True,
        timeout_class=TimeoutClass.MUTATION,
        description=(
            "Cancel membership (default: at period end). Confirm with the customer "
            "before executing."
        ),
    ),
    "upgrade_membership": ToolSpec(
        name="upgrade_membership",
        args_model=ChangeMembershipPlanArgs,
        tool_group="memberships",
        permissions=("memberships.update",),
        mutation=True,
        confirmation_required=True,
        idempotency_required=True,
        timeout_class=TimeoutClass.MUTATION,
        description="Schedule upgrade at next billing period (no proration).",
    ),
    "downgrade_membership": ToolSpec(
        name="downgrade_membership",
        args_model=ChangeMembershipPlanArgs,
        tool_group="memberships",
        permissions=("memberships.update",),
        mutation=True,
        confirmation_required=True,
        idempotency_required=True,
        timeout_class=TimeoutClass.MUTATION,
        description="Schedule downgrade at next billing period (no proration).",
    ),
}


def get_tool_spec(name: str) -> ToolSpec | None:
    return TOOL_SPECS.get(name)


def list_tool_names() -> list[str]:
    return sorted(TOOL_SPECS.keys())
