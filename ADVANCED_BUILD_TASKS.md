# AI Business OS — Advanced Build Tasks

## Product Vision

Build a multi-tenant, AI-first Business Operating System that can adapt itself to different businesses.

The platform should support:

- CRM
- Products
- Services
- Inventory
- Orders
- Leads
- Jobs
- Appointments
- Dispatch
- Technicians
- Estimates
- Invoices
- Payments
- Memberships
- Equipment
- AI Voice Agent
- AI SMS Agent
- AI Knowledge Base
- Automations
- Analytics
- Integrations

The system must NOT assume every business is the same.

A business should configure its CRM and AI behavior during onboarding.

---

# GLOBAL DEVELOPMENT RULES

Before starting any task:

- [ ] Inspect the existing repository
- [ ] Understand the current architecture
- [ ] Reuse existing patterns
- [ ] Do not duplicate existing functionality
- [ ] Do not introduce unnecessary dependencies
- [ ] Do not use mock data for production functionality
- [ ] Preserve existing functionality

For every completed task:

- [ ] Database changes implemented
- [ ] Migration created if required
- [ ] Backend implemented
- [ ] API implemented
- [ ] Authorization implemented
- [ ] Frontend implemented if required
- [ ] Validation implemented
- [ ] Loading state implemented
- [ ] Empty state implemented
- [ ] Error state implemented
- [ ] Tests added
- [ ] Existing tests pass
- [ ] Lint passes
- [ ] Build passes
- [ ] No TypeScript errors
- [ ] No regression
- [ ] Documentation updated
- [ ] Mark task complete only after verification

---

# PHASE 0 — ARCHITECTURE AUDIT

## TASK 0.1 — Repository Audit

### Description

Understand the current application before modifying anything.

### Checklist

- [x] Identify frontend
- [x] Identify backend
- [x] Identify database
- [x] Identify authentication
- [x] Identify existing tenant/business model
- [x] Identify existing users
- [x] Identify existing calls
- [x] Identify existing voice agent
- [x] Identify Twilio implementation
- [x] Identify LiveKit implementation
- [x] Identify OpenAI implementation
- [x] Identify Stripe implementation
- [x] Identify SMS implementation
- [x] Identify email implementation
- [x] Identify existing CRM
- [x] Identify existing calendar
- [x] Identify existing background jobs
- [x] Identify queues/events
- [x] Identify existing integrations

### Deliverable

Created:

[`docs/ARCHITECTURE_AUDIT.md`](./docs/ARCHITECTURE_AUDIT.md)

---

# PHASE 1 — MULTI-TENANT FOUNDATION

## TASK 1.1 — Organization Model

### Description

Create the main business/tenant entity.

### Fields

- `id`
- `name`
- `slug`
- `industry`
- `business_type`
- `timezone`
- `currency`
- `country`
- `state`
- `website`
- `phone`
- `email`
- `status`
- `created_at`
- `updated_at`

### Checklist

- [x] Database table
- [x] Migration
- [x] Entity/model
- [x] Repository
- [x] Service
- [x] API
- [x] Validation
- [x] Tests

---

## TASK 1.2 — Organization Membership

### Description

Connect users with businesses.

### Checklist

- [ ] Membership table
- [ ] User relationship
- [ ] Organization relationship
- [ ] Role
- [ ] Status
- [ ] Unique constraint
- [ ] API
- [ ] Authorization tests

---

## TASK 1.3 — RBAC

### Description

Implement organization-level roles.

### Roles

- Owner
- Admin
- Manager
- Dispatcher
- Technician
- CSR
- Accountant

### Checklist

- [ ] Define permissions
- [ ] Permission middleware
- [ ] Role middleware
- [ ] API protection
- [ ] UI permission checks
- [ ] Permission tests

---

## TASK 1.4 — Tenant Isolation

### Description

Every business must only access its own data.

### Checklist

- [ ] Organization filtering
- [ ] Customer isolation
- [ ] Product isolation
- [ ] Job isolation
- [ ] Call isolation
- [ ] Invoice isolation
- [ ] Payment isolation
- [ ] File isolation
- [ ] Audit isolation
- [ ] Cross-tenant security tests

---

# PHASE 2 — BUSINESS ONBOARDING

## TASK 2.1 — Onboarding State

### Description

Create a persistent onboarding process.

### Checklist

- [ ] Onboarding status
- [ ] Current step
- [ ] Completed steps
- [ ] Progress
- [ ] Resume onboarding
- [ ] Skip optional steps
- [ ] Save partial progress

---

## TASK 2.2 — Business Information Wizard

### Description

Collect business information during signup.

### Steps

1. Business
2. Industry
3. Business model
4. Products/services
5. Customers
6. Scheduling
7. AI agent
8. Review

### Checklist

- [ ] Business name
- [ ] Industry
- [ ] Country
- [ ] State
- [ ] Timezone
- [ ] Currency
- [ ] Website
- [ ] Phone
- [ ] Email
- [ ] Business size
- [ ] Business type

---

## TASK 2.3 — Business Model Selection

### Description

Determine what the business sells.

### Options

- Products
- Services
- Products + Services
- Subscriptions
- Appointments
- Rentals
- Custom

### Checklist

