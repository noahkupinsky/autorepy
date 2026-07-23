from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from autorepy.repo_object import RepoObject, deep_ref, ref, type_ref
from autorepy.tags import ID_TAG


@dataclass
class Dog(RepoObject):
    breed: str


@dataclass
class Person(RepoObject):
    name: str
    dog: Dog | None = ref(default=None)


@dataclass
class Node(RepoObject):
    value: int
    next: Node | None = ref(default=None)


@dataclass
class Pair(RepoObject):
    left: RepoObject = ref()
    right: RepoObject = ref()


@dataclass
class Tree(RepoObject):
    children: list[Tree]
    data: int


@dataclass
class BinaryTree(RepoObject):
    left: BinaryTree | None = ref(default=None)
    right: BinaryTree | None = ref(default=None)
    data: int = 0


@dataclass
class SelfReferential(RepoObject):
    value: SelfReferential | None = ref(default=None)


@dataclass
class Cat(RepoObject):
    pass


@dataclass
class CatCafe(RepoObject):
    cat_map: dict[str, Cat] = deep_ref()
    cats: list[Cat] = deep_ref()


@dataclass(slots=True)
class SlottedObject(RepoObject):
    value: int


@dataclass
class CustomObject(RepoObject):
    value: int
    calls: ClassVar[int] = 0

    @classmethod
    def from_fields(cls, data: dict[str, Any]) -> CustomObject:
        cls.calls += 1
        return cls(id=data[ID_TAG], value=data["value"] * 2)


def migrate_cat_1_to_2(fields: dict[str, Any]) -> dict[str, Any]:
    fields["breed"] = fields.pop("breed_name")
    return fields


@dataclass
class MigratedCat(RepoObject):
    CURRENT_FORMAT_VERSION: ClassVar[int] = 2
    MIGRATIONS: ClassVar = {1: migrate_cat_1_to_2}
    breed: str
    
    
@dataclass
class ObjectWithTypeRef(RepoObject):
    type_ref: type[RepoObject] = type_ref()


REPO_OBJECT_TYPES = (
    RepoObject,
    Dog,
    (Person, "LegacyPerson"),
    Node,
    Pair,
    Tree,
    BinaryTree,
    SelfReferential,
    Cat,
    CatCafe,
    SlottedObject,
    CustomObject,
    (MigratedCat, "LegacyCat"),
    ObjectWithTypeRef
)
