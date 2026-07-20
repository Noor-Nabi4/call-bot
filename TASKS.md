# Product Enhancement Roadmap

## Transforming the AI HVAC Receptionist into a Multi-Industry AI Voice Platform

---

# Vision

Transform the current HVAC-focused AI receptionist into a **multi-tenant AI Voice Platform** capable of powering:

* AI Receptionists
* AI Customer Support
* AI Sales Agents
* AI Appointment Booking
* AI Call Centers
* AI Lead Qualification
* AI Order Support
* AI Collections
* AI Help Desk

The platform should allow every customer (tenant) to create an AI employee customized for their own business without modifying application code.

---

# Goals

## Current

Single AI agent
↓

HVAC business

↓

Appointment booking

↓

Knowledge Base

↓

CRM

---

## Future

One Platform

↓

Unlimited Businesses

↓

Unlimited Industries

↓

Unlimited AI Agents

↓

Unlimited Phone Numbers

↓

Unlimited Workflows

↓

Enterprise Ready

---

# Platform Architecture

```
Platform
│
├── Multi Tenant
│
├── AI Agent Engine
│
├── Knowledge Engine
│
├── Telephony
│
├── CRM
│
├── Scheduling
│
├── Billing
│
├── Analytics
│
├── Automation
│
└── Marketplace
```

---

# Industries

Instead of supporting only HVAC, support configurable industries.

Examples:

* HVAC
* Plumbing
* Electrical
* Roofing
* Pest Control
* Cleaning
* Landscaping
* Locksmith
* Appliance Repair
* Solar
* Medical
* Dental
* Veterinary
* Restaurants
* Salons
* Auto Repair
* Insurance
* Legal
* Real Estate
* Property Management
* Ecommerce
* Logistics
* Customer Support
* Call Centers
* Custom Business

No industry-specific code should exist inside the AI logic.

---

# AI Agent Types

Allow every tenant to create multiple agent profiles.

Examples

### Receptionist

Answers calls

Books appointments

Transfers calls

Collects customer information

---

### Customer Support

Answer FAQs

Troubleshooting

Returns

Policies

Order status

---

### Sales

Lead qualification

Product recommendation

Upselling

Quote requests

---

### Call Center

Inbound support

Outbound campaigns

Ticket creation

Complaint handling

Escalations

---

### Booking Assistant

Appointments

Reservations

Calendar management

---

### Help Desk

Technical support

Ticket lookup

Reset requests

---

### Custom Agent

Fully configurable

---

# Industry Templates

Instead of coding prompts manually.

```
Choose Industry

↓

Choose Template

↓

Customize

↓

Deploy
```

Templates

HVAC

Medical

Restaurant

Insurance

Real Estate

Call Center

Support

Sales

Custom

Each template includes

Greeting

Business Rules

Conversation Style

Tool Configuration

Suggested Knowledge

Example Questions

Safety Rules

---

# Agent Builder

Every tenant should configure an AI agent visually.

Identity

Assistant Name

Voice

Greeting

Language

Personality

Conversation

Response Style

Professional

Friendly

Sales

Support

Formal

Casual

Business

Business Hours

Locations

Services

Policies

Pricing

Emergency Rules

Knowledge

Upload Documents

Website

FAQs

PDFs

Word

CSV

Database

Behavior

Maximum response length

Ask follow-up questions

Confirm actions

Transfer rules

Confidence threshold

Escalation

Tools

Enable

CRM

Scheduling

Invoices

Orders

SMS

Email

Payments

Custom APIs

---

# Agent Profiles

Support multiple profiles.

Example

```
Main Receptionist

Sales Agent

Support Agent

Spanish Receptionist

After Hours Agent

Weekend Agent
```

Each profile has

Prompt

Knowledge

Voice

Tools

Schedule

Phone Number

---

# Phone Number Management

Tenant should manage phone numbers.

Options

Buy Number

Connect Existing Twilio

Future SIP Providers

Features

Search

Purchase

Assign Agent

Assign Business Hours

Assign Routing

Call Recording

Call Forwarding

Caller ID

---

# AI Routing

Incoming Call

↓

Phone Number

↓

Business Rules

↓

Correct AI Agent

↓

Conversation

↓

Human Transfer

Routing Based On

Phone Number

Business Hours

Department

Language

VIP Customer

Location

Call Intent

---

# Multi-Agent Routing (Future)

Router Agent

↓

Sales

↓

Support

↓

Billing

↓

Appointments

↓

Technical

Router decides where to transfer.

---

# Call Flows

Visual Builder

Greeting

↓

Collect Name

↓

Collect Reason

↓

Lookup CRM

↓

Book Appointment

↓

Transfer

↓

Finish

Drag & Drop Editor

---

# CRM

Unified CRM

Customers

Leads

Companies

Jobs

Appointments

Notes

Call History

Activities

Tags

Custom Fields

---

# Scheduling

Google Calendar

Outlook

Internal Calendar

Technician Scheduling

Resources

Availability

Recurring Appointments

Reminders

---

# Knowledge Platform

Sources

Website

