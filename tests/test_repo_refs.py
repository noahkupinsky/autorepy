from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Callable

import pytest

from autorepy.dict_repo import DictRepo
from autorepy.registry import Registry
from autorepy.repo_object import RepoObject, ref, deep_ref
from autorepy.tags import ID_TAG, REF_TAG, TYPE_TAG


@dataclass
class BinaryTree(RepoObject):
    left: BinaryTree | None = ref(default=None)
    right: BinaryTree | None = ref(default=None)
    data: int = 0
    
    
@dataclass
class Person(RepoObject):
    me: Person = ref(default=None)
    
    
@dataclass 
class Cat(RepoObject):
    pass

@dataclass
class CatCafe(RepoObject):
    cat_map: dict[str, Cat] = deep_ref()
    cats: list[Cat] = deep_ref()
    
    
@pytest.fixture
def registry() -> Registry:
    return Registry(
        Person,
        BinaryTree,
        Cat,
        CatCafe
    )

    
@pytest.fixture
def repo(registry: Registry) -> DictRepo:
    return DictRepo(registry)


@pytest.fixture
def clear_cache(repo: DictRepo) -> Callable[[], None]:
    def _clear_cache() -> None:
        repo.cache = {}
    return _clear_cache


def test_binary_tree_refs(repo: DictRepo, clear_cache):
    left = BinaryTree(id="left", data=3)
    right = BinaryTree(id="right", data=7)
    root = BinaryTree(id="root", data=5, left=left, right=right)
    # saving should not be recursive (left and right should remain unsaved)
    repo.save(root)
    # manually clear cache to force recursive load
    clear_cache()
    # loading should fail because we try to load left and right by ref
    with pytest.raises(KeyError):
        repo.load(BinaryTree.repo_type(), "root")
        
    # if we just save the left, we should still get an error
    repo.save(left)
    with pytest.raises(KeyError):
        repo.load(BinaryTree.repo_type(), "root")
        
    # if we save the right, we should be able to load the root
    repo.save(right)
    root = repo.load(BinaryTree.repo_type(), "root")
    assert isinstance(root, BinaryTree)
    assert root.left is left
    assert root.right is right
    
    
def test_reflexive_class(repo: DictRepo, clear_cache):
    myself = Person(id="me")
    myself.me = myself
    repo.save(myself)
    clear_cache()
    myself = repo.load(Person.repo_type(), "me")
    assert isinstance(myself, Person)
    assert myself.me is myself
    
    
def test_deep_refs(repo: DictRepo, clear_cache):
    steven = Cat(id="steven")
    mike = Cat(id="mike")
    tom = Cat(id="tom")
    cat_map = {"steven": steven, "mike": mike, "tom": tom}
    cats = [steven, mike, tom]
    cafe = CatCafe(id="cafe", cat_map=cat_map, cats=cats)
    
    
    steven_ref = steven.to_ref()
    cafe_repo_data = cafe.to_dict()
    assert cafe_repo_data["cat_map"]["steven"] == steven_ref
    
    for cat in cats:
        repo.save(cat)
    
    repo.save(cafe)
    clear_cache()
    
    loaded_cafe = repo.load(CatCafe.repo_type(), "cafe")
    loaded_steven = repo.load(Cat.repo_type(), "steven")
    assert isinstance(loaded_cafe, CatCafe)
    assert loaded_cafe.cat_map["steven"] is loaded_steven
    assert loaded_steven in loaded_cafe.cats
    
    