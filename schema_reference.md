# MongoDB Schema Reference

Repository notes describing the structure of key MongoDB collections used by the Distribution List Copilot. Each section captures representative documents plus field explanations so future updates stay aligned with the live data model.

## Collections

### `audit`

Representative document:

```json
{
  "_id": "a_7fec3b180dc34170bd48ceeadb0270bd",
  "ts": "2025-11-03T22:54:38.298112",
  "actor": "admin",
  "op": "EDIT",
  "diffId": "d_57c8a17ad8f24e33ba720186e8f89224",
  "groupId": "g_acl_evin_north",
  "groupName": "ACL_EVIN-North",
  "rule": {
    "type": "employee-record",
    "label": "Employee Record",
    "value": "Alex Rivera"
  },
  "employeeRecord": {
    "userId": "u_alex",
    "userDisplayName": "Alex Rivera",
    "userEmail": "alex.rivera@demo.local",
    "changes": [
      {
        "field": "manager",
        "label": "Manager / Team Lead",
        "before": "Casey Lee",
        "after": "Maria Gonzales",
        "beforeDisplay": "Casey Lee",
        "afterDisplay": "Maria Gonzales"
      }
    ],
    "set": {
      "manager": "Maria Gonzales"
    },
    "unset": []
  },
  "policyNotes": [],
  "status": "success"
}
```

Key fields:

- `_id`: Unique audit entry identifier.
- `ts`: Timestamp (ISO string) when the audit event was recorded.
- `actor`: User who performed the action.
- `op`: Operation verb (e.g., `ADD`, `EDIT`, `REMOVE`).
- `diffId`: Identifier linking to the proposal diff that generated this entry.
- `groupId` / `groupName`: Target distribution list identifiers.
- `rule`: Object describing which rule was touched (type/label/value).
- `employeeRecord`: Present when the rule concerns employee record edits; includes the target user, a list of field-level `changes`, and `set`/`unset` payloads mirroring what was applied.
- `policyNotes`: Array of strings surfaced to explain policy context.
- `status`: Result string (`success`, `failed`, etc.).

---

*Add additional collection schemas below as they are shared.*

### `diffs`

Representative document:

```json
{
  "_id": "d_57c8a17ad8f24e33ba720186e8f89224",
  "action": "edit",
  "ruleType": "employee-record",
  "ruleLabel": "Employee Record",
  "groupId": "g_acl_evin_north",
  "groupName": "ACL_EVIN-North",
  "value": "alex.rivera@demo.local",
  "expression": null,
  "matches": [
    "u_alex"
  ],
  "matchCount": 1,
  "matchNames": [
    "Alex Rivera"
  ],
  "policyNotes": [],
  "createdAt": "2025-11-03T22:54:26.618352",
  "targetUserId": "u_alex",
  "targetUserEmail": "alex.rivera@demo.local",
  "targetUserName": "Alex Rivera",
  "recordChanges": {
    "set": {
      "manager": "Maria Gonzales"
    },
    "unset": []
  },
  "recordChangeFields": [
    {
      "field": "manager",
      "label": "Manager / Team Lead",
      "before": "Casey Lee",
      "after": "Maria Gonzales",
      "beforeDisplay": "Casey Lee",
      "afterDisplay": "Maria Gonzales"
    }
  ]
}
```

Key fields:

- `_id`: Diff/proposal identifier.
- `action`: High-level intent (`add`, `remove`, `edit`).
- `ruleType` / `ruleLabel`: Indicates which rule family the diff targets. For employee record changes this is `employee-record`.
- `groupId` / `groupName`: Target distribution list identifiers.
- `value`: Depending on rule type, the relevant value (user email for employee record diffs).
- `expression`: Populated for dynamic expressions; `null` for other rule types.
- `matches`, `matchCount`, `matchNames`: Cached lookup results representing which users the diff would affect.
- `policyNotes`: Array of guidance strings shown to operators.
- `createdAt`: ISO timestamp when the diff was created.
- `targetUser*`: Convenience fields for the selected employee (id/email/name).
- `recordChanges`: `set`/`unset` payload mirroring what will be applied.
- `recordChangeFields`: Human-readable before/after breakdown for each field to support previews/audits.

---

### `dl_actions`

Representative document:

```json
{
  "_id": "add",
  "description": "Add matching members to the group.",
  "label": "Add",
  "order": 1,
  "value": "add"
}
```

Key fields:

- `_id`: Stable identifier for the action (mirrors `value`).
- `value`: Action code used by the UI/API (`add`, `remove`, `edit`, etc.).
- `label`: Human-readable name shown in dropdowns.
- `description`: Short explanation surfaced in tooling/help text.
- `order`: Integer used to sort actions when listing them.

---

### `dl_groups`

Representative document:

```json
{
  "_id": "g_drill_permian",
  "value": "g_drill_permian",
  "label": "DRILL_Permian",
  "order": 2,
  "description": "Drilling supervisors in the Permian"
}
```

Key fields:

