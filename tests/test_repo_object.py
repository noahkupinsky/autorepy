from autorepy.repo_object import RepoObject, ref, omit
from autorepy.tags import TYPE_TAG, ID_TAG
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
    
    assert data.keys() == {TYPE_TAG, ID_TAG, "breed"}
    assert data[TYPE_TAG] == "Dog"
    assert data[ID_TAG] == "fido"
    assert data["breed"] == "poodle"
    
    
def test_dog_from_repo_data():
    data = {TYPE_TAG: "Dog", ID_TAG: "fido", "breed": "poodle"}
    fido = Dog.from_fields(data)
    
    assert fido.id == "fido"
    assert fido.breed == "poodle"
    
    
@dataclass
class CustomDataConversion(RepoObject):
    foo: int
    
    def to_dict(self):
        return {
            TYPE_TAG: self.repo_type(),
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

