# Day 3 — SOP Validation and Deterministic Pricing Evidence

Recorded: **2026-08-27**

Environment:

- Python 3.13.14
- Google ADK 2.8.0 remains outside the pricing calculation boundary
- SOP version: `jvl-demo-v1`
- Currency: `USD`

## Focused verification

Command:

```powershell
.\.venv313\Scripts\python.exe -m pytest `
  tests/unit/test_sop_service.py `
  tests/unit/test_pricing_engine.py -q
```

Result: **32 passed in 0.61s**.

Covered controls:

- module keys, aliases, inclusions, exclusions, materiality, and dependencies;
- unknown, self-referencing, duplicate, and cyclic dependencies;
- fixed and per-unit pricing rules;
- per-unit minimum quantity;
- fixed and per-unit duplicate normalization;
- unknown modules and invalid quantities;
- malformed pricing rules and non-USD catalogs;
- explicit USD output and immutable price records;
- model amount/total fields rejected from pricing input;
- deterministic repeated calculations.

## Full repository regression

Command:

```powershell
.\.venv313\Scripts\python.exe -m pytest -q
```

Final result: **51 passed in 4.42s**, with one upstream ADK deprecation warning.

## Golden-path fixture

Fixture: `tests/fixtures/pricing_golden_path.json`

Inputs:

- `core_workflow_automation × 1`
- `email_intake × 1`
- `operations_dashboard × 1`
- `email_notifications × 1`

Expected deterministic result:

- Core Workflow Automation: `1 × USD 4,000 = USD 4,000`
- Gmail Intake Integration: `1 × USD 500 = USD 500`
- Operations Dashboard: `1 × USD 750 = USD 750`
- Email Notification Workflow: `1 × USD 400 = USD 400`
- Total: **USD 5,650**
- SOP version on every line and result: `jvl-demo-v1`

## Example trace

```text
Requirement Analyzer selection
  module_key=email_intake, quantity=1
      ↓ application projects only key + quantity
SOP jvl-demo-v1
  pricing.type=fixed, amount_usd=500, currency=USD
      ↓ PricingEngine arithmetic
PriceLineItem
  unit_rule=fixed, unit_amount_usd=500, subtotal_usd=500,
  currency=USD, sop_version=jvl-demo-v1
```

No model-supplied amount, subtotal, total, currency, or SOP version enters this calculation.
