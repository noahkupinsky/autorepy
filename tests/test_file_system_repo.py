from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from autorepy.file_system_repo import FileSystemRepo
from autorepy.registry import Registry
from autorepy.repo_object import RepoObject, ref
from autorepy.repo import Repo
from autorepy.tags import REF_TAG, ID_TAG, TYPE_TAG
from typing import Any


@dataclass
class Dog(RepoObject):
    breed: str


@dataclass
class Person(RepoObject):
    name: str
    dog: Dog | None = ref(default=None)


@pytest.fixture
def registry() -> Registry:
    return Registry(Dog, (Person, "LegacyPerson"))


@pytest.fixture
def repo(tmp_path: Path, registry: Registry) -> FileSystemRepo:
    return FileSystemRepo(tmp_path / "objects", registry)

def raw(type_name: str, object_id: str, **values: Any) -> dict[str, Any]:
    return {TYPE_TAG: type_name, ID_TAG: object_id, **values}


def reference(type_name: str, object_id: str) -> dict[str, Any]:
    return {REF_TAG: {TYPE_TAG: type_name, ID_TAG: object_id}}


def put(repo: Repo, data: dict[str, Any]) -> None:
    repo._put_in_repo(data[TYPE_TAG], data[ID_TAG], data)


def test_init_creates_root_and_directory_for_every_registered_name(
    tmp_path: Path,
    registry: Registry,
) -> None:
    root = tmp_path / "nested" / "objects"

    created = FileSystemRepo(root, registry)

    assert created.root_dir == root
    assert root.is_dir()
    assert (root / "Dog").is_dir()
    assert (root / "Person").is_dir()
    assert (root / "LegacyPerson").is_dir()


def test_save_writes_json_at_type_and_id_path(
    repo: FileSystemRepo,
) -> None:
    dog = Dog(id="fido", breed="corgi")

    repo.save(dog)

    path = repo.root_dir / "Dog" / "fido.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        TYPE_TAG: "Dog",
        ID_TAG: "fido",
        "breed": "corgi",
    }
    assert repo.cache[("Dog", "fido")] is dog


def test_load_after_cache_clear_reconstructs_object(
    repo: FileSystemRepo,
) -> None:
    repo.save(Dog(id="fido", breed="corgi"))
    repo.cache.clear()

    loaded = repo.load("Dog", "fido")

    assert isinstance(loaded, Dog)
    assert loaded == Dog(id="fido", breed="corgi")


def test_separate_instances_share_files_but_not_cache(
    tmp_path: Path,
    registry: Registry,
) -> None:
    root = tmp_path / "objects"
    writer = FileSystemRepo(root, registry)
    reader = FileSystemRepo(root, registry)
    writer.save(Dog(id="fido", breed="corgi"))

    loaded = reader.load("Dog", "fido")

    assert loaded == Dog(id="fido", breed="corgi")
    assert loaded is not writer.cache[("Dog", "fido")]


def test_save_overwrites_existing_json(repo: FileSystemRepo) -> None:
    repo.save(Dog(id="fido", breed="corgi"))
    repo.save(Dog(id="fido", breed="beagle"))
    repo.cache.clear()

    assert repo.load("Dog", "fido") == Dog(id="fido", breed="beagle")


def test_load_resolves_reference_from_another_file(
    repo: FileSystemRepo,
) -> None:
    dog = Dog(id="fido", breed="corgi")
    person = Person(id="alice", name="Alice", dog=dog)
    repo.save(dog)
    repo.save(person)
    repo.cache.clear()

    loaded = repo.load("Person", "alice")

    assert isinstance(loaded, Person)
    assert loaded.name == "Alice"
    assert loaded.dog == dog


def test_alias_directory_can_load_legacy_data(
    repo: FileSystemRepo,
) -> None:
    path = repo.root_dir / "LegacyPerson" / "alice.json"
    path.write_text(
        json.dumps(
            {
                TYPE_TAG: "LegacyPerson",
                ID_TAG: "alice",
                "name": "Alice",
                "dog": None,
            }
        ),
        encoding="utf-8",
    )

    loaded = repo.load("LegacyPerson", "alice")

    assert isinstance(loaded, Person)
    assert loaded == Person(id="alice", name="Alice")


def test_delete_removes_json_and_cache_entry(repo: FileSystemRepo) -> None:
    repo.save(Dog(id="fido", breed="corgi"))
    path = repo.root_dir / "Dog" / "fido.json"

    repo.delete("Dog", "fido")

    assert not path.exists()
    assert ("Dog", "fido") not in repo.cache


def test_missing_object_raises_file_not_found(repo: FileSystemRepo) -> None:
    with pytest.raises(KeyError):
        repo.load("Dog", "missing")


@pytest.mark.parametrize("bad_id", ["", ".", "..", "../outside", "a/b"])
def test_rejects_ids_that_are_not_single_path_components(
    repo: FileSystemRepo,
    bad_id: str,
) -> None:
    with pytest.raises(ValueError):
        repo.save(Dog(id=bad_id, breed="corgi"))


def test_rejects_unsafe_registered_type_name(tmp_path: Path) -> None:
    registry = Registry((Dog, "../outside"))

    with pytest.raises(ValueError):
        FileSystemRepo(tmp_path / "objects", registry)


def test_non_object_json_is_rejected(repo: FileSystemRepo) -> None:
    path = repo.root_dir / "Dog" / "fido.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a JSON object"):
        repo.load("Dog", "fido")

def test_load_all_with_aliases(repo: Repo) -> None:
    johns_dog = Dog(id="fido", breed="corgi")
    repo.save(johns_dog)
    john = Person(id="john", name="John", dog=johns_dog)
    repo.save(john)
    put(repo, raw("LegacyPerson", "alice", name="Alice", dog=reference("Dog", "fido")))
    repo.cache = {}
    loaded = repo.load_all("Person")
    assert isinstance(loaded, list)
    assert len(loaded) == 2
    assert loaded[0] == Person(id="john", name="John", dog=johns_dog)
    assert loaded[1] == Person(id="alice", name="Alice", dog=johns_dog)