PDF

Word

CSV

Notion

Google Docs

FAQ

Database

Features

Auto Sync

Versioning

Approval Workflow

Categories

Search

---

# AI Memory

Short Memory

Conversation

Long Memory

Preferences

Previous Calls

Orders

Notes

Future

Conversation Insights

---

# Analytics Dashboard

Executive Dashboard

Calls

Answered

Missed

Appointments

Revenue

Average Duration

Resolution Rate

Agent Performance

Graphs

Daily Calls

Weekly Trends

Monthly Growth

Top Intent

Transfer Rate

Knowledge Usage

---

# Call Center Features

Queue Management

Departments

Agents

Skills

Transfer Rules

Call Recording

Live Monitoring

Whisper

Barge

Supervisor Dashboard

After Call Work

Disposition Codes

Quality Scores

---

# Workforce Management

Technicians

Customer Service

Sales

Availability

Locations

GPS

Status

Assignments

---

# Integrations

CRM

Salesforce

HubSpot

Zoho

Pipedrive

Calendars

Google

Microsoft

Communication

Twilio

LiveKit

Email

SMS

Slack

Teams

Payments

Stripe

QuickBooks

Xero

Custom REST APIs

Webhooks

---

# Billing

Stripe

Plans

Usage

Voice Minutes

Phone Numbers

AI Agents

Knowledge Storage

Team Members

Enterprise Features

Customer Portal

Invoices

Coupons

Trials

---

# Marketplace

Install ready-made AI agents.

Examples

HVAC

Medical

Insurance

Restaurant

Sales

Support

Collections

Real Estate

One Click Install

---

# White Label

Custom Logo

Brand Colors

Domain

Emails

Voice Identity

---

# Security

Multi Tenant Isolation

RBAC

Audit Logs

Encryption

API Keys

Rate Limits

Secret Management

---

# Admin Portal

Tenants

Subscriptions

Usage

Phone Numbers

Support

System Health

Logs

Feature Flags

Announcements

---

# Developer Platform

REST API

Webhooks

SDK

OAuth

Custom Integrations

CLI

---

# AI Improvements

* Tenant-aware prompts
* Dynamic prompt composition
* RAG
* Function calling
* Conversation summarization
* Intent detection
* Entity extraction
* Confidence scoring
* Human handoff
* Personalization
* Context optimization
* Guardrails
* Hallucination reduction
* Prompt versioning
* Agent evaluation pipeline

---

# Roadmap

## Phase 1 (Completed)

* LiveKit voice agent
* OpenAI Realtime
* Tenant resolution
* Dynamic prompts
* CRM tools
* Scheduling
* Knowledge search
* Human handoff

## Phase 2 (Completed in code — operator verification pending)

* [x] Multi-industry support (industry template registry; no industry branches in voice logic)
* [x] Multi agent profiles per tenant + phone → profile routing
* [x] Agent Builder UI (`ops/agents`)
* [x] Industry templates (apply + optional KB seed)
* [x] Phone number management in Ops (inventory, buy/connect, assign, test call)
* [x] Ops premium redesign (shell sections, dashboard/dispatch/agents/phones polish)

Deferred to later Telephony phase: call recording, forwarding, caller ID, voicemail.

## Phase 3

* [x] Billing (Stripe Checkout + webhooks + ops entitlement gate — existing)
* [x] Stripe (platform account Checkout / Portal / signature-verified webhooks — existing)
* [x] Customer Portal (Ops → Stripe Billing Portal — existing)
* [x] Usage tracking (`billable_seconds` on calls, `GET /billing/usage`, Ops billing usage panel)
* [x] Entitlement enforcement (hard: team seats, phone numbers, knowledge docs; soft: voice minutes/overage estimate)
* [x] Team management (`PATCH /api/admin/users/{id}`, Ops `/settings/team` invite/role/deactivate)

Deferred: Stripe metered overage invoices, in-app plan upgrades via Checkout, email invite/magic link, true no-card trial.

## Phase 4

* Visual Call Flow Builder
* [x] Knowledge management improvements (edit/deactivate, agent-profile scope, Ops search preview via `POST /api/knowledge/search`)
* [x] Advanced analytics (voice minutes, avg duration, handoffs, disconnect reasons, calls-by-day on Ops `/metrics`)
* [x] Automation rules (triggers: call ended / handoff / appointment created; actions: audit + follow-up job; Ops `/settings/automations`)

## Phase 5

* Call center features
* Supervisor dashboard
* Queue management
* Quality monitoring
* Live monitoring

## Phase 6

* Marketplace
* White label
* Multi-agent routing
* Enterprise integrations
* Public APIs

---

# Guiding Principles

1. Build one platform, not one industry solution.
2. Every business should configure—not require code changes.
3. Tenant isolation is mandatory.
4. Use real data only—no mock data in production.
5. Keep AI responses concise, natural, and human-like.
6. Make every major capability modular and feature-flagged.
7. Design APIs and data models to support future industries without breaking existing tenants.
8. Ensure scalability for thousands of tenants, millions of calls, and enterprise deployments.
