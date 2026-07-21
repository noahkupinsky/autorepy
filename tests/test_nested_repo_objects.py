from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Callable

import pytest

from autorepy.dict_repo import DictRepo
from autorepy.registry import Registry
from autorepy.repo_object import RepoObject, ref, deep_ref
from autorepy.tags import ID_TAG, REF_TAG, TYPE_TAG


@dataclass
class Tree(RepoObject):
    children: list[Tree] # not a ref
    data: int
    
    
@pytest.fixture
def registry() -> Registry:
    return Registry(
        Tree,
    )
    

@pytest.fixture
def repo(registry: Registry) -> DictRepo:
    return DictRepo(registry)


@pytest.fixture
def clear_cache(repo: DictRepo) -> Callable[[], None]:
    def _clear_cache() -> None:
        repo.cache = {}
    return _clear_cache


def test_tree(repo: DictRepo, clear_cache):
    left = Tree(id="left", children=[], data=3)
    right = Tree(id="right", children=[], data=7)
    root = Tree(id="root", children=[left, right], data=5)
    
    expected_dict = {
        "$type": "Tree",
        "$id": "root",
        "data": 5,
        "children": [
            {
                "$type": "Tree",
                "$id": "left",
                "data": 3,
                "children": [],
            },
            {
                "$type": "Tree",
                "$id": "right",
                "data": 7,
                "children": [],
            },
        ]
    }
    
    assert root.to_dict() == expected_dict
    repo.save(root)
    clear_cache()
    loaded_root = repo.load(Tree.repo_type(), "root")
    assert isinstance(loaded_root, Tree)
    assert loaded_root.children[0].data == 3
    assert loaded_root.children[1].children == []
    
    