# Donation Plan for RGWND

## Purpose of This Document

This document describes a **temporary, legally safe, and trust‑preserving donation model** for RGWND, to be used **before** a formal paywall can be introduced.

The goal is **not monetization**, but:

* covering part of the infrastructure costs
* validating willingness to financially support the project
* strengthening trust with early, hardcore users
* preparing a clean transition to a future paid model

---

## Context and Constraints

### Legal Context (Belgium)

At the moment, RGWND does **not** operate under an ondernemingsnummer.

This implies:

* Payments **may not** be linked to feature access
* Payments **must** be voluntary
* Donations **must not** be framed as compensation for services

Therefore:

* ❌ “Donate to unlock features” → **not allowed**
* ✅ “Support the project voluntarily” → **allowed**

This donation model is designed to fully respect these constraints.

---

## Strategic Intent

This donation system is designed as a **bridge**, not an endpoint.

It should:

1. Feel fair and non‑intrusive
2. Only appear after value is delivered
3. Never block functionality
4. Create early supporters, not customers
5. Keep the future subscription model clean

The long‑term plan remains:

* Feature‑based paywall
* Subscription pricing
* Clear premium tiers

---

## Core Principles

### 1. Voluntary by Design

Donations must:

* never be required
* never unlock features
* never remove limits

All functionality remains identical for donors and non‑donors.

---

### 2. Value First, Ask Second

The donation prompt should only appear:

* **after** a successful route generation
* **after** computationally expensive routes

Never:

* on the homepage
* before results
* as a popup

---

### 3. Transparency Over Persuasion

The messaging must be:

* factual
* short
* non‑emotional

No guilt language.
No urgency.
No pressure.

---

## Where to Ask for Donations

### Recommended Placement

**Primary location**:

* Results page after route generation

**Secondary triggers (optional)**:

* Routes longer than 60 km
* Routes that took unusually long to compute

---

### Example Placement Copy (Dutch)

> *“Deze route vergde meer rekenkracht dan gemiddeld.*
> *Vind je RGWND nuttig? Je kan het project vrijwillig steunen.”*

Secondary explanation (optional, smaller text):

> *“RGWND draait op eigen kosten en vrije tijd. Donaties helpen om de dienst betrouwbaar en gratis te houden.”*

---

## Donation Amounts

### Preset Amounts Only

To minimize friction and decision fatigue:

* €2 – small appreciation
* €5 – typical support
* €10 – strong support

No custom amount field by default.

---

### Why These Amounts

* Low psychological barrier
* Comparable to a coffee or energy bar
* Appropriate for a free tool
* Scales naturally with perceived value

---

## Payment Implementation

### Platform Choice (Important)

RGWND **must not** use Stripe at this stage.

Reason:

* Stripe requires a legal entity or ondernemingsnummer
* Even for donations, Stripe will eventually request business verification
* Using Stripe prematurely risks account freezes and forced refunds

Therefore, donations must be handled via a **third-party platform that explicitly supports private individuals**.

---

### Approved Donation Platforms

#### Option 1: Buy Me a Coffee (Recommended)

Why this is the preferred solution:

* Designed for private individuals
* Explicitly donation-based
* No ondernemingsnummer required
* Familiar and trusted by technical users
* Simple fixed-amount support

Usage rules:

* One-time donations only
* No rewards
* No feature access
* No promises

---

#### Option 2: Ko-fi (Acceptable Alternative)

Also valid if Buy Me a Coffee is not desired:

* Supports individuals
* One-time donations possible
* Slightly more "creator-oriented" branding

Still legally safe if used correctly.

---

#### Option 3: PayPal.me (Last Resort)

Legally acceptable but not ideal:

* Lower trust
* Worse UX
* Higher dispute risk

Only use if other platforms are unavailable.

---

### Integration Model

* Use **external links only** (no embeds)
* Clearly state donations are voluntary
* Do not track donor identity
* Do not alter application behavior based on donations

RGWND itself:

* does not process payments
* does not store financial data
* does not handle refunds

This minimizes legal and GDPR exposure.

---

### Backend Handling

* Log outbound donation link clicks (optional, anonymous)
* Do **not** log payment confirmations
* Do **not** associate donations with users
* Do **not** expose donation status in UI

Donation data is **analytics only**, not access control.

---

## UX Rules (Important)

### What NOT to Do

* ❌ No popups
* ❌ No blocking banners
* ❌ No countdowns
* ❌ No “premium coming soon” messaging
* ❌ No donor badges or status symbols

---

### Tone Guidelines

* Neutral
* Respectful
* Honest
* Brief

Hardcore cyclists respect clarity and autonomy.

---

## Communication Strategy

### How to Explain Donations (If Asked)

Short, honest answer:

> “RGWND is currently a free project. Donaties zijn volledig vrijwillig en helpen om serverkosten te dragen tot een officieel betaalmodel mogelijk is.”

No over‑explaining.

---

## Relationship to Future Paywall

### What Donations Are NOT

* Not a discount
* Not early access
* Not lifetime rights
* Not premium credits

---

### What Donations ARE

* Early trust signal
* Willingness‑to‑pay indicator
* Community support

When the paywall is introduced:

* Donors become natural early subscribers
* Communication can be direct and respectful

---

## Transition Plan (Later)

When an ondernemingsnummer is available:

1. Disable donation flow
2. Introduce clear free vs premium tiers
3. Communicate transparently:

   * donations were temporary
   * subscriptions are now official
4. Optionally offer early supporters:

   * a thank‑you
   * a free trial
   * or early access

(No promises implied by donations.)

---

## Success Criteria

This donation plan is successful if:

* It does **not** annoy users
* It generates some cost coverage
* It identifies engaged users
* It builds trust rather than resistance

Revenue is secondary.

---

## Final Note

This donation model is intentionally modest.

Its strength is not income, but **credibility**.

By staying honest, restrained, and respectful, RGWND earns the right to later introduce a paid model without backlash.

This is the long game — and it fits the project.
