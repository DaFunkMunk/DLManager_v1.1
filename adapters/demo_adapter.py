from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Dict, List, Optional, Callable, Iterable

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, OperationFailure

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

        self._ensure_indexes()
        if seed:
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
        ]

        for collection, keys, options in index_specs:
            try:
                collection.create_index(keys, **options)
            except OperationFailure as exc:
                if exc.code == 85:  # IndexOptionsConflict
                    continue
                raise

    def seed_if_empty(self) -> None:
        if self._users.estimated_document_count() > 0:
            return

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

        self._users.insert_many(users)
        self._groups.insert_many(groups)
        try:
            self._memberships.insert_many(memberships, ordered=False)
        except DuplicateKeyError:
            pass

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
    def apply(self, diff_id: str, actor: str) -> Dict[str, Any]:
        diff = self._diffs.find_one({"_id": diff_id})
        if not diff:
            return {"error": "Diff not found."}

        action = diff.get("action")
        rule_type = diff.get("ruleType")
        value = diff.get("value")
        expression = diff.get("expression")
        matches_ids: List[str] = diff.get("matches", [])

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

            if existing and existing.get("_id"):
                membership_doc["_id"] = existing["_id"]
            else:
                membership_doc["_id"] = f"m_{uuid.uuid4().hex}"
                membership_doc["addedAt"] = dt.datetime.utcnow().isoformat()

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
            }
            for doc in cursor
        ]

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
        }