- [ ] Selection UI
- [ ] Store configuration
- [ ] Validation
- [ ] API
- [ ] Tests

---

## TASK 2.4 — Industry Templates

### Description

Create configuration templates for different industries.

### Initial templates

- HVAC
- Plumbing
- Electrical
- Cleaning
- Automotive
- Dental
- Medical
- Real Estate
- E-commerce
- Consulting
- Beauty/Salon
- Fitness
- Custom

### Checklist

- [ ] Template model
- [ ] Template configuration
- [ ] HVAC template
- [ ] Plumbing template
- [ ] Electrical template
- [ ] Cleaning template
- [ ] E-commerce template
- [ ] Generic template
- [ ] Template tests

---

## TASK 2.5 — Automatic CRM Setup

### Description

When onboarding finishes, automatically create the CRM configuration based on business type and industry.

Example:

HVAC:

```text
Customers
Properties
Equipment
Services
Jobs
Appointments
Technicians
Estimates
Invoices
Payments
Memberships
```

E-commerce:

```text
Customers
Products
Categories
Inventory
Orders
Payments
Shipping
Returns
Discounts
```

### Checklist

- [ ] Read onboarding configuration
- [ ] Select template
- [ ] Enable modules
- [ ] Create default settings
- [ ] Create default statuses
- [ ] Create default fields
- [ ] Create default workflows
- [ ] Persist configuration
- [ ] Make process idempotent
- [ ] Add tests

---

# PHASE 3 — DYNAMIC CRM ENGINE

## TASK 3.1 — CRM Modules

### Description

CRM modules must be configurable instead of hardcoded per business.

### Modules

- Customers
- Companies
- Leads
- Deals
- Products
- Services
- Orders
- Jobs
- Appointments
- Estimates
- Invoices
- Payments
- Equipment
- Memberships
- Calls
- Conversations
- Tasks

### Checklist

- [ ] Module registry
- [ ] Enable/disable modules
- [ ] Organization-specific configuration
- [ ] Module ordering
- [ ] Navigation generated dynamically
- [ ] Permission mapping

---

## TASK 3.2 — Custom Fields

### Description

Allow businesses to add custom fields without database migrations for every field.

### Field types

- Text
- Number
- Currency
- Boolean
- Date
- DateTime
- Email
- Phone
- URL
- Dropdown
- Multi-select
- Address
- File
- Relationship

### Checklist

- [ ] Custom field model
- [ ] Field definitions
- [ ] Validation
- [ ] Field rendering
- [ ] API support
- [ ] Search support
- [ ] Filtering support
- [ ] Required fields
- [ ] Default values
- [ ] Permission support

---

## TASK 3.3 — Custom Objects

### Description

Allow businesses to create business-specific entities.

Examples:

- Equipment
- Vehicle
- Property
- Contract
- Asset
- Membership
- Subscription

### Checklist

- [ ] Object definition
- [ ] Object fields
- [ ] Relationships
- [ ] CRUD API
- [ ] Dynamic UI
- [ ] Permissions
- [ ] Search
- [ ] Audit history

---

## TASK 3.4 — Relationships

### Description

Support relationships between CRM entities.

Examples:

```text
Customer
 ├── Locations
 ├── Jobs
 ├── Orders
 ├── Appointments
 ├── Equipment
 ├── Invoices
 └── Calls
```

### Checklist

- [ ] Relationship model
- [ ] One-to-one
- [ ] One-to-many
- [ ] Many-to-many
- [ ] Relationship API
- [ ] Relationship UI
- [ ] Query support

---

# PHASE 4 — CUSTOMER CRM

## TASK 4.1 — Customer

### Checklist

- [ ] Customer model
- [ ] Name
- [ ] Phone
- [ ] Email
- [ ] Status
- [ ] Notes
- [ ] Tags
- [ ] Organization
- [ ] CRUD APIs
- [ ] Tests

---

## TASK 4.2 — Customer Locations

### Checklist

- [ ] Address
- [ ] City
- [ ] State
- [ ] ZIP
- [ ] Country
- [ ] Latitude
- [ ] Longitude
- [ ] Access instructions
- [ ] Primary location
- [ ] Multiple locations

---

## TASK 4.3 — Customer Search

### Description

Allow AI and staff to quickly find customers.

### Checklist

- [ ] Phone search
- [ ] Email search
- [ ] Name search
- [ ] Address search
- [ ] Fuzzy search
- [ ] Normalized phone
- [ ] Database indexes
- [ ] Pagination

---

## TASK 4.4 — Customer Timeline

### Checklist

- [ ] Calls
- [ ] SMS
- [ ] Emails
- [ ] Leads
- [ ] Jobs
- [ ] Orders
- [ ] Appointments
- [ ] Estimates
- [ ] Invoices
- [ ] Payments
- [ ] Notes
- [ ] Activity history

---

# PHASE 5 — PRODUCT CATALOG

## TASK 5.1 — Product Model

### Description

Allow businesses to create and manage products.

### Fields

- Name
- SKU
- Description
- Category
- Brand
- Price
- Cost
- Tax
- Weight
- Status
- Images

### Checklist

- [ ] Product table
- [ ] CRUD
- [ ] API
- [ ] Validation
- [ ] Search
- [ ] Filtering
- [ ] Pagination
- [ ] Tests

