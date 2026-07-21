from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from autorepy.repo import Repo
from autorepy.tags import FORMAT_VERSION_TAG, ID_TAG, REF_TAG, TYPE_TAG
from repo_contract_models import (
    BinaryTree,
    Cat,
    CatCafe,
    CustomObject,
    Dog,
    MigratedCat,
    Node,
    Pair,
    Person,
    SelfReferential,
    SlottedObject,
    Tree,
)


PutRawRepoData = Callable[[dict], None]


def raw(type_name: str, object_id: str, **values: Any) -> dict[str, Any]:
    return {
        TYPE_TAG: type_name,
        ID_TAG: object_id,
        FORMAT_VERSION_TAG: 1,
        **values,
    }


def reference(type_name: str, object_id: str) -> dict[str, Any]:
    return {REF_TAG: {TYPE_TAG: type_name, ID_TAG: object_id}}


def test_starts_with_empty_cache(repo: Repo) -> None:
    assert repo.cache == {}


def test_save_caches_exact_object(repo: Repo) -> None:
    dog = Dog(id="fido", breed="corgi")
    repo.save(dog)
    assert repo.cache[("Dog", "fido")] is dog


def test_save_overwrites_object(repo: Repo) -> None:
    repo.save(Dog(id="fido", breed="corgi"))
    replacement = Dog(id="fido", breed="beagle")
    repo.save(replacement)
    repo.cache.clear()
    assert repo.load("Dog", "fido") == replacement


def test_load_constructs_registered_class(
    repo: Repo, put_raw_repo_data: PutRawRepoData
) -> None:
    put_raw_repo_data(raw("Dog", "fido", breed="corgi"))
    loaded = repo.load("Dog", "fido")
    assert isinstance(loaded, Dog)
    assert loaded == Dog(id="fido", breed="corgi")


def test_load_reuses_cached_instance(
    repo: Repo, put_raw_repo_data: PutRawRepoData
) -> None:
    put_raw_repo_data(raw("Dog", "fido", breed="corgi"))
    assert repo.load("Dog", "fido") is repo.load("Dog", "fido")


def test_cache_hit_does_not_require_stored_object(repo: Repo) -> None:
    dog = Dog(id="fido", breed="corgi")
    repo.cache[("Dog", "fido")] = dog
    assert repo.load("Dog", "fido") is dog


def test_delete_removes_object_and_cache(repo: Repo) -> None:
    repo.save(Dog(id="fido", breed="corgi"))
    repo.delete("Dog", "fido")
    assert ("Dog", "fido") not in repo.cache
    with pytest.raises(KeyError):
        repo.load("Dog", "fido")


def test_delete_uncached_object(
    repo: Repo, put_raw_repo_data: PutRawRepoData
) -> None:
    put_raw_repo_data(raw("Dog", "fido", breed="corgi"))
    repo.delete("Dog", "fido")
    with pytest.raises(KeyError):
        repo.load("Dog", "fido")


def test_unknown_type_does_not_pollute_cache(repo: Repo) -> None:
    with pytest.raises(KeyError):
        repo.load("Unknown", "1")
    assert ("Unknown", "1") not in repo.cache


def test_missing_object_does_not_pollute_cache(repo: Repo) -> None:
    with pytest.raises(KeyError):
        repo.load("Dog", "missing")
    assert ("Dog", "missing") not in repo.cache


def test_alias_loads_old_type_as_current_class(
    repo: Repo, put_raw_repo_data: PutRawRepoData
) -> None:
    put_raw_repo_data(raw("LegacyPerson", "alice", name="Alice", dog=None))
    loaded = repo.load("LegacyPerson", "alice")
    assert isinstance(loaded, Person)
    assert loaded == Person(id="alice", name="Alice")


def test_canonical_type_finds_object_stored_under_alias(
    repo: Repo, put_raw_repo_data: PutRawRepoData
) -> None:
    put_raw_repo_data(raw("LegacyPerson", "alice", name="Alice", dog=None))
    loaded = repo.load("Person", "alice")
    assert isinstance(loaded, Person)
    assert loaded.id == "alice"


