from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

import pyodbc

from .base import DirectoryAdapter


class StandardAdapter(DirectoryAdapter):
    """Wraps the existing SQL Server logic so the API surface matches the demo adapter."""

    def __init__(self, conn_str: str) -> None:
        self._conn_str = conn_str

    def _connect(self) -> pyodbc.Connection:
        return pyodbc.connect(self._conn_str)

    def list_users(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        params: List[Any] = []
        like_clause = ""

        def _execute(sql: str, arguments: List[Any]) -> List[Any]:
            cursor.execute(sql, arguments)
            return cursor.fetchall()

        try:
            sql = (
                "SELECT EmployeeID, EmployeeName, EmailAddress "
                "FROM dbo.Employee_List"
            )
            if query:
                like_clause = " WHERE EmployeeName LIKE ? OR EmployeeID LIKE ? OR EmailAddress LIKE ?"
                like = f"%{query}%"
                params = [like, like, like]
                sql += like_clause
            rows = _execute(sql, params)
            email_supported = True
        except pyodbc.ProgrammingError:
            # Fall back for environments where EmailAddress/Department/Active columns are absent.
            sql = "SELECT EmployeeID, EmployeeName FROM dbo.Employee_List"
            if query:
                like_clause = " WHERE EmployeeName LIKE ? OR EmployeeID LIKE ?"
                like = f"%{query}%"
                params = [like, like]
                sql += like_clause
            rows = _execute(sql, params)
            email_supported = False
        finally:
            conn.close()

        results: List[Dict[str, Any]] = []
        for row in rows:
            display_name = getattr(row, "EmployeeName", None) or row[1]
            employee_id = getattr(row, "EmployeeID", None) or row[0]
            email = None
            if email_supported:
                email = getattr(row, "EmailAddress", None)
            results.append(
                {
                    "id": str(employee_id),
                    "displayName": display_name,
                    "email": email,
                }
            )
        return results

    def list_groups(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._connect()
        cursor = conn.cursor()
        params: List[Any] = []
        sql = "SELECT DLID, DL_NAME, BUSINESS_UNIT FROM dbo.DL_Header"
        fallback_sql = "SELECT DLID, DL_NAME FROM dbo.DL_Header"
        if query:
            like = f"%{query}%"
            sql += " WHERE DL_NAME LIKE ? OR BUSINESS_UNIT LIKE ?"
            fallback_sql += " WHERE DL_NAME LIKE ?"
            params = [like, like]
            fallback_params = [like]
        else:
            fallback_params = []

        try:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            has_business_unit = True
        except pyodbc.ProgrammingError:
            cursor.execute(fallback_sql, fallback_params)
            rows = cursor.fetchall()
            has_business_unit = False
        finally:
            conn.close()

        groups: List[Dict[str, Any]] = []
        for row in rows:
            groups.append(
                {
                    "id": str(getattr(row, "DLID", None) or row[0]),
                    "name": getattr(row, "DL_NAME", None) or row[1],
                    "businessUnit": getattr(row, "BUSINESS_UNIT", None) if has_business_unit else None,
                }
            )
        return groups

    def propose(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        # Standard mode continues to use the legacy workflow; surface a friendly message.
        return {
            "error": "Propose/apply workflow is only available in Demo mode.",
        }

    def apply(self, diff_id: str, actor: str) -> Dict[str, Any]:
        return {
            "error": "Propose/apply workflow is only available in Demo mode.",
        }

    def group_memberships(self, group_ref: str) -> List[Dict[str, Any]]:
        raise NotImplementedError("Group membership lookup is not available for the standard adapter.")

    def audit(self, limit: int = 100) -> List[Dict[str, Any]]:
        # There is no unified audit store in Standard mode yet.
        return []
    def validate_expression(self, expression: str) -> Dict[str, Any]:
        raise NotImplementedError("Expression validation is not supported in standard mode.")