---

## TASK 5.2 — Product Categories

### Checklist

- [ ] Category model
- [ ] Parent category
- [ ] Nested categories
- [ ] Category CRUD
- [ ] Product filtering

---

## TASK 5.3 — Product Variants

### Description

Support products with variants.

Example:

```text
T-Shirt

Color:
Black
Blue
Red

Size:
S
M
L
XL
```

### Checklist

- [ ] Variant model
- [ ] SKU per variant
- [ ] Price per variant
- [ ] Inventory per variant
- [ ] Attributes
- [ ] Variant API
- [ ] Tests

---

## TASK 5.4 — Product Images

### Checklist

- [ ] Upload
- [ ] Storage
- [ ] Multiple images
- [ ] Primary image
- [ ] Delete image
- [ ] Secure access

---

# PHASE 6 — INVENTORY

## TASK 6.1 — Inventory Model

### Checklist

- [ ] Stock quantity
- [ ] Reserved quantity
- [ ] Available quantity
- [ ] Minimum stock
- [ ] Location
- [ ] SKU
- [ ] Inventory status

---

## TASK 6.2 — Inventory Transactions

### Description

Never directly modify stock without creating an inventory transaction.

### Transaction types

- Purchase
- Sale
- Adjustment
- Return
- Reservation
- Release

### Checklist

- [ ] Transaction model
- [ ] Atomic stock update
- [ ] Transaction history
- [ ] Audit log
- [ ] Concurrency protection
- [ ] Tests

---

## TASK 6.3 — Low Stock Alerts

### Checklist

- [ ] Threshold configuration
- [ ] Alert event
- [ ] Dashboard warning
- [ ] Email
- [ ] SMS optional

---

# PHASE 7 — SERVICES & PRICEBOOK

## TASK 7.1 — Services

### Checklist

- [ ] Service model
- [ ] Category
- [ ] Description
- [ ] Duration
- [ ] Base price
- [ ] Status
- [ ] CRUD
- [ ] Search

---

## TASK 7.2 — Pricebook

### Checklist

- [ ] Pricebook
- [ ] Pricebook items
- [ ] Labor
- [ ] Materials
- [ ] Fixed pricing
- [ ] Starting price
- [ ] Organization pricing
- [ ] Price overrides
- [ ] Effective dates

---

# PHASE 8 — LEADS

## TASK 8.1 — Lead Management

### Checklist

- [ ] Lead model
- [ ] Customer relation
- [ ] Source
- [ ] Service/product
- [ ] Priority
- [ ] Status
- [ ] Owner
- [ ] Notes
- [ ] CRUD APIs

---

## TASK 8.2 — Lead Pipeline

```text
NEW
→ QUALIFIED
→ CONTACTED
→ BOOKED
→ WON
→ LOST
```

### Checklist

- [ ] Status transitions
- [ ] Pipeline UI
- [ ] Activity tracking
- [ ] Conversion tracking

---

# PHASE 9 — ORDERS

## TASK 9.1 — Order Model

### Description

Support commerce businesses and product sales.

### Checklist

- [ ] Order
- [ ] Customer
- [ ] Line items
- [ ] Product
- [ ] Variant
- [ ] Quantity
- [ ] Price
- [ ] Discount
- [ ] Tax
- [ ] Shipping
- [ ] Total
- [ ] Status

---

## TASK 9.2 — Order Lifecycle

```text
DRAFT
→ PENDING
→ CONFIRMED
→ PROCESSING
→ SHIPPED
→ DELIVERED
→ CANCELLED
→ REFUNDED
```

### Checklist

- [ ] State machine
- [ ] Status history
- [ ] Validation
- [ ] Tests

---

# PHASE 10 — JOB MANAGEMENT

## TASK 10.1 — Jobs

### Checklist

- [ ] Job model
- [ ] Customer
- [ ] Location
- [ ] Service
- [ ] Description
- [ ] Priority
- [ ] Status
- [ ] Technician
- [ ] Notes
- [ ] Attachments

---

## TASK 10.2 — Job Status

```text
NEW
SCHEDULED
CONFIRMED
DISPATCHED
EN_ROUTE
ARRIVED
IN_PROGRESS
COMPLETED
CANCELLED
NO_SHOW
```

### Checklist

- [ ] State machine
- [ ] Status history
- [ ] Validation
- [ ] Audit events
- [ ] Tests

---

# PHASE 11 — APPOINTMENTS & SCHEDULING

## TASK 11.1 — Business Hours

### Checklist

- [ ] Working days
- [ ] Opening time
- [ ] Closing time
- [ ] Holidays
- [ ] Timezone
- [ ] Emergency hours

---

## TASK 11.2 — Technician Availability

### Checklist

- [ ] Working schedule
- [ ] Breaks
- [ ] Vacation
- [ ] Days off
- [ ] Skills
- [ ] Service areas

---

## TASK 11.3 — Appointment

### Checklist

- [ ] Appointment model
- [ ] Start time
- [ ] End time
- [ ] Duration
- [ ] Customer
- [ ] Job
- [ ] Technician
- [ ] Status
- [ ] Timezone

---

## TASK 11.4 — Availability Engine

### Description

