from __future__ import annotations

from autorepy.dict_repo import DictRepo
from autorepy.registry import Registry
from autorepy.tags import FORMAT_VERSION_TAG, ID_TAG, TYPE_TAG
from repo_contract_models import Dog


def test_constructor_initializes_independent_state(registry: Registry) -> None:
    first = DictRepo(registry)
    second = DictRepo(registry)

    first.save(Dog(id="fido", breed="corgi"))

    assert first.registry is registry
    assert first.data
    assert first.cache
    assert second.data == {}
    assert second.cache == {}


def test_storage_uses_type_and_id_tuple_keys(registry: Registry) -> None:
    repo = DictRepo(registry)
    data = {
        TYPE_TAG: "Dog",
        ID_TAG: "fido",
        FORMAT_VERSION_TAG: 1,
        "breed": "corgi",
    }

    repo._put_in_repo("Dog", "fido", data)

    assert repo.data[("Dog", "fido")] is data
    assert repo._get_from_repo("Dog", "fido") is data
    assert repo._has_in_repo("Dog", "fido")
    assert repo._get_all_ids_for_type_name("Dog") == ["fido"]


def test_storage_delete_removes_tuple_key(registry: Registry) -> None:
    repo = DictRepo(registry)
    repo._put_in_repo("Dog", "fido", {})

    repo._delete_from_repo("Dog", "fido")

    assert ("Dog", "fido") not in repo.data


def test_missing_storage_key_raises_key_error(registry: Registry) -> None:
    repo = DictRepo(registry)

    try:
        repo._get_from_repo("Dog", "missing")
    except KeyError:
        pass
    else:
        raise AssertionError("Expected missing DictRepo key to raise KeyError")
