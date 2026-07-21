from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import pytest

from autorepy.dict_repo import DictRepo
from autorepy.registry import Registry
from autorepy.repo_object import RepoObject, ref
from autorepy.tags import ID_TAG, REF_TAG, TYPE_TAG


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


@dataclass(slots=True)
class SlottedObject(RepoObject):
    value: int


@dataclass
class CustomObject(RepoObject):
    value: int
    calls: ClassVar[int] = 0

    @classmethod
    def from_repo_data(cls, data: dict[str, Any]) -> CustomObject:
        cls.calls += 1
        return cls(id=data[ID_TAG], value=data["value"] * 2)


@pytest.fixture
def registry() -> Registry:
    return Registry(
        RepoObject,
        Dog,
        (Person, "LegacyPerson"),
        Node,
        Pair,
        SlottedObject,
        CustomObject,
    )


@pytest.fixture
def repo(registry: Registry) -> DictRepo:
    return DictRepo(registry)


def raw(type_name: str, object_id: str, **values: Any) -> dict[str, Any]:
    return {TYPE_TAG: type_name, ID_TAG: object_id, **values}


def reference(type_name: str, object_id: str) -> dict[str, Any]:
    return {REF_TAG: {TYPE_TAG: type_name, ID_TAG: object_id}}


def put(repo: DictRepo, data: dict[str, Any]) -> None:
    repo._put_in_repo(data[TYPE_TAG], data[ID_TAG], data)


class TestConstructionAndStorage:
    def test_constructor_initializes_state(self, registry: Registry) -> None:
        repo = DictRepo(registry)
        assert repo.registry is registry
        assert repo.cache == {}
        assert repo.data == {}

    def test_instances_do_not_share_state(self, registry: Registry) -> None:
        first, second = DictRepo(registry), DictRepo(registry)
        first.save(Dog(id="fido", breed="corgi"))
        assert first.data and first.cache
        assert second.data == {} and second.cache == {}

    def test_storage_primitives_use_tuple_keys(self, repo: DictRepo) -> None:
        data = raw("Dog", "fido", breed="corgi")
        repo._put_in_repo("Dog", "fido", data)
        assert repo._get_from_repo("Dog", "fido") is data
        repo._delete_from_repo("Dog", "fido")
        assert ("Dog", "fido") not in repo.data

    def test_get_missing_key_raises_key_error(self, repo: DictRepo) -> None:
        with pytest.raises(KeyError):
            repo._get_from_repo("Dog", "missing")


class TestSaveLoadDelete:
    def test_save_serializes_and_caches_exact_object(self, repo: DictRepo) -> None:
        dog = Dog(id="fido", breed="corgi")
        repo.save(dog)
        assert repo.data[("Dog", "fido")] == raw("Dog", "fido", breed="corgi")
        assert repo.cache[("Dog", "fido")] is dog

    def test_save_overwrites_storage_and_cache(self, repo: DictRepo) -> None:
        repo.save(Dog(id="fido", breed="corgi"))
        new = Dog(id="fido", breed="beagle")
        repo.save(new)
        assert repo.data[("Dog", "fido")]["breed"] == "beagle"
        assert repo.cache[("Dog", "fido")] is new

    def test_load_constructs_registered_class(self, repo: DictRepo) -> None:
        put(repo, raw("Dog", "fido", breed="corgi"))
        loaded = repo.load("Dog", "fido")
        assert isinstance(loaded, Dog)
        assert loaded == Dog(id="fido", breed="corgi")

    def test_load_reuses_cached_instance(self, repo: DictRepo) -> None:
        put(repo, raw("Dog", "fido", breed="corgi"))
        assert repo.load("Dog", "fido") is repo.load("Dog", "fido")

    def test_cache_hit_does_not_require_storage(self, repo: DictRepo) -> None:
        dog = Dog(id="fido", breed="corgi")
        repo.cache[("Dog", "fido")] = dog
        assert repo.load("Dog", "fido") is dog

    def test_delete_removes_storage_and_cache(self, repo: DictRepo) -> None:
        repo.save(Dog(id="fido", breed="corgi"))
        repo.delete("Dog", "fido")
        assert ("Dog", "fido") not in repo.data
        assert ("Dog", "fido") not in repo.cache

    def test_delete_uncached_object(self, repo: DictRepo) -> None:
        put(repo, raw("Dog", "fido", breed="corgi"))
        repo.delete("Dog", "fido")
        assert ("Dog", "fido") not in repo.data

    def test_unknown_type_does_not_pollute_cache(self, repo: DictRepo) -> None:
        with pytest.raises(KeyError):
            repo.load("Unknown", "1")
        assert ("Unknown", "1") not in repo.cache

    def test_missing_object_does_not_pollute_cache(self, repo: DictRepo) -> None:
        with pytest.raises(KeyError):
            repo.load("Dog", "missing")
        assert ("Dog", "missing") not in repo.cache

    def test_alias_loads_old_type_as_current_class(self, repo: DictRepo) -> None:
        put(repo, raw("LegacyPerson", "alice", name="Alice", dog=None))
        loaded = repo.load("LegacyPerson", "alice")
        assert isinstance(loaded, Person)
        assert loaded == Person(id="alice", name="Alice")

    def test_custom_deserializer_is_used(self, repo: DictRepo) -> None:
        CustomObject.calls = 0
        put(repo, raw("CustomObject", "custom", value=4))
        loaded = repo.load("CustomObject", "custom")
        assert isinstance(loaded, CustomObject)
        assert loaded.value == 8 and CustomObject.calls == 1

    def test_slotted_dataclass_loads(self, repo: DictRepo) -> None:
        put(repo, raw("SlottedObject", "slot", value=7))
        assert repo.load("SlottedObject", "slot") == SlottedObject("slot", 7)

    def test_failed_deserialization_removes_placeholder(self, repo: DictRepo) -> None:
        put(repo, raw("Dog", "broken"))
        with pytest.raises(ValueError):
            repo.load("Dog", "broken")
        assert ("Dog", "broken") not in repo.cache