Calculate real availability instead of relying on static calendar slots.

### Checklist

- [ ] Business hours
- [ ] Technician schedule
- [ ] Existing appointments
- [ ] Appointment duration
- [ ] Skills
- [ ] Service area
- [ ] Emergency priority
- [ ] Timezone
- [ ] Double-booking prevention
- [ ] Race-condition protection

---

# PHASE 12 — DISPATCH

## TASK 12.1 — Technician Management

### Checklist

- [ ] Technician profile
- [ ] Skills
- [ ] Service categories
- [ ] Service areas
- [ ] Schedule
- [ ] Status

---

## TASK 12.2 — Dispatch Board

### Checklist

- [ ] Today's jobs
- [ ] Technician columns
- [ ] Unassigned jobs
- [ ] Assign job
- [ ] Reassign job
- [ ] Drag/drop
- [ ] Job priority
- [ ] Status
- [ ] ETA

---

## TASK 12.3 — Technician Status

```text
AVAILABLE
BUSY
EN_ROUTE
ARRIVED
ON_BREAK
OFFLINE
```

### Checklist

- [ ] Status API
- [ ] Status history
- [ ] Real-time updates
- [ ] Authorization

---

# PHASE 13 — AI TOOL LAYER

## TASK 13.1 — AI Tool Registry

### Description

Create a centralized tool system that allows AI agents to execute business operations safely.

### Checklist

- [ ] Tool registry
- [ ] Tool schemas
- [ ] Authentication
- [ ] Organization context
- [ ] Authorization
- [ ] Validation
- [ ] Tool logging
- [ ] Error handling
- [ ] Tool timeout
- [ ] Tool retry policy

---

## TASK 13.2 — Customer Tools

Create:

- [ ] `find_customer`
- [ ] `create_customer`
- [ ] `update_customer`
- [ ] `get_customer_history`

---

## TASK 13.3 — Commerce Tools

Create:

- [ ] `search_products`
- [ ] `get_product`
- [ ] `check_inventory`
- [ ] `get_product_price`
- [ ] `create_order`
- [ ] `get_order`
- [ ] `get_order_status`

---

## TASK 13.4 — Service Tools

Create:

- [ ] `get_services`
- [ ] `get_service_price`
- [ ] `get_pricebook_item`

---

## TASK 13.5 — Scheduling Tools

Create:

- [ ] `check_availability`
- [ ] `get_available_slots`
- [ ] `create_appointment`
- [ ] `reschedule_appointment`
- [ ] `cancel_appointment`

---

## TASK 13.6 — Job Tools

Create:

- [ ] `create_job`
- [ ] `get_job`
- [ ] `update_job`
- [ ] `get_job_status`

---

## TASK 13.7 — Billing Tools

Create:

- [ ] `create_estimate`
- [ ] `send_estimate`
- [ ] `create_invoice`
- [ ] `create_payment_link`
- [ ] `get_payment_status`

---

## TASK 13.8 — Communication Tools

Create:

- [ ] `send_sms`
- [ ] `send_email`
- [ ] `transfer_call`
- [ ] `create_callback`

---

# PHASE 14 — AI VOICE AGENT

## TASK 14.1 — Caller Identification

### Checklist

- [ ] Read caller number
- [ ] Normalize number
- [ ] Search customer
- [ ] Identify existing customer
- [ ] Create new customer
- [ ] Load customer context

---

## TASK 14.2 — AI System Prompt

### Description

Create a structured system prompt for the AI receptionist.

AI must understand:

- Business identity
- Business hours
- Services
- Products
- Pricing
- Policies
- Customer context
- Available tools
- Escalation rules

### Checklist

- [ ] Business context
- [ ] Customer context
- [ ] Tool rules
- [ ] Safety rules
- [ ] Confirmation rules
- [ ] Escalation rules
- [ ] No hallucinated data
- [ ] Prompt tests

---

## TASK 14.3 — AI Booking

### Flow

```text
CALL
→ IDENTIFY CUSTOMER
→ UNDERSTAND REQUEST
→ FIND SERVICE
→ CHECK AVAILABILITY
→ OFFER SLOTS
→ CONFIRM
→ CREATE JOB
→ CREATE APPOINTMENT
→ SEND SMS
```

### Checklist

- [ ] New customer flow
- [ ] Existing customer flow
- [ ] Availability
- [ ] Slot selection
- [ ] Booking confirmation
- [ ] Job creation
- [ ] SMS
- [ ] Error handling

---

## TASK 14.4 — AI Commerce

### Example

Customer:

> "Do you have a blue iPhone 15 Pro case?"

AI:

```text
search_products()
→ get product
→ check_inventory()
→ get_product_price()
→ answer customer
```

### Checklist

- [ ] Product search
- [ ] Variant search
- [ ] Inventory lookup
- [ ] Price lookup
- [ ] Product questions
- [ ] Order lookup
- [ ] Order status
- [ ] Create order if enabled

---

# PHASE 15 — AI SMS AGENT

## TASK 15.1 — Incoming SMS

### Checklist

- [ ] Receive webhook
- [ ] Identify customer
- [ ] Load conversation
- [ ] Detect intent
- [ ] Generate response
- [ ] Execute tools
- [ ] Store message
- [ ] Store AI action