- `_id`: Unique identifier (matches `value`) for the group option.
- `value`: Canonical reference used in rules and API payloads.
- `label`: Friendly name shown in the UI.
- `order`: Sort order for the dropdown list.
- `description`: Optional blurb describing the group’s purpose or membership.

---

### `dl_rules`

Representative document:

```json
{
  "_id": "user",
  "label": "User",
  "order": 1,
  "recordFields": [],
  "staticValues": [],
  "value": "user",
  "valueSource": "employees"
}
```

Key fields:

- `_id`: Rule identifier (also stored in `value`).
- `label`: Display name for the rule type.
- `order`: Determines dropdown ordering.
- `valueSource`: Indicates how the value list is populated (`employees`, `static`, `expression`, `employee-record`, etc.).
- `staticValues`: Predefined options when `valueSource` is `static`.
- `recordFields`: Schema for employee-record drawer fields when `valueSource` is `employee-record`.

---

### `group_rule_events`

Representative document:

```json
{
  "_id": "evt_seed_demo",
  "groupId": "g_acl_evin_north",
  "ruleType": "employee-record",
  "action": "edit",
  "actor": {
    "id": "admin",
    "displayName": "admin"
  },
  "timestamp": {
    "$date": "2025-11-06T06:48:02.733Z"
  },
  "summary": {
    "label": "Jane Doe (6 fields)",
    "fieldCount": 6
  },
  "targets": {
    "userIds": [
      "u_jane"
    ],
    "entityId": "u_jane",
    "entityName": "Jane Doe",
    "matchedCount": 1
  },
  "details": {
    "employeeRecord": {
      "set": {
        "employmentType": "Contractor",
        "role": "IT Systems Analyst",
        "department": "Corporate IT",
        "location": "Houston HQ",
        "manager": "Casey Lee",
        "active": false
      },
      "unset": [],
      "fields": [
        {
          "name": "employmentType",
          "label": "Employment Type",
          "before": "Full-time",
          "after": "Contractor"
        },
        {
          "name": "active",
          "label": "Active Status",
          "before": true,
          "after": false
        }
      ]
    }
  },
  "diffId": "d_seed",
  "auditId": "a_seed"
}
```

Key fields:

- `_id`: Event identifier.
- `groupId`: Target distribution list.
- `ruleType` / `action`: Which rule was executed and how (add/remove/edit).
- `actor`: User metadata for who triggered the event.
- `timestamp`: BSON date (stored as ISO string when returned via API).
- `summary`: Human-readable label and counts for UI cards.
- `targets`: Lists the user IDs/entities affected, with match counts.
- `details.employeeRecord`: Nested payload summarizing `set`/`unset` changes and a `fields` array with before/after info (only present for employee record events; other rule types may have different structures).
- `diffId` / `auditId`: Links back to the originating diff and audit documents.

---

### `groups`

Representative document:

```json
{
  "_id": "g_acl_evin_north",
  "name": "ACL_EVIN-North",
  "businessUnit": "North",
  "description": "EVIN access for North asset team"
}
```

Key fields:

- `_id`: Unique group identifier (referenced by other collections).
- `name`: Display name for the distribution list.
- `businessUnit`: Optional organizational bucket.
- `description`: Free-form summary describing why the group exists.

---

### `memberships`

Representative document:

```json
{
  "_id": "m1",
  "groupId": "g_msg_prod_east",
  "userId": "u_temp",
  "addedAt": "2025-11-06T04:24:43.744043",
  "expiresAt": "2025-11-13T04:24:43.744043",
  "flag": "Include",
  "ruleType": "user",
  "ruleValue": "Sam Contractor"
}
```

Key fields:

- `_id`: Membership row identifier.
- `groupId`: Distribution list reference.
- `userId`: Employee identifier.
- `addedAt` / `expiresAt`: Timestamps for when the membership was created and when it should expire (nullable in other records).
- `flag`: Inclusion/exclusion flag (e.g., `Include`, `Exclude`).
- `ruleType` / `ruleValue`: Rule metadata indicating how the member was enrolled (user rule, manager rule, etc.).

---

### `users`

Representative document:

```json
{
  "_id": "u_erika",
  "displayName": "Erika Howard",
  "email": "erika.howard@demo.local",
  "department": "South Operations",
  "location": "Remote",
  "role": "Drilling Supervisor",
  "employmentType": "Full-time",
  "tags": [
    "Operations",
    "Leadership"
  ],
  "directoryGroups": [
    "DL_Permian_Operators"
  ],
  "manager": "Maria Gonzales",
  "tenureDays": 510,
  "active": true
}
```

Key fields:

- `_id`: Employee identifier used across the dataset.
- `displayName`, `email`: Primary identity fields.
- `department`, `location`, `role`, `employmentType`: Core metadata that powers rules/filters.
- `tags`: Arbitrary labels (array of strings).
- `directoryGroups`: External group memberships (array of strings).
- `manager`: Direct manager name.
- `tenureDays`: Numeric tenure value used by expression builder and employee-record fields.
- `active`: Boolean employment status.
