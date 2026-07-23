from typing import Any, ClassVar

import pytest

from autorepy.repo_object import RepoDataError, RepoObject, ref, omit, type_ref
from autorepy.tags import FORMAT_VERSION_TAG, TYPE_TAG, ID_TAG, TYPE_REF_TAG
from dataclasses import dataclass

@dataclass
class Dog(RepoObject):
    breed: str
    
@dataclass
class Omitter(RepoObject):
    foo: str = omit()


def test_dog_to_repo_data():
    fido = Dog("fido", "poodle")
    data = fido.to_dict()
    
    assert data.keys() == {TYPE_TAG, ID_TAG, FORMAT_VERSION_TAG, "breed"}
    assert data[TYPE_TAG] == "Dog"
    assert data[ID_TAG] == "fido"
    assert data[FORMAT_VERSION_TAG] == 1
    assert data["breed"] == "poodle"
    
    
def test_dog_from_repo_data():
    data = {TYPE_TAG: "Dog", ID_TAG: "fido", FORMAT_VERSION_TAG: 1, "breed": "poodle"}
    fido = Dog.from_fields(data)
    
    assert fido.id == "fido"
    assert fido.breed == "poodle"
    
    
@dataclass
class CustomDataConversion(RepoObject):
    foo: int
    
    def to_dict(self):
        return {
            TYPE_TAG: self.type_name(),
            ID_TAG: self.id,
            "foo": self.foo + 1
        }
        
    def from_fields(data):
        return CustomDataConversion(id=data[ID_TAG], foo=data["foo"] - 1)
    
    
def test_custom_data_conversion_to_repo_data():
    fido = CustomDataConversion(id="fido", foo=1)
    data = fido.to_dict()
    
    assert data.keys() == {TYPE_TAG, ID_TAG, "foo"}
    assert data[ID_TAG] == "fido"
    assert data[TYPE_TAG] == "CustomDataConversion"
    assert data["foo"] == 2
    
    
def test_custom_data_conversion_from_repo_data():
    data = {
        TYPE_TAG: "CustomDataConversion", 
        ID_TAG: "fido", 
        "foo": 1
    }
    converted = CustomDataConversion.from_fields(data)
    
    assert converted.id == "fido"
    assert converted.foo == 0
    
    
@dataclass
class Cat(RepoObject):
    breed: str


@dataclass
class CatOwner(RepoObject):
    cat: Cat = ref()
    
    
def test_ref_field():
    cat = Cat(id="Bob", breed="Tabby")
    owner = CatOwner(id="Alice", cat=cat)
    
    data = owner.to_dict()
    
    assert data["cat"] == cat.to_ref()
    
    
def test_omit_field():
    om = Omitter(id="Alice", foo="omit me!")
    
    data = om.to_dict()
    
    assert "foo" not in data


def migrate_profile_0_to_1(data: dict[str, Any]) -> dict[str, Any]:
    data["full_name"] = data.pop("name")
    return data


def migrate_profile_1_to_2(data: dict[str, Any]) -> dict[str, Any]:
    first, last = data.pop("full_name").split(" ", maxsplit=1)
    data.update(first_name=first, last_name=last)
    return data


@dataclass
class Profile(RepoObject):
    CURRENT_FORMAT_VERSION: ClassVar[int] = 2
    MIGRATIONS: ClassVar = {0: migrate_profile_0_to_1, 1: migrate_profile_1_to_2}
    first_name: str
    last_name: str


def test_from_fields_migrates_unversioned_data_without_mutating_input():
    original = {TYPE_TAG: "Profile", ID_TAG: "alice", "name": "Alice Smith"}
    assert Profile.from_fields(original) == Profile("alice", "Alice", "Smith")
    assert original == {TYPE_TAG: "Profile", ID_TAG: "alice", "name": "Alice Smith"}


def test_from_fields_runs_partial_migration_chain():
    data = {TYPE_TAG: "Profile", ID_TAG: "alice", FORMAT_VERSION_TAG: 1, "full_name": "Alice Smith"}
    assert Profile.from_fields(data) == Profile("alice", "Alice", "Smith")


def test_current_version_skips_migrations():
    data = {TYPE_TAG: "Profile", ID_TAG: "alice", FORMAT_VERSION_TAG: 2, "first_name": "Alice", "last_name": "Smith"}
    assert Profile.from_fields(data) == Profile("alice", "Alice", "Smith")


def test_missing_migration_step_is_rejected():
    with pytest.raises(RepoDataError, match="Missing migration.*version 0 to 1"):
        Dog.from_fields({TYPE_TAG: "Dog", ID_TAG: "fido", "breed": "corgi"})


@pytest.mark.parametrize("version", [-1, 1.5, "1", True])
def test_invalid_stored_version_is_rejected(version: Any):
    with pytest.raises(RepoDataError, match="nonnegative integer"):
        Dog.from_fields({TYPE_TAG: "Dog", ID_TAG: "fido", FORMAT_VERSION_TAG: version, "breed": "corgi"})


def test_future_version_is_rejected():
    with pytest.raises(RepoDataError, match="current version is 1"):
        Dog.from_fields({TYPE_TAG: "Dog", ID_TAG: "fido", FORMAT_VERSION_TAG: 2, "breed": "corgi"})


def test_migration_must_return_dict():
    @dataclass
    class InvalidMigration(RepoObject):
        MIGRATIONS: ClassVar = {0: lambda data: None}

    with pytest.raises(RepoDataError, match="must return a dict"):
        InvalidMigration.from_fields({TYPE_TAG: "InvalidMigration", ID_TAG: "x"})


def test_migrations_do_not_need_to_update_format_version_tag():
    calls = []

    def migrate_0_to_1(data):
        calls.append(0)
        return data

    def migrate_1_to_2(data):
        calls.append(1)
        return data

    @dataclass
    class Migrated(RepoObject):
        CURRENT_FORMAT_VERSION: ClassVar[int] = 2
        MIGRATIONS: ClassVar = {0: migrate_0_to_1, 1: migrate_1_to_2}

    loaded = Migrated.from_fields({TYPE_TAG: "Migrated", ID_TAG: "x"})

    assert loaded == Migrated("x")
    assert calls == [0, 1]


@pytest.mark.parametrize("version", [-1, 1.5, "1", True])
def test_invalid_current_version_is_rejected(version: Any):
    @dataclass
    class InvalidVersion(RepoObject):
        CURRENT_FORMAT_VERSION: ClassVar = version

    with pytest.raises(RepoDataError, match="nonnegative integer"):
        InvalidVersion.from_fields({TYPE_TAG: "InvalidVersion", ID_TAG: "x", FORMAT_VERSION_TAG: 0})


def test_to_dict_rejects_invalid_current_version():
    @dataclass
    class InvalidVersion(RepoObject):
        CURRENT_FORMAT_VERSION: ClassVar = -1

    with pytest.raises(RepoDataError, match="nonnegative integer"):
        InvalidVersion("x").to_dict()
        
        
        
@dataclass
class Foo(RepoObject):
    pass


@dataclass
class Bar(RepoObject):
    foo_type: type = type_ref()
    
    
def test_type_ref_rejects_non_repo_object():
    with pytest.raises(TypeError):
        Bar(foo_type="x").to_dict()
        
        
def test_type_ref_succeeds_for_repo_object():
    assert Bar(id="bar", foo_type=Foo).to_dict() == {
        TYPE_TAG: "Bar",
        ID_TAG: "bar",
        FORMAT_VERSION_TAG: 1,
        "foo_type": {
            TYPE_REF_TAG: {
                TYPE_TAG: "Foo",
            }
        }
    }
