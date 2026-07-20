from autorepy.repo_object import RepoObject
from dataclasses import dataclass

@dataclass
class Dog(RepoObject):
    REPO_OBJECT_TYPE = "dog"
    
    breed: str


def test_dog_to_repo_data():
    fido = Dog("fido", "poodle")
    data = fido.to_repo_data()
    
    assert data.keys() == {"type", "id", "breed"}
    assert data["type"] == "dog"
    assert data["id"] == "fido"
    assert data["breed"] == "poodle"
    