def test_load_all_includes_canonical_and_alias_names(
    repo: Repo, put_raw_repo_data: PutRawRepoData
) -> None:
    dog = Dog(id="fido", breed="corgi")
    repo.save(dog)
    repo.save(Person(id="john", name="John", dog=dog))
    put_raw_repo_data(
        raw("LegacyPerson", "alice", name="Alice", dog=reference("Dog", "fido"))
    )
    repo.cache.clear()

    loaded = repo.load_all("Person")

    assert {person.id for person in loaded} == {"john", "alice"}
    assert all(isinstance(person, Person) for person in loaded)
    assert loaded[0].dog is loaded[1].dog


def test_custom_from_fields_is_used(
    repo: Repo, put_raw_repo_data: PutRawRepoData
) -> None:
    CustomObject.calls = 0
    put_raw_repo_data(raw("CustomObject", "custom", value=4))
    loaded = repo.load("CustomObject", "custom")
    assert isinstance(loaded, CustomObject)
    assert loaded.value == 8
    assert CustomObject.calls == 1


def test_slotted_dataclass_loads(
    repo: Repo, put_raw_repo_data: PutRawRepoData
) -> None:
    put_raw_repo_data(raw("SlottedObject", "slot", value=7))
    assert repo.load("SlottedObject", "slot") == SlottedObject("slot", 7)


def test_failed_deserialization_removes_placeholder(
    repo: Repo, put_raw_repo_data: PutRawRepoData
) -> None:
    put_raw_repo_data(raw("Dog", "broken"))
    with pytest.raises(ValueError):
        repo.load("Dog", "broken")
    assert ("Dog", "broken") not in repo.cache


def test_format_migration_and_legacy_type_work_together(
    repo: Repo, put_raw_repo_data: PutRawRepoData
) -> None:
    put_raw_repo_data(
        raw("LegacyCat", "old_cat", breed_name="Tabby")
    )
    assert repo.load("MigratedCat", "old_cat") == MigratedCat(
        id="old_cat", breed="Tabby"
    )


def test_embedded_repo_objects_are_reconstructed(repo: Repo) -> None:
    root = Tree(
        id="root",
        data=5,
        children=[
            Tree(id="left", children=[], data=3),
            Tree(id="right", children=[], data=7),
        ],
    )
    repo.save(root)
    repo.cache.clear()

    loaded = repo.load("Tree", "root")

    assert isinstance(loaded, Tree)
    assert all(isinstance(child, Tree) for child in loaded.children)
    assert [child.data for child in loaded.children] == [3, 7]


def test_direct_reference_becomes_repo_object(
    repo: Repo, put_raw_repo_data: PutRawRepoData
) -> None:
    put_raw_repo_data(raw("Dog", "fido", breed="corgi"))
    put_raw_repo_data(
        raw("Person", "alice", name="Alice", dog=reference("Dog", "fido"))
    )
    person = repo.load("Person", "alice")
    assert isinstance(person, Person)
    assert person.dog == Dog(id="fido", breed="corgi")


def test_repeated_reference_preserves_identity(
    repo: Repo, put_raw_repo_data: PutRawRepoData
) -> None:
    put_raw_repo_data(raw("Dog", "fido", breed="corgi"))
    put_raw_repo_data(
        raw(
            "Pair",
            "pair",
            left=reference("Dog", "fido"),
            right=reference("Dog", "fido"),
        )
    )
    pair = repo.load("Pair", "pair")
    assert isinstance(pair, Pair)
    assert pair.left is pair.right


def test_self_reference_preserves_identity(
    repo: Repo, put_raw_repo_data: PutRawRepoData
) -> None:
    put_raw_repo_data(
        raw("Node", "one", value=1, next=reference("Node", "one"))
    )
    node = repo.load("Node", "one")
    assert isinstance(node, Node)
    assert node.next is node


