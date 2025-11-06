from __future__ import annotations

import datetime as dt
import uuid
from copy import deepcopy
import os
from typing import Any, Dict, List, Optional, Callable, Iterable

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.errors import OperationFailure

from .base import DirectoryAdapter


class DemoAdapter(DirectoryAdapter):
    """MongoDB-backed demo directory for portfolio-safe workflows."""

    ALLOWED_ACTIONS = {"add", "remove", "edit"}

    RULE_LABELS: Dict[str, str] = {
        "user": "User",
        "tree": "Org Unit",
        "location": "Location",
        "role": "Role / Job Title",
        "employment-type": "Employment Type",
        "tag": "Tag / Attribute",
        "directory-group": "Directory Group",
        "tenure-window": "Tenure Window",
        "manager": "Manager / Team Lead",
        "saved-filter": "Saved Filter",
        "expression": "Dynamic Expression",
        "employee-record": "Employee Record",
    }

    STATIC_VALUE_FIELDS: Dict[str, List[str]] = {
        "tree": ["Permian Operations", "Corporate IT", "HSE Response", "Analytics Guild"],
        "location": ["Permian Field Office", "Midland Regional HQ", "Houston HQ", "Remote"],
        "role": [
            "Operations Manager",
            "Production Engineer",
            "Pipeline Coordinator",
            "Contract Technician",
            "HSE Specialist",
            "Drilling Supervisor",
            "IT Systems Analyst",
            "Data Scientist",
        ],
        "employment-type": ["Full-time", "Contractor", "Intern"],
        "tag": ["Operations", "Responder", "HSE", "AI", "Analytics", "Leadership"],
        "directory-group": [
            "DL_Permian_Operators",
            "DL_Permian_Engineers",
            "DL_HSE_Responders",
            "DL_Corporate_IT",
            "DL_Data_Analytics",
        ],
        "tenure-window": ["0-90", "91-180", "181-365", "365+"],
        "manager": ["Casey Lee", "Alex Rivera", "Maria Gonzales", "Erika Howard"],
        "saved-filter": ["HSE Responders", "Permian Engineers", "Contractors Ending Soon"],
    }

    EXPRESSION_ALLOWED_FIELDS = {
        "employmentType",
        "location",
        "role",
        "department",
        "tags",
        "directoryGroups",
        "manager",
        "tenureDays",
        "orgUnit",
        "active",
    }

    SAVED_FILTERS: Dict[str, Callable[[Dict[str, Any]], bool]] = {
        "HSE Responders": lambda doc: "HSE" in doc.get("tags", []),
        "Permian Engineers": lambda doc: doc.get("department") == "Permian Operations" and "Engineer" in (doc.get("role") or ""),
        "Contractors Ending Soon": lambda doc: doc.get("employmentType") == "Contractor" and doc.get("tenureDays", 0) <= 30,
    }

    EMPLOYEE_RECORD_FIELDS: List[Dict[str, Any]] = [
        {
            "name": "employmentType",
            "label": "Employment Type",
            "type": "select",
            "options": [{"value": value, "label": value} for value in STATIC_VALUE_FIELDS["employment-type"]],
        },
        {
            "name": "role",
            "label": "Role / Job Title",
            "type": "select",
            "options": [{"value": value, "label": value} for value in STATIC_VALUE_FIELDS["role"]],
        },
        {
            "name": "department",
            "label": "Department",
            "type": "select",
            "options": [{"value": value, "label": value} for value in [
                "Permian Operations",
                "Corporate IT",
                "HSE",
                "South Operations",
                "East Projects",
                "Analytics Guild",
            ]],
        },
        {
            "name": "location",
            "label": "Location",
            "type": "select",
            "options": [{"value": value, "label": value} for value in STATIC_VALUE_FIELDS["location"]],
        },
        {
            "name": "manager",
            "label": "Manager / Team Lead",
            "type": "select",
            "options": [{"value": value, "label": value} for value in STATIC_VALUE_FIELDS["manager"]],
        },
        {
            "name": "tenureDays",
            "label": "Tenure (days)",
            "type": "number",
            "options": [],
        },
        {
            "name": "active",
            "label": "Active Status",
            "type": "boolean",
            "options": [
                {"value": True, "label": "Active"},
                {"value": False, "label": "Inactive"},
            ],
        },
    ]

    def __init__(
        self,
        mongo_uri: str,
        db_name: str = "dl_demo",
        seed: bool = True,
    ) -> None:
        if not mongo_uri:
            raise ValueError("mongo_uri is required for DemoAdapter.")

        self._client = MongoClient(mongo_uri, appname="DLWebAppDemo")
        self._db = self._client[db_name]

        self._users: Collection = self._db["users"]
        self._groups: Collection = self._db["groups"]
        self._memberships: Collection = self._db["memberships"]
        self._diffs: Collection = self._db["diffs"]
        self._audit: Collection = self._db["audit"]
        self._rule_events: Collection = self._db["group_rule_events"]
        self._option_actions: Collection = self._db["dl_actions"]
        self._option_groups: Collection = self._db["dl_groups"]
        self._option_rules: Collection = self._db["dl_rules"]
        self._employee_record_field_map: Dict[str, Dict[str, Any]] = {
            field["name"]: field for field in self.EMPLOYEE_RECORD_FIELDS
        }

        self._ensure_indexes()
        auto_seed = os.getenv("DEMO_AUTO_SEED", "true").lower() in {"1", "true", "yes", "on"}
        if seed and auto_seed:
            self.seed_if_empty()

    def _ensure_indexes(self) -> None:
        index_specs = [
            (self._users, [("displayName", ASCENDING)], {"name": "idx_users_displayName"}),
            (self._users, [("email", ASCENDING)], {"unique": True, "name": "idx_users_email"}),
            (self._users, [("department", ASCENDING)], {"name": "idx_users_department"}),
            (self._users, [("location", ASCENDING)], {"name": "idx_users_location"}),
            (self._users, [("role", ASCENDING)], {"name": "idx_users_role"}),
            (self._users, [("employmentType", ASCENDING)], {"name": "idx_users_employmentType"}),
            (self._users, [("tags", ASCENDING)], {"name": "idx_users_tags"}),
            (self._users, [("directoryGroups", ASCENDING)], {"name": "idx_users_directoryGroups"}),
            (self._users, [("manager", ASCENDING)], {"name": "idx_users_manager"}),
            (self._groups, [("name", ASCENDING)], {"unique": True, "name": "idx_groups_name"}),
            (self._groups, [("businessUnit", ASCENDING)], {"name": "idx_groups_businessUnit"}),
            (self._memberships, [("userId", ASCENDING), ("groupId", ASCENDING)], {"unique": True, "name": "idx_memberships_user_group"}),
            (self._memberships, [("groupId", ASCENDING)], {"name": "idx_memberships_group"}),
            (self._diffs, [("createdAt", DESCENDING)], {"name": "idx_diffs_createdAt"}),
            (self._audit, [("ts", DESCENDING)], {"name": "idx_audit_ts"}),
            (self._option_actions, [("order", ASCENDING)], {"name": "idx_actions_order"}),
            (self._option_groups, [("order", ASCENDING)], {"name": "idx_dl_groups_order"}),
            (self._option_rules, [("order", ASCENDING)], {"name": "idx_rules_order"}),
            (self._rule_events, [("groupId", ASCENDING), ("timestamp", DESCENDING)], {"name": "idx_events_group_ts"}),
            (self._rule_events, [("groupId", ASCENDING), ("ruleType", ASCENDING), ("timestamp", DESCENDING)], {"name": "idx_events_group_rule_ts"}),
        ]

        for collection, keys, options in index_specs:
            try:
                collection.create_index(keys, **options)
            except OperationFailure as exc:
                if exc.code == 85:  # IndexOptionsConflict
                    continue
                raise

    def seed_if_empty(self, force: bool = False) -> None:
        if force:
            for collection in (
                self._users,
                self._groups,
                self._memberships,
                self._diffs,
                self._audit,
                self._option_actions,
                self._option_groups,
                self._option_rules,
                self._rule_events,
            ):
                collection.delete_many({})

        now = dt.datetime.utcnow()
        users = [
            {
                "_id": "u_alex",
                "displayName": "Alex Rivera",
                "email": "alex.rivera@demo.local",
                "department": "Permian Operations",
                "location": "Permian Field Office",
                "role": "Operations Manager",
                "employmentType": "Full-time",
                "tags": ["Operations", "Leadership"],
                "directoryGroups": ["DL_Permian_Operators", "DL_Leadership"],
                "manager": "Casey Lee",
                "tenureDays": 820,
                "active": True,
            },
            {
                "_id": "u_jane",
                "displayName": "Jane Doe",
                "email": "jane.doe@demo.local",
                "department": "Permian Operations",
                "location": "Midland Regional HQ",
                "role": "Production Engineer",
                "employmentType": "Full-time",
                "tags": ["Operations", "Responder"],
                "directoryGroups": ["DL_Permian_Engineers", "DL_Permian_Operators"],
                "manager": "Alex Rivera",
                "tenureDays": 420,
                "active": True,
            },
            {
                "_id": "u_temp",
                "displayName": "Sam Contractor",
                "email": "sam.contractor@demo.local",
                "department": "East Projects",
                "location": "Permian Field Office",
                "role": "Contract Technician",
                "employmentType": "Contractor",
                "tags": ["Operations"],
                "directoryGroups": ["DL_Permian_Engineers"],
                "manager": "Alex Rivera",
                "tenureDays": 18,
                "active": True,
            },
            {
                "_id": "u_casey",
                "displayName": "Casey Lee",
                "email": "casey.lee@demo.local",
                "department": "Corporate IT",
                "location": "Houston HQ",
                "role": "IT Systems Analyst",
                "employmentType": "Full-time",
                "tags": ["Leadership", "AI"],
                "directoryGroups": ["DL_Corporate_IT", "DL_Data_Analytics"],
                "manager": "Maria Gonzales",
                "tenureDays": 960,
                "active": True,
            },
            {
                "_id": "u_maria",
                "displayName": "Maria Gonzales",
                "email": "maria.gonzales@demo.local",
                "department": "HSE",
                "location": "Houston HQ",
                "role": "HSE Specialist",
                "employmentType": "Full-time",
                "tags": ["HSE", "Responder"],
                "directoryGroups": ["DL_HSE_Responders"],
                "manager": "Casey Lee",
                "tenureDays": 640,
                "active": True,
            },
            {
                "_id": "u_devon",
                "displayName": "Devon Price",
                "email": "devon.price@demo.local",
                "department": "Permian Operations",
                "location": "Permian Field Office",
                "role": "Pipeline Coordinator",
                "employmentType": "Full-time",
                "tags": ["Operations"],
                "directoryGroups": ["DL_Permian_Operators"],
                "manager": "Alex Rivera",
                "tenureDays": 210,
                "active": True,
            },
            {
                "_id": "u_erika",
                "displayName": "Erika Howard",
                "email": "erika.howard@demo.local",
                "department": "South Operations",
                "location": "Remote",
                "role": "Drilling Supervisor",
                "employmentType": "Full-time",
                "tags": ["Operations", "Leadership"],
                "directoryGroups": ["DL_Permian_Operators"],
                "manager": "Maria Gonzales",
                "tenureDays": 510,
                "active": True,
            },
            {
                "_id": "u_frank",
                "displayName": "Frank Patel",
                "email": "frank.patel@demo.local",
                "department": "Analytics Guild",
                "location": "Houston HQ",
                "role": "Data Scientist",
                "employmentType": "Full-time",
                "tags": ["Analytics", "AI"],
                "directoryGroups": ["DL_Data_Analytics", "DL_Corporate_IT"],
                "manager": "Casey Lee",
                "tenureDays": 120,
                "active": True,
            },
        ]

        groups = [
            {
                "_id": "g_acl_evin_north",
                "name": "ACL_EVIN-North",
                "businessUnit": "North",
                "description": "EVIN access for North asset team",
            },
            {
                "_id": "g_msg_prod_east",
                "name": "MSG_Production_East",
                "businessUnit": "East",
                "description": "Production messaging channel for East region",
            },
            {
                "_id": "g_drill_permian",
                "name": "DRILL_Permian",
                "businessUnit": "Permian",
                "description": "Drilling supervisors in the Permian",
            },
            {
                "_id": "g_hse_incident",
                "name": "HSE_Incident_Response",
                "businessUnit": "HSE",
                "description": "Rapid responders for HSE incidents",
            },
            {
                "_id": "g_corp_it",
                "name": "Corporate_IT",
                "businessUnit": "Corporate",
                "description": "Corporate IT administrators",
            },
        ]

        one_week = now + dt.timedelta(days=7)

        memberships = [
            {
                "_id": "m1",
                "userId": "u_temp",
                "groupId": "g_msg_prod_east",
                "flag": "Include",
                "addedAt": now.isoformat(),
                "expiresAt": one_week.isoformat(),
                "ruleType": "user",
                "ruleValue": "Sam Contractor",
            },
            {
                "_id": "m2",
                "userId": "u_jane",
                "groupId": "g_acl_evin_north",
                "flag": "Include",
                "addedAt": now.isoformat(),
                "expiresAt": None,
                "ruleType": "user",
                "ruleValue": "Jane Doe",
            },
            {
                "_id": "m3",
                "userId": "u_alex",
                "groupId": "g_drill_permian",
                "flag": "Include",
                "addedAt": now.isoformat(),
                "expiresAt": None,
                "ruleType": "tree",
                "ruleValue": "Permian Operations",
            },
        ]

        needs_users = force or self._users.estimated_document_count() == 0
        needs_groups = force or self._groups.estimated_document_count() == 0
        needs_group_options = force or self._option_groups.estimated_document_count() == 0

        if needs_users:
            self._users.insert_many(users)
        else:
            for doc in users:
                self._users.update_one({"_id": doc["_id"]}, {"$set": doc}, upsert=True)

        if needs_groups:
            self._groups.insert_many(groups)
        else:
            for group in groups:
                self._groups.update_one({"_id": group["_id"]}, {"$set": group}, upsert=True)

        for membership in memberships:
            membership.setdefault("flag", "Include")
            membership_filter = {"userId": membership["userId"], "groupId": membership["groupId"]}
            membership_payload = membership.copy()
            membership_id = membership_payload.pop("_id", None)
            update_doc: Dict[str, Any] = {"$set": membership_payload}
            if membership_id:
                update_doc.setdefault("$setOnInsert", {})["_id"] = membership_id
            self._memberships.update_one(membership_filter, update_doc, upsert=True)

        action_options = [
            {"_id": "add", "value": "add", "label": "Add", "order": 1, "description": "Add matching members to the group."},
            {"_id": "remove", "value": "remove", "label": "Remove", "order": 2, "description": "Remove matching members from the group."},
            {"_id": "edit", "value": "edit", "label": "Edit", "order": 3, "description": "Adjust a dynamic membership rule."},
        ]
        for option in action_options:
            self._option_actions.update_one({"_id": option["_id"]}, {"$set": option}, upsert=True)

        group_options = [
            {
                "_id": group["_id"],
                "value": group["_id"],
                "label": group["name"],
                "order": index,
                "description": group.get("description"),
            }
            for index, group in enumerate(groups)
        ]
        if needs_group_options:
            self._option_groups.insert_many(group_options)
        else:
            for option in group_options:
                self._option_groups.update_one({"_id": option["_id"]}, {"$set": option}, upsert=True)

        def as_options(values: Iterable[str]) -> List[Dict[str, str]]:
            return [{"value": value, "label": value} for value in values]

        saved_filter_values = as_options(self.SAVED_FILTERS.keys())

        rule_options_seed = [
            {"_id": "user", "label": "User", "order": 1, "valueSource": "employees"},
            {"_id": "tree", "label": "Org Unit", "order": 2, "valueSource": "static", "staticValues": as_options(["Permian Operations", "Corporate IT", "HSE Response", "Analytics Guild"])},
            {"_id": "location", "label": "Location", "order": 3, "valueSource": "static", "staticValues": as_options(["Permian Field Office", "Midland Regional HQ", "Houston HQ", "Remote"])},
            {"_id": "role", "label": "Role / Job Title", "order": 4, "valueSource": "static", "staticValues": as_options(["Operations Manager", "Production Engineer", "Pipeline Coordinator", "Contract Technician", "HSE Specialist", "Drilling Supervisor", "IT Systems Analyst", "Data Scientist"])},
            {"_id": "employment-type", "label": "Employment Type", "order": 5, "valueSource": "static", "staticValues": as_options(["Full-time", "Contractor", "Intern"])},
            {"_id": "tag", "label": "Tag / Attribute", "order": 6, "valueSource": "static", "staticValues": as_options(["Responder", "Operations", "HSE", "AI", "Analytics", "Leadership"])},
            {"_id": "directory-group", "label": "Directory Group", "order": 7, "valueSource": "static", "staticValues": as_options(["DL_Permian_Operators", "DL_Permian_Engineers", "DL_HSE_Responders", "DL_Corporate_IT", "DL_Data_Analytics"])},
            {"_id": "tenure-window", "label": "Tenure Window", "order": 8, "valueSource": "static", "staticValues": as_options(["0-90", "91-180", "181-365", "365+"])},
            {"_id": "manager", "label": "Manager / Team Lead", "order": 9, "valueSource": "static", "staticValues": as_options(["Casey Lee", "Alex Rivera", "Maria Gonzales", "Erika Howard"])},
            {"_id": "saved-filter", "label": "Saved Filter", "order": 10, "valueSource": "static", "staticValues": saved_filter_values},
            {"_id": "expression", "label": "Dynamic Expression", "order": 11, "valueSource": "expression"},
            {"_id": "employee-record", "label": "Employee Record", "order": 12, "valueSource": "employee-record", "recordFields": deepcopy(self.EMPLOYEE_RECORD_FIELDS)},
        ]

        for option in rule_options_seed:
            option.setdefault("value", option["_id"])
            option.setdefault("staticValues", [])
            option.setdefault("recordFields", [])
            self._option_rules.update_one({"_id": option["_id"]}, {"$set": option}, upsert=True)

    def _propose_employee_record(
        self,
        action: str,
        group_doc: Dict[str, Any],
        employee_ref: str,
        intent: Dict[str, Any],
    ) -> Dict[str, Any]:
        employee_ref = employee_ref.strip()
        if not employee_ref:
            return {"error": "Select an employee record to modify."}

        record_changes = intent.get("recordChanges") or {}
        set_fields = record_changes.get("set") or {}
        unset_fields = record_changes.get("unset") or []

        normalized_set: Dict[str, Any] = {}
        change_fields: List[Dict[str, Any]] = []

        # Normalize set fields
        for field_name, raw_value in set_fields.items():
            if field_name in normalized_set:
                continue
            try:
                normalized_value = self._normalize_employee_field_value(field_name, raw_value)
            except ValueError as exc:
                return {"error": str(exc)}
            normalized_set[field_name] = normalized_value

        # Remove duplicates where a field is both set and unset
        normalized_unset = []
        for field_name in unset_fields:
            if field_name in normalized_set or field_name in normalized_unset:
                continue
            normalized_unset.append(field_name)

        if action == "remove" and not normalized_unset:
            return {"error": "Choose at least one field to clear."}
        if action in {"add", "edit"} and not normalized_set:
            return {"error": "Provide at least one field to update."}

        user_doc = self._users.find_one(
            {"$or": [{"_id": employee_ref}, {"email": employee_ref}, {"displayName": employee_ref}]}
        )
        if not user_doc:
            return {"error": "Employee record not found."}

        for field_name, new_value in normalized_set.items():
            before_value = user_doc.get(field_name)
            if before_value == new_value:
                # Avoid presenting no-op changes
                continue
            change_fields.append(
                {
                    "field": field_name,
                    "label": self._employee_field_label(field_name),
                    "before": before_value,
                    "after": new_value,
                    "beforeDisplay": self._format_employee_field_value(field_name, before_value),
                    "afterDisplay": self._format_employee_field_value(field_name, new_value),
                }
            )

        for field_name in normalized_unset:
            before_value = user_doc.get(field_name)
            change_fields.append(
                {
                    "field": field_name,
                    "label": self._employee_field_label(field_name),
                    "before": before_value,
                    "after": None,
                    "beforeDisplay": self._format_employee_field_value(field_name, before_value),
                    "afterDisplay": "(cleared)",
                }
            )

        if not change_fields:
            return {"error": "No changes detected for the selected employee."}

        diff_id = f"d_{uuid.uuid4().hex}"
        diff_payload = {
            "_id": diff_id,
            "action": action,
            "ruleType": "employee-record",
            "ruleLabel": self.RULE_LABELS.get("employee-record", "Employee Record"),
            "groupId": group_doc.get("_id"),
            "groupName": group_doc.get("name"),
            "value": employee_ref,
            "expression": None,
            "matches": [user_doc.get("_id")],
            "matchCount": len(change_fields),
            "matchNames": [user_doc.get("displayName")],
            "policyNotes": [],
            "createdAt": dt.datetime.utcnow().isoformat(),
            "targetUserId": user_doc.get("_id"),
            "targetUserEmail": user_doc.get("email"),
            "targetUserName": user_doc.get("displayName"),
            "recordChanges": {
                "set": normalized_set,
                "unset": normalized_unset,
            },
            "recordChangeFields": change_fields,
        }
        self._diffs.insert_one(diff_payload)

        change_entry = {
            "changeType": "employee-record",
            "action": action.upper(),
            "userId": user_doc.get("_id"),
            "userDisplayName": user_doc.get("displayName"),
            "userEmail": user_doc.get("email"),
            "ruleLabel": diff_payload["ruleLabel"],
            "ruleType": "employee-record",
            "ruleValueLabel": user_doc.get("displayName"),
            "fields": change_fields,
        }

        return {
            "id": diff_id,
            "groupId": diff_payload["groupId"],
            "groupName": diff_payload["groupName"],
            "action": action,
            "ruleType": "employee-record",
            "ruleLabel": diff_payload["ruleLabel"],
            "matchCount": len(change_fields),
            "changes": [change_entry],
            "policyNotes": [],
            "ruleValue": user_doc.get("displayName"),
            "recordChanges": diff_payload["recordChanges"],
        }

    def _apply_employee_record(self, diff: Dict[str, Any], actor: str) -> Dict[str, Any]:
        target_ref = diff.get("targetUserId") or diff.get("targetUserEmail") or diff.get("value")
        if not target_ref:
            return {"error": "Employee reference missing from diff."}

        user_doc = self._users.find_one(
            {"$or": [{"_id": target_ref}, {"email": target_ref}, {"displayName": target_ref}]}
        )
        if not user_doc:
            return {"error": "Employee record not found."}

        record_changes = diff.get("recordChanges") or {}
        group_doc = self._groups.find_one({"_id": diff.get("groupId")}) or {"_id": diff.get("groupId"), "name": diff.get("groupName")}
        raw_set = record_changes.get("set") or {}
        raw_unset = record_changes.get("unset") or []

        normalized_set: Dict[str, Any] = {}
        for field_name, raw_value in raw_set.items():
            try:
                normalized_set[field_name] = self._normalize_employee_field_value(field_name, raw_value)
            except ValueError as exc:
                return {"error": str(exc)}

        normalized_unset = [field for field in raw_unset if field not in normalized_set]

        update_doc: Dict[str, Any] = {}
        if normalized_set:
            update_doc["$set"] = normalized_set
        if normalized_unset:
            update_doc.setdefault("$unset", {})
            for field in normalized_unset:
                update_doc["$unset"][field] = ""

        before_snapshot = {field: user_doc.get(field) for field in set(normalized_set.keys()) | set(normalized_unset)}

        if update_doc:
            self._users.update_one({"_id": user_doc.get("_id")}, update_doc)

        updated_user = self._users.find_one({"_id": user_doc.get("_id")}) or user_doc
        after_snapshot = {field: updated_user.get(field) for field in before_snapshot.keys()}

        change_fields: List[Dict[str, Any]] = []
        for field_name in before_snapshot.keys():
            change_fields.append(
                {
                    "field": field_name,
                    "label": self._employee_field_label(field_name),
                    "before": before_snapshot[field_name],
                    "after": after_snapshot.get(field_name),
                    "beforeDisplay": self._format_employee_field_value(field_name, before_snapshot[field_name]),
                    "afterDisplay": self._format_employee_field_value(field_name, after_snapshot.get(field_name)),
                }
            )

        audit_doc = {
            "_id": f"a_{uuid.uuid4().hex}",
            "ts": dt.datetime.utcnow().isoformat(),
            "actor": actor,
            "op": diff.get("action", "").upper(),
            "diffId": diff.get("_id"),
            "groupId": diff.get("groupId"),
            "groupName": diff.get("groupName"),
            "rule": {
                "type": "employee-record",
                "label": self.RULE_LABELS.get("employee-record", "Employee Record"),
                "value": updated_user.get("displayName"),
            },
            "employeeRecord": {
                "userId": updated_user.get("_id"),
                "userDisplayName": updated_user.get("displayName"),
                "userEmail": updated_user.get("email"),
                "changes": change_fields,
                "set": normalized_set,
                "unset": normalized_unset,
            },
            "policyNotes": diff.get("policyNotes", []),
            "status": "success",
        }
        self._audit.insert_one(audit_doc)

        field_count = len(change_fields)
        summary_payload = {
            "label": f"{updated_user.get('displayName')} ({field_count} field{'s' if field_count != 1 else ''})",
            "fieldCount": field_count,
            "statusLabel": "Updated",
        }
        targets_payload = {
            "userIds": [updated_user.get("_id")],
            "entityId": updated_user.get("_id"),
            "entityName": updated_user.get("displayName"),
            "matchedCount": 1,
        }
        details_payload = {
            "employeeRecord": {
                "set": normalized_set,
                "unset": normalized_unset,
                "fields": change_fields,
            }
        }
        self._log_rule_event(
            group_doc,
            diff.get("action", "edit"),
            "employee-record",
            actor,
            summary=summary_payload,
            targets=targets_payload,
            details=details_payload,
            diff_id=diff.get("_id"),
            audit_id=audit_doc["_id"],
        )

        empty_summary = {"count": 0, "names": [], "rules": []}
        result_summary = {
            "groupId": diff.get("groupId"),
            "groupName": diff.get("groupName"),
            "rule": {
                "type": "employee-record",
                "label": self.RULE_LABELS.get("employee-record", "Employee Record"),
                "value": updated_user.get("displayName"),
            },
            "recordChange": {
                "userId": updated_user.get("_id"),
                "userDisplayName": updated_user.get("displayName"),
                "userEmail": updated_user.get("email"),
                "fields": change_fields,
            },
            "added": empty_summary,
            "removed": empty_summary,
            "before": {},
            "after": {},
            "policyNotes": diff.get("policyNotes", []),
        }

        return {
            "ok": True,
            "auditId": audit_doc["_id"],
            "applied": len(change_fields),
            "removed": 0,
            "summary": result_summary,
        }

    def list_demo_actions(self) -> List[Dict[str, Any]]:
        cursor = self._option_actions.find().sort("order", ASCENDING)
        actions: List[Dict[str, Any]] = []
        for doc in cursor:
            actions.append(
                {
                    "value": doc.get("value") or doc.get("_id"),
                    "label": doc.get("label") or doc.get("_id"),
                    "description": doc.get("description"),
                }
            )
        return actions

    def list_demo_groups(self) -> List[Dict[str, Any]]:
        cursor = self._option_groups.find().sort("order", ASCENDING)
        groups: List[Dict[str, Any]] = []
        for doc in cursor:
            groups.append(
                {
                    "value": doc.get("value") or doc.get("_id"),
                    "label": doc.get("label") or doc.get("_id"),
                    "description": doc.get("description"),
                    "groupId": doc.get("value") or doc.get("_id"),
                }
            )
        return groups

    def list_demo_rules(self) -> List[Dict[str, Any]]:
        cursor = self._option_rules.find().sort("order", ASCENDING)
        rules: List[Dict[str, Any]] = []
        for doc in cursor:
            rules.append(
                {
                    "value": doc.get("value") or doc.get("_id"),
                    "label": doc.get("label") or doc.get("_id"),
                    "valueSource": doc.get("valueSource") or "static",
                    "staticValues": doc.get("staticValues", []),
                    "recordFields": doc.get("recordFields", []),
                }
            )
        return rules

    def list_users(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        criteria: Dict[str, Any] = {}
        if query:
            regex = {"$regex": query, "$options": "i"}
            criteria = {"$or": [{"displayName": regex}, {"email": regex}, {"department": regex}]}

        projection = {
            "displayName": 1,
            "email": 1,
            "department": 1,
            "location": 1,
            "role": 1,
            "employmentType": 1,
            "manager": 1,
            "tags": 1,
            "directoryGroups": 1,
            "tenureDays": 1,
            "orgUnit": 1,
        }

        cursor = self._users.find(criteria, projection).sort("displayName", ASCENDING)
        return [
            {
                "id": str(doc.get("_id")),
                "name": doc.get("displayName"),
                "email": doc.get("email"),
                "department": doc.get("department"),
                "location": doc.get("location"),
                "role": doc.get("role"),
                "employmentType": doc.get("employmentType"),
                "manager": doc.get("manager"),
                "tags": doc.get("tags", []),
                "directoryGroups": doc.get("directoryGroups", []),
                "tenureDays": doc.get("tenureDays", 0),
                "orgUnit": doc.get("orgUnit"),
            }
            for doc in cursor
        ]

    def list_groups(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        criteria: Dict[str, Any] = {}
        if query:
            regex = {"$regex": query, "$options": "i"}
            criteria = {"$or": [{"name": regex}, {"businessUnit": regex}]}

        cursor = self._groups.find(criteria).sort("name", ASCENDING)
        return [
            {
                "id": str(doc.get("_id")),
                "name": doc.get("name"),
                "businessUnit": doc.get("businessUnit"),
                "description": doc.get("description"),
            }
            for doc in cursor
        ]

    # region expression helpers
    def _expression_context(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "employmentType": doc.get("employmentType"),
            "location": doc.get("location"),
            "role": doc.get("role"),
            "department": doc.get("department"),
            "tags": doc.get("tags", []),
            "directoryGroups": doc.get("directoryGroups", []),
            "manager": doc.get("manager"),
            "tenureDays": doc.get("tenureDays", 0),
            "orgUnit": doc.get("orgUnit"),
            "active": bool(doc.get("active", True)),
        }

    def _compile_expression(self, expression: str) -> Any:
        import ast

        if not expression:
            raise ValueError("Expression is empty.")

        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ValueError(f"Invalid expression syntax: {exc.msg}") from exc

        allowed_nodes = (
            ast.Expression,
            ast.BoolOp,
            ast.UnaryOp,
            ast.BinOp,
            ast.Compare,
            ast.Name,
            ast.Load,
            ast.Constant,
            ast.List,
            ast.Tuple,
            ast.Call,
            ast.And,
            ast.Or,
            ast.Not,
            ast.Eq,
            ast.NotEq,
            ast.Gt,
            ast.GtE,
            ast.Lt,
            ast.LtE,
            ast.In,
            ast.NotIn,
            ast.NameConstant,
        )

        allowed_funcs = {"contains"}

        class Validator(ast.NodeVisitor):
            def visit(self, node):  # type: ignore[override]
                if not isinstance(node, allowed_nodes):
                    raise ValueError("Unsupported expression construct: " + node.__class__.__name__)
                return super().visit(node)

            def visit_Name(self, node: ast.Name):
                if node.id not in DemoAdapter.EXPRESSION_ALLOWED_FIELDS:
                    raise ValueError(f"Unknown field '{node.id}' in expression.")

            def visit_Call(self, node: ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id not in allowed_funcs:
                    raise ValueError("Unsupported function call in expression.")
                if len(node.args) != 2:
                    raise ValueError("contains() expects two arguments.")
                for arg in node.args:
                    self.visit(arg)

        Validator().visit(tree)
        code = compile(tree, "<expression>", "eval")
        return code

    def _evaluate_expression(self, compiled: Any, doc: Dict[str, Any]) -> bool:
        context = self._expression_context(doc)
        safe_globals = {"__builtins__": {}, "contains": lambda collection, value: value in (collection or [])}
        try:
            result = eval(compiled, safe_globals, context)
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"Failed to evaluate expression: {exc}") from exc
        if not isinstance(result, bool):
            raise ValueError("Expression must evaluate to a boolean value.")
        return result

    # endregion

    def validate_expression(self, expression: str) -> Dict[str, Any]:
        compiled = self._compile_expression(expression)
        matches = [doc for doc in self._users.find({}, projection={}) if self._evaluate_expression(compiled, doc)]
        return {
            "ok": True,
            "matches": len(matches),
            "sample": [doc.get("displayName") for doc in matches[:5]],
        }

    def _match_users(
        self,
        rule_type: str,
        value: Optional[str] = None,
        expression: Optional[str] = None,
        compiled_expression: Any = None,
    ) -> List[Dict[str, Any]]:
        rule_type = rule_type.lower()

        if rule_type == "user":
            if not value:
                raise ValueError("User value is required.")
            doc = self._users.find_one(
                {"$or": [{"displayName": value}, {"email": value}]}
            )
            return [doc] if doc else []

        if rule_type == "tree":
            query = {"$or": [{"orgUnit": value}, {"department": value}]}
            return list(self._users.find(query))

        if rule_type == "location":
            return list(self._users.find({"location": value}))

        if rule_type == "role":
            return list(self._users.find({"role": value}))

        if rule_type == "employment-type":
            return list(self._users.find({"employmentType": value}))

        if rule_type == "tag":
            return list(self._users.find({"tags": value}))

        if rule_type == "directory-group":
            return list(self._users.find({"directoryGroups": value}))

        if rule_type == "tenure-window":
            if not value:
                raise ValueError("Tenure window value required.")
            if value.endswith('+'):
                min_days = int(value[:-1])
                return list(self._users.find({"tenureDays": {"$gte": min_days}}))
            try:
                lower, upper = value.split('-')
                lower_days = int(lower)
                upper_days = int(upper)
            except ValueError as exc:
                raise ValueError("Invalid tenure window format.") from exc
            return list(self._users.find({"tenureDays": {"$gte": lower_days, "$lte": upper_days}}))

        if rule_type == "manager":
            return list(self._users.find({"manager": value}))

        if rule_type == "saved-filter":
            predicate = self.SAVED_FILTERS.get(value)
            if not predicate:
                return []
            return [doc for doc in self._users.find({}) if predicate(doc)]

        if rule_type == "expression":
            if not expression:
                raise ValueError("Expression is required.")
            compiled = compiled_expression or self._compile_expression(expression)
            return [doc for doc in self._users.find({}) if self._evaluate_expression(compiled, doc)]

        raise ValueError(f"Unknown rule type '{rule_type}'.")

    def _employee_field_meta(self, field_name: str) -> Dict[str, Any]:
        return self._employee_record_field_map.get(field_name, {})

    def _employee_field_label(self, field_name: str) -> str:
        meta = self._employee_field_meta(field_name)
        return meta.get("label") or field_name.replace("_", " ").title()

    def _normalize_employee_field_value(self, field_name: str, value: Any) -> Any:
        meta = self._employee_field_meta(field_name)
        field_type = (meta.get("type") or "text").lower()
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if field_type == "number":
            try:
                return int(value)
            except (ValueError, TypeError):
                raise ValueError(f"'{self._employee_field_label(field_name)}' must be a number.")
        if field_type == "boolean":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"true", "1", "yes", "on"}
            if isinstance(value, (int, float)):
                return bool(value)
            return False
        return value

    def _format_employee_field_value(self, field_name: str, value: Any) -> str:
        meta = self._employee_field_meta(field_name)
        if value in (None, "", []):
            return "(empty)"
        options = meta.get("options") or []
        for option in options:
            if option.get("value") == value:
                return option.get("label") or str(value)
        if isinstance(value, bool):
            return "Active" if value else "Inactive"
        return str(value)

    def _log_rule_event(
        self,
        group_doc: Dict[str, Any],
        action: str,
        rule_type: str,
        actor: str,
        *,
        summary: Optional[Dict[str, Any]] = None,
        targets: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
        diff_id: Optional[str] = None,
        audit_id: Optional[str] = None,
    ) -> None:
        event_doc = {
            "_id": f"evt_{uuid.uuid4().hex}",
            "groupId": group_doc.get("_id"),
            "groupName": group_doc.get("name"),
            "ruleType": rule_type,
            "action": action,
            "actor": {
                "id": actor,
                "displayName": actor,
            },
            "timestamp": dt.datetime.utcnow(),
            "summary": summary or {},
            "targets": targets or {},
            "details": details or {},
            "diffId": diff_id,
            "auditId": audit_id,
        }
        try:
            self._rule_events.insert_one(event_doc)
        except Exception:
            # Event logging is best-effort; never block main workflow.
            pass

    @staticmethod
    def _preview_change(
        action: str,
        rule_type: str,
        rule_value: Optional[str],
        expression: Optional[str],
        user_doc: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "action": action.upper(),
            "ruleType": rule_type,
            "ruleLabel": DemoAdapter.RULE_LABELS.get(rule_type, rule_type),
            "ruleValue": rule_value,
            "ruleValueLabel": expression if rule_type == "expression" else (rule_value or ""),
            "expression": expression,
            "userId": user_doc.get("_id"),
            "userDisplayName": user_doc.get("displayName"),
            "userEmail": user_doc.get("email"),
        }

    def _policy_notes(
        self,
        action: str,
        rule_type: str,
        matches: List[Dict[str, Any]],
        expression: Optional[str],
    ) -> List[str]:
        notes: List[str] = []
        if action == "edit":
            notes.append("Edit will upsert matching memberships in demo mode.")
        if rule_type == "expression" and expression:
            notes.append("Dynamic expressions evaluate against live demo attributes.")
        if not matches:
            notes.append("No users matched this rule.")
        elif len(matches) > 25:
            notes.append("Large change detected - confirm with a stakeholder before applying.")
        return notes

    def propose(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        if not intent:
            return {"error": "Intent body is required."}

        action = (intent.get("action") or "").strip().lower()
        if action not in self.ALLOWED_ACTIONS:
            return {"error": "Unsupported action supplied."}

        rule_type = (intent.get("ruleType") or "user").strip().lower()
        if rule_type not in self.RULE_LABELS:
            return {"error": "Unsupported rule type supplied."}

        group_ref = (intent.get("group") or "").strip()
        if not group_ref:
            return {"error": "Group is required."}

        group_doc = self._groups.find_one({"$or": [{"_id": group_ref}, {"name": group_ref}]})
        if not group_doc:
            return {"error": "Group not found."}

        value = (intent.get("value") or "").strip()
        expression = (intent.get("expression") or "").strip()

        if rule_type == "employee-record":
            return self._propose_employee_record(action, group_doc, value, intent)

        compiled_expression = None
        if rule_type == "expression":
            try:
                compiled_expression = self._compile_expression(expression)
            except ValueError as exc:
                return {"error": str(exc)}

        try:
            matches = self._match_users(
                rule_type,
                value=value,
                expression=expression,
                compiled_expression=compiled_expression,
            )
        except ValueError as exc:
            return {"error": str(exc)}

        policy_notes = self._policy_notes(action, rule_type, matches, expression)
        match_names = [
            doc.get("displayName")
            for doc in matches
            if doc.get("displayName")
        ]

        changes = [
            self._preview_change(
                action,
                rule_type,
                value if rule_type != "expression" else None,
                expression if rule_type == "expression" else None,
                doc,
            )
            for doc in matches
        ]

        diff_id = f"d_{uuid.uuid4().hex}"
        diff_payload = {
            "_id": diff_id,
            "action": action,
            "ruleType": rule_type,
            "ruleLabel": self.RULE_LABELS.get(rule_type, rule_type),
            "groupId": group_doc.get("_id"),
            "groupName": group_doc.get("name"),
            "value": value if rule_type != "expression" else None,
            "expression": expression if rule_type == "expression" else None,
            "matches": [doc.get("_id") for doc in matches],
            "matchCount": len(matches),
            "matchNames": match_names,
            "policyNotes": policy_notes,
            "createdAt": dt.datetime.utcnow().isoformat(),
        }
        self._diffs.insert_one(diff_payload)

        return {
            "id": diff_id,
            "groupId": diff_payload["groupId"],
            "groupName": diff_payload["groupName"],
            "action": action,
            "ruleType": rule_type,
            "matchCount": len(matches),
            "changes": changes,
            "policyNotes": policy_notes,
            "ruleLabel": self.RULE_LABELS.get(rule_type, rule_type),
            "ruleValue": value if rule_type != "expression" else expression,
        }

    def _user_name_map(self, user_ids: Iterable[str]) -> Dict[str, str]:
        unique_ids = {uid for uid in user_ids if uid}
        if not unique_ids:
            return {}
        cursor = self._users.find({"_id": {"$in": list(unique_ids)}}, {"displayName": 1})
        return {doc["_id"]: doc.get("displayName") for doc in cursor}

    def _summarize_memberships(
        self,
        entries: List[Dict[str, Any]],
        names_map: Dict[str, str],
        tally: str = "generic",
    ) -> Dict[str, Any]:
        if not entries:
            return {"count": 0, "names": [], "rules": []}

        names: List[str] = []
        for entry in entries:
            name = names_map.get(entry.get("userId"))
            if name and name not in names:
                names.append(name)

        rules: List[str] = []
        seen_rules: set = set()
        for entry in entries:
            rule_type = entry.get("ruleType") or ""
            rule_value = entry.get("ruleValue") or ""
            label = self.RULE_LABELS.get(rule_type, rule_type)
            rule_str = f"{label}: {rule_value}" if rule_value else label
            if rule_str not in seen_rules:
                seen_rules.add(rule_str)
                rules.append(rule_str)

        return {
            "count": len(entries),
            "names": names[:5],
            "rules": rules[:3],
            "tally": tally,
        }
    def group_memberships(self, group_ref: str) -> List[Dict[str, Any]]:
        query = {"$or": [{"_id": group_ref}, {"name": group_ref}]}
        group_doc = self._groups.find_one(query)
        if not group_doc:
            return []

        memberships = list(self._memberships.find({"groupId": group_doc["_id"]}).sort("updatedAt", DESCENDING))
        user_ids = [m.get("userId") for m in memberships if m.get("userId")]
        names_map = self._user_name_map(user_ids) if user_ids else {}

        rows: List[Dict[str, Any]] = []
        for entry in memberships:
            rule_type = (entry.get("ruleType") or "user").lower()
            rule_label = self.RULE_LABELS.get(rule_type, rule_type)
            value = entry.get("ruleValue")
            value_label = value or "(none)"

            if rule_type == "user":
                value_label = names_map.get(entry.get("userId")) or value or entry.get("userId")
            elif rule_type == "expression":
                value_label = value or "(expression)"

            flag_value = entry.get("flag") or "Include"
            status_label = "Included" if isinstance(flag_value, str) and flag_value.lower() == "include" else flag_value

            rows.append({
                "statusLabel": status_label,
                "ruleType": rule_type,
                "ruleLabel": rule_label,
                "value": value,
                "valueLabel": value_label,
                "userDisplayName": names_map.get(entry.get("userId")),
                "userId": entry.get("userId"),
                "updatedAt": entry.get("updatedAt"),
            })

        events_cursor = self._rule_events.find(
            {"groupId": group_doc["_id"]},
            sort=[("timestamp", DESCENDING)],
            limit=50,
        )
        for event in events_cursor:
            event_rule_type = (event.get("ruleType") or "").lower()
            summary = event.get("summary") or {}
            targets = event.get("targets") or {}
            details = event.get("details") or {}

            label = summary.get("label") or targets.get("entityName") or "Recent update"
            if event_rule_type == "employee-record" and not summary.get("label"):
                field_count = len(details.get("employeeRecord", {}).get("fields", []))
                user_name = targets.get("entityName") or targets.get("entityId") or "(employee)"
                label = f"{user_name} ({field_count} field{'s' if field_count != 1 else ''})" if field_count else user_name

            timestamp = event.get("timestamp")
            if isinstance(timestamp, dt.datetime):
                timestamp = timestamp.isoformat()

            rows.append({
                "statusLabel": summary.get("statusLabel") or "Updated",
                "ruleType": event_rule_type or "employee-record",
                "ruleLabel": self.RULE_LABELS.get(event_rule_type, event.get("ruleType", "Employee Record")),
                "value": targets.get("entityId"),
                "valueLabel": label,
                "userDisplayName": targets.get("entityName"),
                "userId": targets.get("entityId"),
                "updatedAt": timestamp,
                "isRecentRecordEvent": True,
                "badgeClass": summary.get("badgeClass") or "group-status__tag--updated",
                "rowClasses": summary.get("rowClasses") or ["group-status__row--recent"],
                "suppressUserValue": True,
                "eventId": event.get("_id"),
            })

        return rows

    def apply(self, diff_id: str, actor: str) -> Dict[str, Any]:
        diff = self._diffs.find_one({"_id": diff_id})
        if not diff:
            return {"error": "Diff not found."}

        action = diff.get("action")
        rule_type = diff.get("ruleType")
        value = diff.get("value")
        expression = diff.get("expression")
        matches_ids: List[str] = diff.get("matches", [])

        if rule_type == "employee-record":
            return self._apply_employee_record(diff, actor)

        if rule_type == "expression" and expression:
            compiled = self._compile_expression(expression)
            matches_docs = self._match_users("expression", expression=expression, compiled_expression=compiled)
        elif rule_type == "user" and value:
            matches_docs = self._match_users("user", value=value)
        else:
            matches_docs = list(self._users.find({"_id": {"$in": matches_ids}})) if matches_ids else []
            if not matches_docs and rule_type:
                matches_docs = self._match_users(rule_type, value=value)

        before_payload: List[Dict[str, Any]] = []
        after_payload: List[Dict[str, Any]] = []

        for doc in matches_docs:
            membership_filter = {"userId": doc.get("_id"), "groupId": diff.get("groupId")}
            existing = self._memberships.find_one(membership_filter)

            if existing:
                before_payload.append(self._normalize_membership(existing))

            if action == "remove":
                if existing:
                    self._memberships.delete_one({"_id": existing["_id"]})
                continue

            membership_doc = {
                "userId": doc.get("_id"),
                "groupId": diff.get("groupId"),
                "ruleType": rule_type,
                "ruleValue": value if rule_type != "expression" else expression,
                "updatedAt": dt.datetime.utcnow().isoformat(),
            }

            if existing and existing.get("addedAt"):
                membership_doc["addedAt"] = existing.get("addedAt")

            if existing and existing.get("_id"):
                membership_doc["_id"] = existing["_id"]
            else:
                membership_doc["_id"] = f"m_{uuid.uuid4().hex}"
                membership_doc["addedAt"] = dt.datetime.utcnow().isoformat()

            flag_value = (existing.get("flag") if existing else None) or "Include"
            membership_doc["flag"] = flag_value

            self._memberships.replace_one({"_id": membership_doc["_id"]}, membership_doc, upsert=True)
            after_payload.append(self._normalize_membership(membership_doc))

        user_ids = [entry.get("userId") for entry in before_payload + after_payload if entry.get("userId")]
        names_map = self._user_name_map(user_ids)

        summary_before = self._summarize_memberships(before_payload, names_map)
        summary_after = self._summarize_memberships(after_payload, names_map)
        summary_added = self._summarize_memberships(
            [entry for entry in after_payload if entry.get("addedAt")],
            names_map,
            tally="added",
        )
        summary_removed = self._summarize_memberships(
            [entry for entry in before_payload if entry not in after_payload],
            names_map,
            tally="removed",
        )

        policy_notes = diff.get("policyNotes", [])
        match_count = diff.get("matchCount", (summary_added.get("count", 0) or summary_after.get("count", 0)))
        match_names = diff.get("matchNames") or summary_added.get("names", []) or summary_after.get("names", [])
        rule_label = diff.get("ruleLabel") or self.RULE_LABELS.get(rule_type, rule_type)
        rule_value_display = expression if rule_type == "expression" else value

        audit_doc = {
            "_id": f"a_{uuid.uuid4().hex}",
            "ts": dt.datetime.utcnow().isoformat(),
            "actor": actor,
            "op": action.upper(),
            "diffId": diff_id,
            "groupId": diff.get("groupId"),
            "groupName": diff.get("groupName"),
            "rule": {
                "type": rule_type,
                "label": rule_label,
                "value": rule_value_display,
                "expression": expression if rule_type == "expression" else None,
            },
            "before": before_payload,
            "after": after_payload,
            "summary": {
                "before": summary_before,
                "after": summary_after,
                "added": summary_added,
                "removed": summary_removed,
            },
            "matchCount": match_count,
            "matchNames": (match_names[:5] if match_names else []),
            "policyNotes": policy_notes,
            "status": "success",
        }
        self._audit.insert_one(audit_doc)

        result_summary = {
            "groupId": diff.get("groupId"),
            "groupName": diff.get("groupName"),
            "rule": {
                "type": rule_type,
                "label": rule_label,
                "value": rule_value_display,
                "expression": expression if rule_type == "expression" else None,
            },
            "added": summary_added,
            "removed": summary_removed,
            "before": summary_before,
            "after": summary_after,
            "policyNotes": policy_notes,
        }

        return {
            "ok": True,
            "auditId": audit_doc["_id"],
            "applied": summary_added.get("count", 0),
            "removed": summary_removed.get("count", 0),
            "summary": result_summary,
        }

    def audit(self, limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self._audit.find().sort("ts", DESCENDING).limit(limit)
        return [
            {
                "id": doc.get("_id"),
                "ts": doc.get("ts"),
                "actor": doc.get("actor"),
                "op": doc.get("op"),
                "status": doc.get("status"),
                "diffId": doc.get("diffId"),
                "groupId": doc.get("groupId"),
                "groupName": doc.get("groupName"),
                "rule": doc.get("rule", {}),
                "summary": doc.get("summary", {}),
                "matchCount": doc.get("matchCount"),
                "matchNames": doc.get("matchNames", []),
                "policyNotes": doc.get("policyNotes", []),
                "before": doc.get("before", []),
                "after": doc.get("after", []),
                "employeeRecord": doc.get("employeeRecord", {}),
            }
            for doc in cursor
        ]

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _normalize_membership(doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": doc.get("_id"),
            "userId": doc.get("userId"),
            "groupId": doc.get("groupId"),
            "ruleType": doc.get("ruleType"),
            "ruleValue": doc.get("ruleValue"),
            "addedAt": doc.get("addedAt"),
            "updatedAt": doc.get("updatedAt"),
            "flag": doc.get("flag"),
        }

