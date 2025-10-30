from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class DirectoryAdapter(Protocol):
    """Common contract for directory backends used by the DL Manager demo/standard modes."""

    def list_users(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        ...

    def list_groups(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        ...

    def propose(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def apply(self, diff_id: str, actor: str) -> Dict[str, Any]:
        ...

    def audit(self, limit: int = 100) -> List[Dict[str, Any]]:
        ...

    def validate_expression(self, expression: str) -> Dict[str, Any]:
        ...
