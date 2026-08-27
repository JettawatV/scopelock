# ScopeLock — Business SOP / Service Catalog Specification

## 1. Why the SOP exists

The LLM should understand client intent, but **commercial rules must come from the user's business SOP**.

The SOP is the source of truth for:
- available services/modules;
- what each module includes/excludes;
- pricing formulas;
- standard duration;
- dependencies;
- assumptions;
- change-control rules.

This keeps proposal pricing consistent and auditable.

---

## 2. MVP representation

Use a validated YAML or JSON document loaded into the backend and mirrored to Firestore.

`config/jvl_sop.example.yaml` is a demo template.

The example values are **illustrative placeholders**, not authoritative JVL pricing. Replace them with confirmed demo values before final recording.

---

## 3. Module schema

```yaml
key: line_notifications
name: LINE Notification Integration
description: Send workflow notifications through LINE.
pricing:
  type: fixed
  amount_thb: 15000
timeline:
  base_days: 3
included:
  - one notification flow
  - one LINE channel/account
excluded:
  - chatbot conversation logic
  - LINE mini app
dependencies:
  - core_workflow
aliases:
  - LINE alerts
  - LINE notification
scope_rules:
  material_if_added: true
```

---

## 4. Supported pricing rules for P0

Keep pricing deliberately simple:

### Fixed
```yaml
type: fixed
amount_thb: 15000
```

### Per unit
```yaml
type: per_unit
unit: integration
amount_thb: 12000
minimum_units: 1
```

No percentage-based pricing or LLM-generated estimates in P0.

---

## 5. Timeline rules

For the hackathon, avoid building a scheduling optimizer.

Each module has:
- `base_days`;
- optional dependencies.

A deterministic timeline engine computes a defensible estimate.

Simple accepted rule:
- base project duration;
- add incremental days for modules that cannot run in parallel;
- allow a module to declare `parallelizable: true`.

Document the exact algorithm in code/tests.

---

## 6. Proposal mapping

Agent returns:

```json
{
  "module_key": "line_notifications",
  "quantity": 1,
  "mapped_requirement": "Notify managers through LINE when approval is required",
  "confidence": 0.96
}
```

Pricing service validates:
- module exists;
- quantity allowed;
- pricing rule valid.

Then code calculates the line item.

---

## 7. Included / excluded work

Explicit exclusions are important for ScopeLock because they become future scope-diff evidence.

Example:

```yaml
excluded:
  - mobile application
  - custom ERP replacement
  - 24/7 managed operations
```

If the client later requests an excluded item, the Scope Analyzer should have strong evidence for a material scope event.

---

## 8. User overrides

For P0, allow user edits before proposal approval:
- module selection;
- quantity;
- price override;
- timeline override;
- assumptions/exclusions.

Overrides must be logged.

If a user override becomes a reusable business rule, it may be promoted into `UserPolicy` / SOP after explicit action.