---

## TASK 15.2 — SMS Booking

### Checklist

- [ ] Check availability
- [ ] Offer slots
- [ ] Confirm
- [ ] Book
- [ ] Send confirmation

---

# PHASE 16 — KNOWLEDGE BASE / RAG

## TASK 16.1 — Knowledge Sources

Allow:

- [ ] PDF
- [ ] DOCX
- [ ] Website
- [ ] Text
- [ ] FAQs
- [ ] Policies
- [ ] Business information
- [ ] Product descriptions

---

## TASK 16.2 — Ingestion

### Checklist

- [ ] Upload
- [ ] Extract text
- [ ] Chunk
- [ ] Generate embeddings
- [ ] Store vectors
- [ ] Store metadata
- [ ] Organization isolation
- [ ] Re-index
- [ ] Delete knowledge

---

## TASK 16.3 — Retrieval

### Checklist

- [ ] Semantic search
- [ ] Organization filtering
- [ ] Metadata filtering
- [ ] Context limit
- [ ] Relevance threshold
- [ ] Retrieval logging

---

## TASK 16.4 — RAG vs Tools

Use RAG for:

- [ ] FAQs
- [ ] Policies
- [ ] General business information
- [ ] Product descriptions

Use database tools for:

- [ ] Customer information
- [ ] Inventory
- [ ] Pricing
- [ ] Availability
- [ ] Jobs
- [ ] Appointments
- [ ] Orders
- [ ] Payments

---

# PHASE 17 — ESTIMATES

## TASK 17.1 — Estimate

### Checklist

- [ ] Estimate model
- [ ] Customer
- [ ] Job
- [ ] Line items
- [ ] Quantity
- [ ] Unit price
- [ ] Discount
- [ ] Tax
- [ ] Total

---

## TASK 17.2 — Estimate Workflow

```text
DRAFT
→ SENT
→ VIEWED
→ APPROVED
→ DECLINED
→ EXPIRED
```

### Checklist

- [ ] State machine
- [ ] Email
- [ ] SMS
- [ ] Customer approval
- [ ] Convert to job

---

# PHASE 18 — INVOICING

## TASK 18.1 — Invoice

### Checklist

- [ ] Invoice model
- [ ] Invoice number
- [ ] Customer
- [ ] Job/order
- [ ] Line items
- [ ] Tax
- [ ] Discount
- [ ] Total
- [ ] Balance
- [ ] Due date
- [ ] Status

---

## TASK 18.2 — Invoice Workflow

```text
DRAFT
→ SENT
→ PARTIALLY_PAID
→ PAID
→ OVERDUE
→ VOID
```

---

# PHASE 19 — PAYMENTS

## TASK 19.1 — Stripe Integration

### Checklist

- [ ] Payment link
- [ ] Checkout
- [ ] Webhook
- [ ] Payment status
- [ ] Partial payment
- [ ] Refund
- [ ] Idempotency
- [ ] Audit logging

---

## TASK 19.2 — AI Payment

### Checklist

- [ ] Generate payment link
- [ ] Send SMS
- [ ] Send email
- [ ] Check payment status
- [ ] Never expose card data

---

# PHASE 20 — MEMBERSHIPS

## TASK 20.1 — Membership Plans

### Checklist

- [ ] Plan
- [ ] Monthly price
- [ ] Annual price
- [ ] Included services
- [ ] Discounts
- [ ] Priority scheduling
- [ ] Status

---

## TASK 20.2 — Customer Membership

### Checklist

- [ ] Subscribe
- [ ] Cancel
- [ ] Renew
- [ ] Upgrade
- [ ] Downgrade
- [ ] Membership history

---

# PHASE 21 — EQUIPMENT / ASSETS

## TASK 21.1 — Equipment

### Checklist

- [ ] Equipment model
- [ ] Manufacturer
- [ ] Model
- [ ] Serial number
- [ ] Installation date
- [ ] Warranty
- [ ] Customer relationship
- [ ] Location

---

## TASK 21.2 — Equipment History

### Checklist

- [ ] Service history
- [ ] Repairs
- [ ] Parts
- [ ] Technician notes
- [ ] Photos
- [ ] Warranty status

---

# PHASE 22 — AUTOMATION ENGINE

## TASK 22.1 — Event System

Events:

- [ ] CALL_COMPLETED
- [ ] LEAD_CREATED
- [ ] JOB_CREATED
- [ ] APPOINTMENT_CREATED
- [ ] APPOINTMENT_REMINDER
- [ ] TECHNICIAN_DISPATCHED
- [ ] JOB_COMPLETED
- [ ] ESTIMATE_SENT
- [ ] ESTIMATE_APPROVED
- [ ] INVOICE_CREATED
- [ ] PAYMENT_COMPLETED
- [ ] ORDER_CREATED
- [ ] ORDER_SHIPPED

---

## TASK 22.2 — Automation Actions

Actions:

- [ ] SEND_SMS
- [ ] SEND_EMAIL
- [ ] CREATE_TASK
- [ ] CREATE_JOB
- [ ] CREATE_APPOINTMENT
- [ ] SEND_PAYMENT_LINK
- [ ] REQUEST_REVIEW
- [ ] WEBHOOK

---

