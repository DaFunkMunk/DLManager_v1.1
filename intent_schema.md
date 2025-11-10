Intent & Slot Schema for Natural-Language Prompts
=================================================

Overview
--------
This document defines the target schema we expect from the intent+slot parser that will power natural-language prompts. Every parsed utterance must resolve to one of the supported intents and populate the slots listed below. The output will later be validated against these requirements (e.g., via Pydantic/JSON Schema) before being compiled into expressions or rule updates.

Top-Level Fields
----------------

```json
{
  "intent": "add_rule",
  "confidence": 0.92,
  "slots": {
    "...": "..."
  },
  "raw_text": "Add contractors in Permian Field Office",
  "tokens": ["add", "contractors", ...]
}
```

* `intent` – enumerated label describing the action.
* `confidence` – parser output in [0,1]; used to decide whether to trust the result.
* `slots` – dictionary of slot names to canonical values (defined per intent below).
* `raw_text` / `tokens` – optional debugging aids stored with audit logs.

Supported Intents & Slots
-------------------------

### `add_rule`
Create a new inclusion rule or refresh an existing one.

Required slots:
- `rule_type` – one of `user`, `location`, `role`, `employmentType`, `manager`, `directoryGroup`, `tag`, `tenureWindow`, `dynamicExpression`.
- `rule_value` – canonical value (e.g., `"Permian Field Office"`).
- `group` (optional if already selected in UI).

Optional slots:
- `expression` – when `rule_type == dynamicExpression`.
- `notes` – free-form explanation shown to the user.

### `remove_rule`
Drop an existing rule or explicit membership.

Required slots:
- `rule_type`
- `rule_value`

Optional:
- `group`
- `reason`

### `edit_rule`
Modify the criteria for an existing rule.

Required slots:
- `rule_type`
- `from_value`
- `to_value`

Optional:
- `group`
- `expression` (if editing a dynamic expression rule)

### `employee_record_set`
Update fields on a specific user via the Employee Record rule.

Required slots:
- `user` – canonical display name or email.
- `field_updates` – array of `{ "field": "tenureDays", "value": 365 }`.

Optional:
- `group`

### `employee_record_clear`
Clear one or more fields for a user.

Required slots:
- `user`
- `fields_to_clear` – array of field names.

### `expression_rule`
Standalone expression generation (without add/remove context).

Required slots:
- `expression` – string containing the compiled expression language.

Optional:
- `intent_hint` – e.g., `add_rule` vs `remove_rule` for downstream use.

JSON Schema (Draft 7)
---------------------

```json
{
  "$id": "https://dlmanager.local/nlp-intent.schema.json",
  "type": "object",
  "required": ["intent", "confidence", "slots"],
  "properties": {
    "intent": {
      "type": "string",
      "enum": [
        "add_rule",
        "remove_rule",
        "edit_rule",
        "employee_record_set",
        "employee_record_clear",
        "expression_rule"
      ]
    },
    "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
    "slots": {
      "type": "object",
      "properties": {
        "group": { "type": "string" },
        "rule_type": { "type": "string" },
        "rule_value": { "type": "string" },
        "from_value": { "type": "string" },
        "to_value": { "type": "string" },
        "expression": { "type": "string" },
        "user": { "type": "string" },
        "field_updates": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["field", "value"],
            "properties": {
              "field": { "type": "string" },
              "value": {}
            }
          }
        },
        "fields_to_clear": {
          "type": "array",
          "items": { "type": "string" }
        },
        "notes": { "type": "string" },
        "reason": { "type": "string" }
      },
      "additionalProperties": false
    },
    "raw_text": { "type": "string" },
    "tokens": {
      "type": "array",
      "items": { "type": "string" }
    }
  },
  "additionalProperties": false
}
```

Normalization Guidelines
------------------------

* Convert slot values to the canonical labels already used in dropdowns (e.g., map “permian office” → “Permian Field Office”).
* `rule_type` must align with back-end identifiers (`employment-type`, `directory-group`, `employee-record`, etc.).
* Numeric values (tenure, days) should be parsed as integers before compilation.

Normalization Resource
----------------------

Use `nlp_synonyms.json` to canonicalize values. The file defines:

* `rule_type` synonyms – map arbitrary phrases to backend rule identifiers.
* `value_synonyms` – per-field canonical values (locations, roles, managers, etc.).
* `boolean_values` / `tenure_phrases` – helpers for active/inactive wording and tenure ranges.

During parsing:
1. Lowercase the extracted slot text.
2. Look it up in the relevant synonym table (rule type, location, etc.).
3. If a match exists, replace it with the canonical label before validation.
4. If no match exists, flag the slot as low-confidence so the UI can fall back to manual selection.

Next Steps
----------

1. Build synonym tables for locations, roles, managers, and other enumerations.
2. Collect labeled utterances per intent to train the spaCy/sklearn classifier/slotter.
3. Implement a validator (JSON Schema or Pydantic) to enforce this contract before translating slots into expressions or rule mutations.
