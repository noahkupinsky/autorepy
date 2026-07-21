from __future__ import annotations
from autorepy.repo import Repo
from autorepy.registry import Registry
from typing import Any

class DictRepo(Repo):
    data: dict[tuple[str, str], dict[str, Any]]
    
    def __init__(self, registry: Registry) -> None:
        super().__init__(registry)
        self.data = {}
        
    def _get_all_ids_for_type_name(self, type: str) -> list[str]:
        return [id for (t, id) in self.data if t == type]
    
    def _has_in_repo(self, type: str, id: str) -> bool:
        return (type, id) in self.data
        
    def _put_in_repo(self, type: str, id: str, data: dict) -> None:
        self.data[(type, id)] = data
        
    def _get_from_repo(self, type: str, id: str) -> dict:
        return self.data[(type, id)]
    
    def _delete_from_repo(self, type: str, id: str) -> None:
        del self.data[(type, id)]