class TestReferenceResolution:
    def test_direct_reference_becomes_repo_object(self, repo: DictRepo) -> None:
        put(repo, raw("Dog", "fido", breed="corgi"))
        put(repo, raw("Person", "alice", name="Alice", dog=reference("Dog", "fido")))
        person = repo.load("Person", "alice")
        assert isinstance(person, Person)
        assert person.dog == Dog(id="fido", breed="corgi")

    def test_nested_dict_and_list_references(self, repo: DictRepo) -> None:
        put(repo, raw("Dog", "fido", breed="corgi"))
        resolved = repo.resolve_refs({"outer": [{"dog": reference("Dog", "fido")}, reference("Dog", "fido")]})
        dog = resolved["outer"][0]["dog"]
        assert isinstance(dog, Dog)
        assert resolved["outer"][1] is dog

    def test_repeated_reference_preserves_identity(self, repo: DictRepo) -> None:
        put(repo, raw("Dog", "fido", breed="corgi"))
        put(repo, raw("Pair", "pair", left=reference("Dog", "fido"), right=reference("Dog", "fido")))
        pair = repo.load("Pair", "pair")
        assert isinstance(pair, Pair)
        assert pair.left is pair.right

    def test_self_reference_preserves_identity(self, repo: DictRepo) -> None:
        put(repo, raw("Node", "one", value=1, next=reference("Node", "one")))
        node = repo.load("Node", "one")
        assert isinstance(node, Node)
        assert node.next is node

    def test_multi_object_cycle_preserves_identity(self, repo: DictRepo) -> None:
        put(repo, raw("Node", "one", value=1, next=reference("Node", "two")))
        put(repo, raw("Node", "two", value=2, next=reference("Node", "one")))
        one = repo.load("Node", "one")
        assert isinstance(one.next, Node)
        assert one.next.next is one

    @pytest.mark.parametrize("shared", [{"value": 1}, [1, 2]])
    def test_shared_container_identity(self, repo: DictRepo, shared: Any) -> None:
        resolved = repo.resolve_refs({"first": shared, "second": shared})
        assert resolved["first"] is resolved["second"]

    def test_cyclic_raw_dict(self, repo: DictRepo) -> None:
        data: dict[str, Any] = {}
        data["self"] = data
        resolved = repo.resolve_refs(data)
        assert resolved["self"] is resolved

    def test_cyclic_raw_list(self, repo: DictRepo) -> None:
        data: list[Any] = []
        data.append(data)
        resolved = repo.resolve_refs(data)
        assert resolved[0] is resolved

    def test_ref_key_with_sibling_is_not_reference(self, repo: DictRepo) -> None:
        data = {REF_TAG: {TYPE_TAG: "Dog", ID_TAG: "fido"}, "extra": True}
        assert repo.resolve_refs(data) == data

    @pytest.mark.parametrize("bad_ref", [
        {REF_TAG: None}, {REF_TAG: []}, {REF_TAG: {}},
        {REF_TAG: {TYPE_TAG: "Dog"}}, {REF_TAG: {ID_TAG: "fido"}},
        {REF_TAG: {TYPE_TAG: 123, ID_TAG: "fido"}},
        {REF_TAG: {TYPE_TAG: "Dog", ID_TAG: 123}},
    ])
    def test_malformed_reference_raises_value_error(self, repo: DictRepo, bad_ref: Any) -> None:
        with pytest.raises(ValueError):
            repo.resolve_refs(bad_ref)

    def test_failed_nested_load_cleans_outer_placeholder(self, repo: DictRepo) -> None:
        put(repo, raw("Person", "alice", name="Alice", dog=reference("Dog", "missing")))
        with pytest.raises(KeyError):
            repo.load("Person", "alice")
        assert ("Person", "alice") not in repo.cache
        assert ("Dog", "missing") not in repo.cache