## TASK 22.3 — Workflow Builder

### Description

Allow business owners to visually create:

```text
WHEN
Job Completed

IF
Invoice > $500

THEN
Send SMS
+
Send Email
+
Create Follow-up Task
```

### Checklist

- [ ] Trigger model
- [ ] Conditions
- [ ] Actions
- [ ] Workflow UI
- [ ] Enable/disable
- [ ] Execution history
- [ ] Retry
- [ ] Error handling

---

# PHASE 23 — CALL INTELLIGENCE

## TASK 23.1 — Call Recording

### Checklist

- [ ] Recording reference
- [ ] Secure storage
- [ ] Retention settings
- [ ] Access permissions

---

## TASK 23.2 — Transcript

### Checklist

- [ ] Transcription
- [ ] Speaker identification
- [ ] Timestamp
- [ ] Search
- [ ] Storage

---

## TASK 23.3 — AI Summary

Generate:

- [ ] Intent
- [ ] Problem
- [ ] Outcome
- [ ] Customer sentiment
- [ ] Appointment status
- [ ] Follow-up
- [ ] Important notes

---

## TASK 23.4 — Call Classification

Categories:

- [ ] Booking
- [ ] Rescheduling
- [ ] Cancellation
- [ ] Sales
- [ ] Support
- [ ] Emergency
- [ ] Billing
- [ ] Product inquiry
- [ ] Order inquiry
- [ ] Spam
- [ ] Human transfer

---

# PHASE 24 — HUMAN HANDOFF

## TASK 24.1 — Call Transfer

### Checklist

- [ ] Transfer to user
- [ ] Transfer to department
- [ ] Transfer to technician
- [ ] Emergency routing
- [ ] Business-hours routing
- [ ] After-hours routing

---

## TASK 24.2 — Handoff Context

Before transfer provide:

- [ ] Customer
- [ ] Intent
- [ ] Summary
- [ ] Job
- [ ] Appointment
- [ ] AI actions already performed

---

# PHASE 25 — COMMUNICATION AUTOMATION

## TASK 25.1 — SMS Templates

Templates:

- [ ] Booking confirmation
- [ ] Reminder
- [ ] Technician en route
- [ ] Technician arrived
- [ ] Job completed
- [ ] Invoice
- [ ] Payment
- [ ] Review request

---

## TASK 25.2 — Email Templates

- [ ] Booking
- [ ] Estimate
- [ ] Invoice
- [ ] Receipt
- [ ] Reminder
- [ ] Review

---

# PHASE 26 — ADMIN DASHBOARD

## TASK 26.1 — Dashboard

Display:

- [ ] Calls
- [ ] Leads
- [ ] Bookings
- [ ] Jobs
- [ ] Revenue
- [ ] Outstanding invoices
- [ ] AI resolution rate

---

## TASK 26.2 — CRM UI

- [ ] Customers
- [ ] Leads
- [ ] Products
- [ ] Services
- [ ] Orders
- [ ] Jobs
- [ ] Appointments
- [ ] Calls
- [ ] Invoices

---

## TASK 26.3 — Scheduling UI

- [ ] Calendar
- [ ] Day view
- [ ] Week view
- [ ] Technician view
- [ ] Drag/drop
- [ ] Reschedule

---

## TASK 26.4 — Dispatch UI

- [ ] Technician columns
- [ ] Job cards
- [ ] Unassigned jobs
- [ ] Assignment
- [ ] Reassignment
- [ ] Status
- [ ] ETA

---

# PHASE 27 — ANALYTICS

## TASK 27.1 — Call Analytics

- [ ] Total calls
- [ ] Answer rate
- [ ] Missed calls
- [ ] Average duration
- [ ] Transfer rate
- [ ] AI resolution rate

---

## TASK 27.2 — Sales Analytics

- [ ] Leads
- [ ] Qualified leads
- [ ] Bookings
- [ ] Conversion
- [ ] Revenue per lead
- [ ] Revenue per call
- [ ] Product sales

---

## TASK 27.3 — Operations Analytics

- [ ] Jobs completed
- [ ] Cancellation rate
- [ ] No-show rate
- [ ] Technician utilization
- [ ] Average job duration
- [ ] Response time

---

# PHASE 28 — INTEGRATIONS

## TASK 28.1 — Integration Framework

Create a provider abstraction.

Example:

```text
CRMProvider
├── ServiceTitan
├── HubSpot
└── Salesforce
```

### Checklist

- [ ] Provider interface
- [ ] OAuth
- [ ] Credential storage
- [ ] Connection status
- [ ] Sync status
- [ ] Error handling
- [ ] Retry

---

## TASK 28.2 — Calendar Integrations

- [ ] Google Calendar
- [ ] Outlook Calendar

---

## TASK 28.3 — Commerce Integrations

- [ ] Shopify
- [ ] WooCommerce

---

## TASK 28.4 — Accounting

- [ ] QuickBooks
- [ ] Xero

---

# PHASE 29 — AI BUSINESS SETUP

## TASK 29.1 — AI Onboarding Assistant

### Description

Allow the owner to describe their business in natural language.

Example:

> "We are an HVAC company in Texas. We install and repair residential AC systems."

AI should suggest:

