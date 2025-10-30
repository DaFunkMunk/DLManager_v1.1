from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Dict, List, Optional

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from .base import DirectoryAdapter


class DemoAdapter(DirectoryAdapter):
    """MongoDB-backed demo directory for portfolio-safe workflows."""

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

    # ------------------------------------------------------------------ helpers
    def _ensure_indexes(self) -> None:
        self._users.create_index("email", unique=True, sparse=True)
        self._users.create_index("displayName", name="idx_users_displayName")

        self._groups.create_index("name", unique=True)
        self._groups.create_index("businessUnit", name="idx_groups_businessUnit")

        self._memberships.create_index(
            [("userId", ASCENDING), ("groupId", ASCENDING)],
            unique=True,
            name="uidx_memberships_user_group",
        )
        self._memberships.create_index("groupId", name="idx_memberships_group")

        self._diffs.create_index([("createdAt", DESCENDING)], name="idx_diffs_createdAt")
        self._audit.create_index([("ts", DESCENDING)], name="idx_audit_ts")

    def seed_if_empty(self) -> None:
        if self._users.estimated_document_count() > 0:
            return

        now = dt.datetime.utcnow()
        users = [
            {
                "_id": "u_alex",
                "displayName": "Alex Rivera",
                "email": "alex.rivera@demo.local",
                "department": "Permian West",
                "active": True,
            },
            {
                "_id": "u_jane",
                "displayName": "Jane Doe",
                "email": "jane.doe@demo.local",
                "department": "North Operations",
                "active": True,
            },
            {
                "_id": "u_temp",
                "displayName": "Sam Contractor",
                "email": "sam.contractor@demo.local",
                "department": "East Projects",
                "active": True,
            },
            {
                "_id": "u_casey",
                "displayName": "Casey Lee",
                "email": "casey.lee@demo.local",
                "department": "Corporate IT",
                "active": True,
            },
            {
                "_id": "u_maria",
                "displayName": "Maria Gonzales",
                "email": "maria.gonzales@demo.local",
                "department": "HSE",
                "active": True,
            },
            {
                "_id": "u_devon",
                "displayName": "Devon Price",
                "email": "devon.price@demo.local",
                "department": "Permian West",
                "active": True,
            },
            {
                "_id": "u_erika",
                "displayName": "Erika Howard",
                "email": "erika.howard@demo.local",
                "department": "South Ops",
                "active": True,
            },
            {
                "_id": "u_frank",
                "displayName": "Frank Patel",
                "email": "frank.patel@demo.local",
                "department": "Drilling Analytics",
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
            },
            {
                "_id": "m2",
                "userId": "u_jane",
                "groupId": "g_acl_evin_north",
                "flag": "Include",
                "addedAt": now.isoformat(),
                "expiresAt": None,
            },
            {
                "_id": "m3",
                "userId": "u_alex",
                "groupId": "g_drill_permian",
                "flag": "Include",
                "addedAt": now.isoformat(),
                "expiresAt": None,
            },
        ]

        self._users.insert_many(users)
        self._groups.insert_many(groups)
        try:
            self._memberships.insert_many(memberships, ordered=False)
        except DuplicateKeyError:
            # If parallel seeding attempts run, ignore duplicate inserts.
            pass

    @staticmethod
    def _policy_notes(changes: List[Dict[str, Any]]) -> List[str]:
        notes: List[str] = []
        for change in changes:
            if change.get("op") == "ADD" and not change.get("expiresAt"):
                notes.append("Tip: add an expiration date for contractors.")
        return notes

    @staticmethod
    def _normalize_membership(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not doc:
            return None
        return {
            "id": str(doc.get("_id")),
            "userId": doc.get("userId"),
            "groupId": doc.get("groupId"),
            "flag": doc.get("flag"),
            "addedAt": doc.get("addedAt"),
            "expiresAt": doc.get("expiresAt"),
        }

    # ------------------------------------------------------------------- public
    def list_users(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        criteria: Dict[str, Any] = {}
        if query:
            regex = {"$regex": query, "$options": "i"}
            criteria = {"$or": [{"displayName": regex}, {"email": regex}, {"department": regex}]}

        cursor = self._users.find(criteria).sort("displayName", ASCENDING)
        users: List[Dict[str, Any]] = []
        for doc in cursor:
            users.append(
                {
                    "id": str(doc.get("_id")),
                    "displayName": doc.get("displayName"),
                    "email": doc.get("email"),
                    "department": doc.get("department"),
                    "active": bool(doc.get("active", True)),
                }
            )
        return users

    def list_groups(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        criteria: Dict[str, Any] = {}
        if query:
            regex = {"$regex": query, "$options": "i"}
            criteria = {"$or": [{"name": regex}, {"businessUnit": regex}]}

        cursor = self._groups.find(criteria).sort("name", ASCENDING)
        groups: List[Dict[str, Any]] = []
        for doc in cursor:
            groups.append(
                {
                    "id": str(doc.get("_id")),
                    "name": doc.get("name"),
                    "businessUnit": doc.get("businessUnit"),
                    "description": doc.get("description"),
                }
            )
        return groups

    def propose(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        if not intent:
            return {"error": "Intent body is required."}

        action = (intent.get("action") or "").strip().lower()
        if action not in {"add", "remove"}:
            return {"error": "Intent requires action 'add' or 'remove'."}

        user_ref = (intent.get("user") or "").strip()
        group_ref = (intent.get("group") or "").strip()
        expires_at = intent.get("expiresAt")

        if not user_ref or not group_ref:
            return {"error": "Intent must include user and group references."}

        user_doc = self._users.find_one(
            {"$or": [{"_id": user_ref}, {"displayName": user_ref}, {"email": user_ref}]}
        )
        if not user_doc:
            return {"error": f"User '{user_ref}' not found."}

        group_doc = self._groups.find_one(
            {"$or": [{"_id": group_ref}, {"name": group_ref}]}
        )
        if not group_doc:
            return {"error": f"Group '{group_ref}' not found."}

        change = {
            "op": action.upper(),
            "userId": str(user_doc["_id"]),
            "userDisplayName": user_doc.get("displayName"),
            "groupId": str(group_doc["_id"]),
            "groupName": group_doc.get("name"),
            "expiresAt": expires_at,
        }

        diff_id = f"d_{uuid.uuid4().hex}"
        payload = [change]
        self._diffs.insert_one(
            {
                "_id": diff_id,
                "payload": payload,
                "createdAt": dt.datetime.utcnow().isoformat(),
            }
        )

        return {
            "id": diff_id,
            "changes": payload,
            "policyNotes": self._policy_notes(payload),
        }

    def apply(self, diff_id: str, actor: str) -> Dict[str, Any]:
        if not diff_id:
            return {"error": "diffId is required."}

        diff_doc = self._diffs.find_one({"_id": diff_id})
        if not diff_doc:
            return {"error": "Diff not found."}

        changes: List[Dict[str, Any]] = diff_doc.get("payload", [])
        before_payload: List[Dict[str, Any]] = []
        after_payload: List[Dict[str, Any]] = []

        for change in changes:
            op = change.get("op")
            user_id = change.get("userId")
            group_id = change.get("groupId")
            expires_at = change.get("expiresAt")

            if not user_id or not group_id:
                continue

            membership_filter = {"userId": user_id, "groupId": group_id}
            existing = self._memberships.find_one(membership_filter)
            normalized_existing = self._normalize_membership(existing)
            if normalized_existing:
                before_payload.append(normalized_existing)

            if op == "ADD":
                membership_doc = {
                    "_id": existing.get("_id") if existing else f"m_{uuid.uuid4().hex}",
                    "userId": user_id,
                    "groupId": group_id,
                    "flag": change.get("flag", "Include"),
                    "addedAt": existing.get("addedAt") if existing else dt.datetime.utcnow().isoformat(),
                    "expiresAt": expires_at,
                }
                self._memberships.replace_one(
                    membership_filter,
                    membership_doc,
                    upsert=True,
                )
                after_payload.append(self._normalize_membership(membership_doc))
            elif op == "REMOVE":
                if existing:
                    self._memberships.delete_one(membership_filter)
                    after_payload.append({"userId": user_id, "groupId": group_id, "removed": True})
            else:
                continue

        audit_id = f"a_{uuid.uuid4().hex}"
        audit_doc = {
            "_id": audit_id,
            "ts": dt.datetime.utcnow().isoformat(),
            "actor": actor,
            "op": "APPLY",
            "diffId": diff_id,
            "beforePayload": before_payload,
            "afterPayload": after_payload,
            "status": "success",
        }
        self._audit.insert_one(audit_doc)

        return {"ok": True, "auditId": audit_id}

    def audit(self, limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self._audit.find().sort("ts", DESCENDING).limit(limit)
        entries: List[Dict[str, Any]] = []
        for doc in cursor:
            entries.append(
                {
                    "id": str(doc.get("_id")),
                    "ts": doc.get("ts"),
                    "actor": doc.get("actor"),
                    "op": doc.get("op"),
                    "diffId": doc.get("diffId"),
                    "status": doc.get("status"),
                }
            )
        return entries
