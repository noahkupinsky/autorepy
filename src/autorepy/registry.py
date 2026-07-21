from __future__ import annotations
from autorepy.repo_object import RepoObject

class Registry:
    type_name_to_class_map: dict[str, type]
    class_to_type_names_map: dict[type, list[str]]
    
    def __init__(self, *registrations):
        self.type_name_to_class_map = {}
        self.class_to_type_names_map = {}
        self.register_many(*registrations)
    
    def register(self, cls: type[RepoObject], *aliases: str):
        # make sure this class name and its aliases are unique
        type_names = [cls.repo_type(), *aliases]
        for name in type_names:
            if name in self.type_name_to_class_map:
                raise ValueError(f"Class name {name} is already registered")
            
        if cls in self.class_to_type_names_map:
            raise ValueError(f"Class {cls} is already registered")
        
        for name in type_names:
            self.type_name_to_class_map[name] = cls
        
        self.class_to_type_names_map[cls] = type_names
            
    def register_many(self, *registrations):
        for reg in registrations:
            if isinstance(reg, tuple):
                cls, *aliases = reg
                self.register(cls, *aliases)
            else:
                self.register(reg)
                
    def get_class(self, type_name: str) -> type[RepoObject]:
        return self.type_name_to_class_map[type_name]
    
    def get_type_names(self, value: type[RepoObject] | str) -> list[str]:
        if isinstance(value, str):
            cls = self.get_class(value)
        elif isinstance(value, type) and issubclass(value, RepoObject):
            cls = value
        else:
            raise TypeError(f"Expected type or type name, got {type(value).__name__}")
            
        return self.class_to_type_names_map[cls]