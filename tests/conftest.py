from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from autorepy.dict_repo import DictRepo
from autorepy.file_system_repo import FileSystemRepo
from autorepy.registry import Registry
from autorepy.repo import Repo
from autorepy.tags import ID_TAG, TYPE_TAG
from repo_contract_models import REPO_OBJECT_TYPES


RepoInitializer = Callable[[Registry, Path], Repo]
PutRawRepoData = Callable[[dict], None]


def initialize_dict_repo(registry: Registry, root_dir: Path) -> Repo:
    return DictRepo(registry=registry)


def initialize_file_system_repo(registry: Registry, root_dir: Path) -> Repo:
    return FileSystemRepo(root_dir=root_dir, registry=registry)


REPO_INITIALIZERS = (
    pytest.param(initialize_dict_repo, id="DictRepo"),
    pytest.param(initialize_file_system_repo, id="FileSystemRepo"),
)


@pytest.fixture
def registry() -> Registry:
    return Registry(*REPO_OBJECT_TYPES)


@pytest.fixture(params=REPO_INITIALIZERS)
def repo(request: pytest.FixtureRequest, registry: Registry, tmp_path: Path) -> Repo:
    initializer: RepoInitializer = request.param
    return initializer(registry, tmp_path / "repository")


@pytest.fixture
def put_raw_repo_data(repo: Repo) -> PutRawRepoData:
    def put(data: dict) -> None:
        repo._put_in_repo(data[TYPE_TAG], data[ID_TAG], data)

    return put