```text
Industry: HVAC

Business Model:
Products + Services

Modules:
✓ Customers
✓ Products
✓ Inventory
✓ Services
✓ Jobs
✓ Appointments
✓ Technicians
✓ Estimates
✓ Invoices
✓ Payments
✓ Equipment
✓ Memberships
✓ AI Calling
```

### Checklist

- [ ] Natural language input
- [ ] Business extraction
- [ ] Industry classification
- [ ] Business model detection
- [ ] Module recommendation
- [ ] Custom field recommendation
- [ ] Service recommendation
- [ ] AI configuration recommendation
- [ ] Human review
- [ ] Confirm setup
- [ ] Persist configuration

---

# PHASE 30 — AI AGENT CONFIGURATION

## TASK 30.1 — Agent Profile

Allow business owner to configure:

- [ ] Agent name
- [ ] Voice
- [ ] Language
- [ ] Tone
- [ ] Greeting
- [ ] Business hours
- [ ] Transfer rules
- [ ] Escalation rules

---

## TASK 30.2 — Agent Capabilities

Allow:

- [ ] Answer calls
- [ ] Book appointments
- [ ] Reschedule
- [ ] Cancel
- [ ] Product search
- [ ] Inventory lookup
- [ ] Pricing
- [ ] Lead creation
- [ ] Lead qualification
- [ ] Order lookup
- [ ] Payment links
- [ ] SMS
- [ ] Human transfer

---

# PHASE 31 — AI GUARDRAILS

## TASK 31.1 — No Hallucinated Business Data

AI must never invent:

- [ ] Price
- [ ] Inventory
- [ ] Availability
- [ ] Technician
- [ ] Customer history
- [ ] Order status
- [ ] Payment status

All operational information must come from tools.

---

## TASK 31.2 — Confirmation Rules

Require confirmation before:

- [ ] Booking
- [ ] Cancellation
- [ ] Rescheduling
- [ ] Order placement
- [ ] Payment action
- [ ] Destructive changes

---

## TASK 31.3 — Tool Authorization

Every tool call must verify:

- [ ] Organization
- [ ] User/agent permission
- [ ] Resource ownership
- [ ] Input validation
- [ ] Audit logging

---

# PHASE 32 — AI COST TRACKING

## TASK 32.1 — Usage Tracking

Track per organization:

- [ ] Voice minutes
- [ ] LLM tokens
- [ ] AI requests
- [ ] Tool calls
- [ ] SMS
- [ ] Transcription
- [ ] Storage

---

## TASK 32.2 — COGS

Calculate:

```text
Revenue
- Voice cost
- LLM cost
- SMS cost
- Transcription cost
- Storage
- Infrastructure
=
Gross Margin
```

### Checklist

- [ ] Usage records
- [ ] Cost calculation
- [ ] Organization dashboard
- [ ] Admin COGS dashboard
- [ ] Billing limits
- [ ] Alerts

---

# PHASE 33 — SECURITY

## TASK 33.1 — Security Baseline

- [ ] Tenant isolation
- [ ] RBAC
- [ ] API authorization
- [ ] Input validation
- [ ] Rate limiting
- [ ] Webhook verification
- [ ] Audit logs
- [ ] Secure file access
- [ ] Encryption
- [ ] Secrets management

---

# PHASE 34 — OBSERVABILITY

## TASK 34.1 — Logging

Track:

- [ ] API requests
- [ ] AI requests
- [ ] Tool calls
- [ ] Voice events
- [ ] Webhooks
- [ ] Payments
- [ ] Automation executions

---

## TASK 34.2 — Metrics

Track:

- [ ] API latency
- [ ] AI latency
- [ ] Tool latency
- [ ] Tool failure rate
- [ ] Booking failure rate
- [ ] Webhook failures
- [ ] Voice failures

---

# PHASE 35 — AI TESTING

## TASK 35.1 — Voice Scenarios

Test:

- [ ] New customer
- [ ] Existing customer
- [ ] Product inquiry
- [ ] Inventory inquiry
- [ ] Price inquiry
- [ ] Booking
- [ ] Rescheduling
- [ ] Cancellation
- [ ] Emergency
- [ ] No availability
- [ ] Human transfer
- [ ] Angry customer
- [ ] After-hours call

---

## TASK 35.2 — AI Evaluation

Evaluate:

- [ ] Intent accuracy
- [ ] Customer identification
- [ ] Product identification
- [ ] Service identification
- [ ] Tool selection
- [ ] Availability correctness
- [ ] Booking correctness
- [ ] Pricing correctness
- [ ] Escalation correctness

---

# PHASE 36 — END-TO-END GOLDEN FLOWS

## FLOW 1 — Service Business

```text
Customer calls
→ AI answers
→ Finds customer
→ Understands issue
→ Finds service
→ Checks availability
→ Offers slots
→ Customer confirms
→ Creates job
→ Creates appointment
→ Assigns technician
→ Sends SMS
→ Technician dispatched
→ Technician completes job
→ Estimate if required
→ Invoice
→ Payment link
→ Payment
→ Review request
```

### Checklist

- [ ] Complete flow works
- [ ] Database state correct
- [ ] Events emitted correctly
- [ ] Notifications sent
- [ ] AI transcript correct
- [ ] Customer timeline correct