def test_multi_object_cycle_preserves_identity(
    repo: Repo, put_raw_repo_data: PutRawRepoData
) -> None:
    put_raw_repo_data(
        raw("Node", "one", value=1, next=reference("Node", "two"))
    )
    put_raw_repo_data(
        raw("Node", "two", value=2, next=reference("Node", "one"))
    )
    one = repo.load("Node", "one")
    assert isinstance(one.next, Node)
    assert one.next.next is one


def test_saved_self_reference_round_trip(repo: Repo) -> None:
    value = SelfReferential(id="self")
    value.value = value
    repo.save(value)
    repo.cache.clear()
    loaded = repo.load("SelfReferential", "self")
    assert loaded.value is loaded


def test_references_are_not_saved_recursively(repo: Repo) -> None:
    left = BinaryTree(id="left", data=3)
    right = BinaryTree(id="right", data=7)
    root = BinaryTree(id="root", data=5, left=left, right=right)
    repo.save(root)
    repo.cache.clear()
    with pytest.raises(KeyError):
        repo.load("BinaryTree", "root")

    repo.save(left)
    with pytest.raises(KeyError):
        repo.load("BinaryTree", "root")

    repo.save(right)
    loaded = repo.load("BinaryTree", "root")
    assert loaded.left is left
    assert loaded.right is right


def test_deep_references_resolve_and_share_identity(repo: Repo) -> None:
    cats = [Cat(id=name) for name in ("steven", "mike", "tom")]
    cafe = CatCafe(
        id="cafe",
        cat_map={cat.id: cat for cat in cats},
        cats=cats,
    )
    for cat in cats:
        repo.save(cat)
    repo.save(cafe)
    repo.cache.clear()

    loaded_cafe = repo.load("CatCafe", "cafe")
    loaded_steven = repo.load("Cat", "steven")

    assert loaded_cafe.cat_map["steven"] is loaded_steven
    assert loaded_cafe.cats[0] is loaded_steven


@pytest.mark.parametrize("shared", [{"value": 1}, [1, 2]])
def test_reference_resolution_preserves_shared_container_identity(
    repo: Repo, shared: Any
) -> None:
    resolved = repo._resolve_refs({"first": shared, "second": shared})
    assert resolved["first"] is resolved["second"]


def test_reference_resolution_handles_cyclic_dict(repo: Repo) -> None:
    data: dict[str, Any] = {}
    data["self"] = data
    resolved = repo._resolve_refs(data)
    assert resolved["self"] is resolved


def test_reference_resolution_handles_cyclic_list(repo: Repo) -> None:
    data: list[Any] = []
    data.append(data)
    resolved = repo._resolve_refs(data)
    assert resolved[0] is resolved


def test_ref_key_with_sibling_is_not_a_reference(repo: Repo) -> None:
    data = {REF_TAG: {TYPE_TAG: "Dog", ID_TAG: "fido"}, "extra": True}
    assert repo._resolve_refs(data) == data


@pytest.mark.parametrize(
    "bad_ref",
    [
        {REF_TAG: None},
        {REF_TAG: []},
        {REF_TAG: {}},
        {REF_TAG: {TYPE_TAG: "Dog"}},
        {REF_TAG: {ID_TAG: "fido"}},
        {REF_TAG: {TYPE_TAG: 123, ID_TAG: "fido"}},
        {REF_TAG: {TYPE_TAG: "Dog", ID_TAG: 123}},
    ],
)
def test_malformed_reference_is_rejected(repo: Repo, bad_ref: Any) -> None:
    with pytest.raises(ValueError):
        repo._resolve_refs(bad_ref)


def test_failed_nested_load_cleans_all_placeholders(
    repo: Repo, put_raw_repo_data: PutRawRepoData
) -> None:
    put_raw_repo_data(
        raw("Person", "alice", name="Alice", dog=reference("Dog", "missing"))
    )
    with pytest.raises(KeyError):
        repo.load("Person", "alice")
    assert ("Person", "alice") not in repo.cache
    assert ("Dog", "missing") not in repo.cache
