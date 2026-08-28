# ScopeLock — Business SOP / Service Catalog Specification

## 1. Why the SOP exists

The LLM should understand client intent, but **commercial rules must come from the user's business SOP**.

The SOP is the source of truth for:

- available services/modules;
- what each module includes/excludes;
- pricing formulas;
- standard duration;
- dependencies;
- materiality settings;
- assumptions;
- change-control rules.

This keeps proposal pricing consistent and auditable.

---

## 2. MVP representation and versioning

Use a validated YAML or JSON document loaded into the backend and mirrored to Firestore.

`config/jvl_sop.example.yaml` is a demo template. Its values are **illustrative placeholders**, not authoritative JVL pricing. Replace them with confirmed demo values before final recording.

Every catalog must have an immutable, non-empty `version`. Every pricing result and price line item records that version so a commercial result can be reproduced after the SOP changes.

P0 supports only an explicit `USD` catalog currency. A missing or different currency is rejected before calculation.

---

## 3. Module schema

```yaml
version: jvl-demo-v1
business:
  name: JVL
  currency: USD

modules:
  - key: line_notifications
    name: LINE Notification Integration
    description: Send workflow notifications through LINE.
    pricing:
      type: fixed
      amount_usd: 750
    timeline:
      base_days: 3
      parallelizable: false
    included:
      - one notification flow
      - one LINE channel/account
    excluded:
      - chatbot conversation logic
      - LINE mini app
    dependencies:
      - core_workflow_automation
    aliases:
      - LINE alerts
      - LINE notification
    scope_rules:
      material_if_added: true
```

Catalog validation rejects:

- duplicate or malformed module keys;
- unknown, self-referencing, duplicate, or cyclic dependencies;
- blank or duplicate aliases, inclusions, exclusions, or dependencies;
- one normalized item appearing in both `included` and `excluded`;
- one normalized alias assigned to multiple modules;
- missing or non-boolean `scope_rules.material_if_added` values;
- unknown fields in catalog, module, policy, pricing, timeline, or materiality records.

---

## 4. Supported pricing rules for P0

Keep pricing deliberately simple.

### Fixed

```yaml
type: fixed
amount_usd: 750
```

A fixed module is one package and therefore accepts only quantity `1`.

### Per unit

```yaml
type: per_unit
unit: integration
amount_usd: 600
minimum_units: 1
```

Per-unit quantity must be a positive integer at or above `minimum_units`.

No percentage-based pricing, floating model estimates, currency conversion, or LLM-generated monetary values are allowed in P0.

---

## 5. Pricing input and duplicate policy

The PricingEngine accepts only this application-owned input:

```json
{
  "module_key": "line_notifications",
  "quantity": 1
}
```

Extra fields such as model-proposed unit amounts, subtotals, totals, currency, or SOP version are rejected.

Duplicate selections follow one deterministic policy:

- repeated fixed-price module selections collapse to one module instance, and every incoming selection must have quantity `1`;
- repeated per-unit selections merge by summing quantities;
- normalized output keeps the first-seen module order;
- required dependencies must also be explicitly selected; the engine never silently adds a chargeable module.

This prevents repeated semantic mappings from charging the same fixed package twice while preserving additive per-unit intent.

---

## 6. Immutable pricing output

Each line item contains:

- `module_key`;
- normalized `quantity`;
- `unit_rule` (`fixed` or `per_unit`);
- optional per-unit name;
- `unit_amount_usd` read from the SOP;
- deterministic `subtotal_usd`;
- `currency: USD`;
- `sop_version`.

The result contains the same `currency` and `sop_version`, an immutable tuple of line items, and `total_usd` calculated only by summing line subtotals.

---

## 7. Timeline rules

For the hackathon, avoid building a scheduling optimizer.

Each module has:

- `base_days`;
- optional dependencies;
- `parallelizable`.

A deterministic timeline engine computes a defensible estimate. The accepted algorithm is implemented and tested during Day 4.

P0 uses this exact algorithm:

1. Normalize duplicate module selections with the same fixed/per-unit policy used by deterministic pricing.
2. Require every dependency to be explicitly selected, reject unknown or cyclic dependencies, and process modules in deterministic topological order.
3. Choose the selected module with the greatest `base_days` as the base module; break equal-duration ties by module key.
4. Start with the base module's full `base_days`.
5. Add the full `base_days` of every other selected module whose `parallelizable` value is `false`.
6. Add zero incremental days for every other selected module whose `parallelizable` value is `true`.
7. P0 records quantity but does not multiply duration by quantity. A future per-unit duration rule requires a new SOP schema/version.

The immutable result records normalized calculation inputs, the base module, one line per selected module, dependency keys, incremental days, total days, and SOP version.

---

## 8. Proposal mapping

The agent returns semantic selections and evidence:

```json
{
  "module_key": "line_notifications",
  "quantity": 1,
  "mapped_requirement": "Notify managers through LINE when approval is required",
  "confidence": 0.96
}
```

Application code projects only `module_key` and `quantity` into the PricingEngine. The service validates the catalog key, quantity, dependencies, rule, currency, and SOP version before calculating line items.

---

## 9. Included / excluded work

Explicit exclusions are important because they become future scope-diff evidence.

```yaml
excluded:
  - mobile application
  - custom ERP replacement
  - 24/7 managed operations
  - customer-facing AI response generation
```

If the client later requests an excluded item, the Scope Analyzer should have strong evidence for a material scope event.

---

## 10. User overrides

For P0, allow authorized user edits before proposal approval to module selection, quantity, price, timeline, assumptions, or exclusions. Overrides must be logged.

A price override is a separate, explicit application-owned audit record applied after the baseline deterministic calculation. It is never accepted through agent output or the PricingEngine's module-selection input.

If an override becomes a reusable business rule, it may be promoted into `UserPolicy` or a new SOP version only after explicit user action.