---

# FLOW 2 — Commerce Business

```text
Customer calls
→ AI identifies customer
→ Searches product
→ Checks variant
→ Checks inventory
→ Gives real price
→ Customer confirms
→ Creates order
→ Payment link
→ Payment
→ Confirmation SMS
```

### Checklist

- [ ] Product search
- [ ] Variant
- [ ] Inventory
- [ ] Price
- [ ] Order
- [ ] Payment
- [ ] Notification
- [ ] Customer timeline

---

# FLOW 3 — Existing Customer Support

```text
Customer calls
→ Identify customer
→ Load history
→ Find previous order/job
→ Understand problem
→ Check warranty
→ Create support job
→ Schedule technician
→ Send confirmation
```

### Checklist

- [ ] Customer identified
- [ ] History loaded
- [ ] Warranty checked
- [ ] Job created
- [ ] Appointment created
- [ ] SMS sent

---

# PHASE 37 — PRODUCTION READINESS

## TASK 37.1 — Reliability

- [ ] Database backups
- [ ] Retry policies
- [ ] Idempotency
- [ ] Queue retry
- [ ] Dead-letter handling
- [ ] Graceful shutdown
- [ ] Health checks
- [ ] Readiness checks

---

## TASK 37.2 — Performance

- [ ] Database indexes
- [ ] Query optimization
- [ ] Pagination
- [ ] Caching
- [ ] Connection pooling
- [ ] AI context optimization
- [ ] Tool latency optimization
- [ ] Scheduling query optimization

---

## TASK 37.3 — Final QA

- [ ] Frontend build
- [ ] Backend build
- [ ] Unit tests
- [ ] Integration tests
- [ ] E2E tests
- [ ] Security tests
- [ ] Tenant isolation tests
- [ ] AI scenario tests
- [ ] Payment tests
- [ ] Webhook tests
- [ ] Production deployment test

---

# MVP RELEASE CHECKLIST

The following must be completed before the first serious production release:

## Foundation

- [ ] Multi-tenancy
- [ ] RBAC
- [ ] Tenant isolation
- [ ] Business onboarding

## CRM

- [ ] Customers
- [ ] Locations
- [ ] Leads
- [ ] Timeline
- [ ] Custom fields

## Commerce

- [ ] Products
- [ ] Categories
- [ ] Variants
- [ ] Inventory
- [ ] Orders

## Field Service

- [ ] Services
- [ ] Pricebook
- [ ] Jobs
- [ ] Appointments
- [ ] Scheduling
- [ ] Technicians
- [ ] Dispatch

## AI

- [ ] Voice agent
- [ ] AI tools
- [ ] AI booking
- [ ] Product search
- [ ] Inventory lookup
- [ ] RAG
- [ ] AI summaries
- [ ] Human handoff

## Billing

- [ ] Estimates
- [ ] Invoices
- [ ] Stripe payments

## Communication

- [ ] SMS
- [ ] Email
- [ ] Automated notifications

## Platform

- [ ] Dashboard
- [ ] Analytics
- [ ] Automation
- [ ] Audit logs
- [ ] Usage tracking
- [ ] COGS
- [ ] Monitoring

---

# IMPORTANT IMPLEMENTATION PRINCIPLE

Do NOT build this as one giant CRM.

Build it as a configurable platform:

```text
                         ORGANIZATION
                              │
                    BUSINESS CONFIGURATION
                              │
                 ┌────────────┴────────────┐
                 │                         │
            CRM CONFIG                  AI CONFIG
                 │                         │
        ┌────────┼────────┐        ┌───────┼────────┐
        │        │        │        │       │        │
     Products Services  Jobs     Voice   SMS     RAG
        │        │        │        │       │        │
        └────────┴────────┴────────┴───────┴────────┘
                              │
                       BUSINESS OS
```

Every organization should get its own:

- CRM configuration
- Modules
- Custom fields
- Custom objects
- Products
- Services
- Pricebook
- Workflows
- AI agent
- Knowledge base
- Automation
- Integrations
- Permissions

The goal is that a business owner can sign up and configure the platform without engineering changes.

---

# FINAL DEFINITION OF DONE

The platform is considered complete when a new business can:

- [ ] Sign up
- [ ] Describe their business
- [ ] Select industry
- [ ] Select business model
- [ ] Automatically receive recommended CRM configuration
- [ ] Review configuration
- [ ] Add products
- [ ] Add services
- [ ] Configure pricing
- [ ] Configure inventory
- [ ] Configure business hours
- [ ] Configure technicians
- [ ] Configure AI agent
- [ ] Upload knowledge
- [ ] Connect phone number
- [ ] Receive a customer call
- [ ] AI identifies customer
- [ ] AI understands request
- [ ] AI searches products/services
- [ ] AI checks real inventory
- [ ] AI checks real availability
- [ ] AI books appointment/order
- [ ] AI sends SMS
- [ ] Staff sees activity in CRM
- [ ] Staff manages job/order
- [ ] Technician completes job where applicable
- [ ] Estimate/invoice is generated
- [ ] Customer pays
- [ ] Automation follows up
- [ ] Business owner sees analytics

The final experience should feel like:

**"Connect your business → configure it once → AI runs the repetitive customer and operational work."**