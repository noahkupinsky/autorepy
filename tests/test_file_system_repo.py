from __future__ import annotations

import json
from pathlib import Path

import pytest

from autorepy.file_system_repo import FileSystemRepo
from autorepy.registry import Registry
from autorepy.tags import FORMAT_VERSION_TAG, ID_TAG, TYPE_TAG
from repo_contract_models import Dog


def test_init_creates_only_the_repository_root(
    tmp_path: Path,
    registry: Registry,
) -> None:
    root = tmp_path / "nested" / "objects"

    repo = FileSystemRepo(root_dir=root, registry=registry)

    assert repo.root_dir == root
    assert root.is_dir()
    for type_name in registry.type_name_to_class_map:
        assert not (root / type_name).exists()
    assert repo.list_all_ids(Dog) == []


def test_save_writes_json_at_type_and_id_path(
    tmp_path: Path,
    registry: Registry,
) -> None:
    repo = FileSystemRepo(tmp_path, registry)

    repo.save(Dog(id="fido", breed="corgi"))

    assert (tmp_path / "Dog").is_dir()
    assert json.loads((tmp_path / "Dog" / "fido.json").read_text()) == {
        TYPE_TAG: "Dog",
        ID_TAG: "fido",
        FORMAT_VERSION_TAG: 1,
        "breed": "corgi",
    }


def test_separate_instances_share_files_but_not_cache(
    tmp_path: Path,
    registry: Registry,
) -> None:
    writer = FileSystemRepo(tmp_path, registry)
    reader = FileSystemRepo(tmp_path, registry)
    dog = Dog(id="fido", breed="corgi")
    writer.save(dog)

    loaded = reader.load("Dog", "fido")

    assert loaded == dog
    assert loaded is not dog


def test_storage_lists_only_json_ids(
    tmp_path: Path,
    registry: Registry,
) -> None:
    repo = FileSystemRepo(tmp_path, registry)
    (tmp_path / "Dog").mkdir()
    (tmp_path / "Dog" / "fido.json").write_text("{}")
    (tmp_path / "Dog" / "ignore.txt").write_text("ignored")

    assert repo._get_all_ids_for_type_name("Dog") == ["fido"]


@pytest.mark.parametrize("bad_id", ["", ".", "..", "../outside", "a/b"])
def test_rejects_ids_that_are_not_single_path_components(
    tmp_path: Path,
    registry: Registry,
    bad_id: str,
) -> None:
    repo = FileSystemRepo(tmp_path, registry)

    with pytest.raises(ValueError):
        repo.save(Dog(id=bad_id, breed="corgi"))


def test_rejects_unsafe_type_name_when_storage_is_accessed(
    tmp_path: Path,
) -> None:
    registry = Registry((Dog, "../outside"))
    repo = FileSystemRepo(tmp_path, registry)

    with pytest.raises(ValueError):
        repo.list_all_ids("../outside")


def test_non_object_json_is_rejected(
    tmp_path: Path,
    registry: Registry,
) -> None:
    repo = FileSystemRepo(tmp_path, registry)
    (tmp_path / "Dog").mkdir()
    (tmp_path / "Dog" / "fido.json").write_text("[]")

    with pytest.raises(ValueError, match="must contain a JSON object"):
        repo.load("Dog", "fido")
