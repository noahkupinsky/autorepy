from autorepy.repo_object import RepoObject
from autorepy.registry import Registry
from dataclasses import dataclass
import pytest


@dataclass
class Dog(RepoObject):
    pass

@dataclass
class Cat(RepoObject):
    pass


def test_register_no_alias():
    registry = Registry()
    registry.register(Dog)
    assert registry.get_class("Dog") == Dog
    

def test_register_collision():
    registry = Registry(Dog)
    with pytest.raises(ValueError):
        registry.register(Dog)

    
def test_register_with_alias():
    registry = Registry()
    registry.register(Dog, "Canine")
    assert registry.get_class("Dog") == Dog
    assert registry.get_class("Canine") == Dog
    
def test_register_many():
    registry = Registry()
    registry.register_many(
        (Dog, "Canine"),
        (Cat, "Feline")
    )
    
    assert registry.get_class("Dog") == Dog
    assert registry.get_class("Canine") == Dog
    assert registry.get_class("Cat") == Cat
    assert registry.get_class("Feline") == Cat
    
def test_init():
    registry = Registry(
        (Dog, "Canine"),
        (Cat, "Feline")
    )
    
    assert registry.get_class("Dog") == Dog
    assert registry.get_class("Canine") == Dog
    assert registry.get_class("Cat") == Cat
    assert registry.get_class("Feline") == Cat