from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import fields, is_dataclass
from typing import Any, Iterable

from autorepy.registry import Registry
from autorepy.repo_object import RepoObject
from autorepy.tags import REF_TAG, TYPE_TAG, ID_TAG


class Repo(ABC):
    registry: Registry
    cache: dict[tuple[str, str], RepoObject]

    def __init__(self, registry: Registry) -> None:
        self.registry = registry
        self.cache = {}

    def save(self, obj: RepoObject) -> None:
        """
        Save a repository object to the repository and add it to the cache.
        """
        data = obj.to_dict()
        type_name = data[TYPE_TAG]
        object_id = data[ID_TAG]

        self._put_in_repo(type_name, object_id, data)
        self.cache[(type_name, object_id)] = obj    

    def load(self, type: str | type[RepoObject], id: str) -> RepoObject:
        """
        Load a repository object and recursively resolve its references.

        An uninitialized instance is inserted into the cache before references
        are resolved. This allows cyclic references to point to the same
        eventual RepoObject instance.
        """
        type = self._as_type_name(type)
            
        key = (type, id)

        cached = self.cache.get(key)
        if cached is not None:
            return cached

        cls = self.registry.get_class(type)
        if not self._has_in_repo(type, id):
            type = self._find_under_alias(type, id)

        raw_data = self._get_from_repo(type, id)

        if not issubclass(cls, RepoObject):
            raise TypeError(
                f"Registry entry for {type!r} is not a RepoObject subclass"
            )

        # Allocate the object without calling __init__. This object must be
        # cached before resolving references so cycles return the same instance.
        placeholder = cls.__new__(cls)
        self.cache[key] = placeholder

        try:
            resolved_data = self._resolve_refs(raw_data)

            # Let the class perform its normal deserialization logic.
            initialized = self._deep_from_repo_data(resolved_data)

            # Transfer the initialized object's state onto the cached object.
            self._copy_object_state(
                source=initialized,
                destination=placeholder,
            )
        except Exception:
            self.cache.pop(key, None)
            raise

        return placeholder

    @staticmethod
    def _copy_object_state(
        *,
        source: RepoObject,
        destination: RepoObject,
    ) -> None:
        """
        Copy the deserialized object's state onto the cached placeholder.

        object.__setattr__ supports ordinary, slotted, and frozen dataclasses.
        """
        if not is_dataclass(source):
            raise TypeError(
                f"{type(source).__qualname__} must be a dataclass"
            )

        for dataclass_field in fields(source):
            object.__setattr__(
                destination,
                dataclass_field.name,
                getattr(source, dataclass_field.name),
            )

    def _resolve_refs(
        self,
        data: Any,
        accumulator: dict[int, Any] | None = None,
    ) -> Any:
        """
        Recursively resolve repository references into RepoObject instances.

        References have the form:

            {
                REF_TAG: {
                    TYPE_TAG: "...",
                    ID_TAG: "..."
                }
            }

        Dictionaries and lists are traversed recursively. The accumulator
        preserves shared container identity and handles cycles in the raw
        input structure.
        """
        if accumulator is None:
            accumulator = {}

        if isinstance(data, dict):
            # A dictionary is a reference only when REF_TAG is its sole key.
            if set(data) == {REF_TAG}:
                reference = data[REF_TAG]

                if not isinstance(reference, dict):
                    raise ValueError(
                        f"{REF_TAG!r} must contain a dictionary"
                    )

                type_name = reference.get(TYPE_TAG)
                object_id = reference.get(ID_TAG)

                if not isinstance(type_name, str):
                    raise ValueError(
                        f"{REF_TAG!r}.{TYPE_TAG!r} must be a string"
                    )

                if not isinstance(object_id, str):
                    raise ValueError(
                        f"{REF_TAG!r}.{ID_TAG!r} must be a string"
                    )

                return self.load(
                    type=type_name,
                    id=object_id,
                )

            identity = id(data)

            if identity in accumulator:
                return accumulator[identity]

            resolved_dict: dict[str, Any] = {}
            accumulator[identity] = resolved_dict

            for key, value in data.items():
                resolved_dict[key] = self._resolve_refs(
                    value,
                    accumulator,
                )

            return resolved_dict

        if isinstance(data, list):
            identity = id(data)

            if identity in accumulator:
                return accumulator[identity]

            resolved_list: list[Any] = []
            accumulator[identity] = resolved_list

            resolved_list.extend(
                self._resolve_refs(item, accumulator)
                for item in data
            )

            return resolved_list

        return data
    
    def _deep_from_repo_data(self, data: Any) -> Any:
        if isinstance(data, dict):
            # before trying to turn this into a repo object, make sure all its fields are appropriately initialized
            data = {k: self._deep_from_repo_data(v) for k, v in data.items()}
            
            if TYPE_TAG in data and ID_TAG in data:
                cls = self.registry.get_class(data[TYPE_TAG])
                return cls.from_fields(data)
            else:
                return data
        elif isinstance(data, list):
            return [self._deep_from_repo_data(item) for item in data]
        else:
            return data

    def _find_under_alias(self, type: str, id: str) -> str | None:
        """
        Looks for an alias of the given type such that (alias, id) is in the repo
        Returns the alias or None if not found
        """
        for alias in self.registry.get_type_names(type):
            if self._has_in_repo(alias, id):
                return alias
            
        raise KeyError(f"Object {type!r} with id {id!r} not found under any aliases")

    def load_all(self, type: str | type[RepoObject]) -> list[RepoObject]:
        """
        Loads all objects whose type is the given type or an alias of it
        """
        type = self._as_type_name(type)
        
        return [
            self.load(type=type, id=id)
            for alias in self.registry.get_type_names(type)
            for id in self._get_all_ids_for_type_name(alias)
        ]
        
    @staticmethod
    def _as_type_name(type: str | type[RepoObject]) -> str:
        if isinstance(type, str):
            return type
        if issubclass(type, RepoObject):
            return type.type_name()
        raise TypeError(f"Expected type or type name, got {type(type).__name__}")

    @abstractmethod
    def _get_all_ids_for_type_name(self, type_name: str) -> list[str]:
        """
        Return a list of ids for the given type name. 
        Does not look for ids of any aliases
        """
        ...
        
    @abstractmethod
    def _has_in_repo(self, type: str, id: str) -> bool:
        ...

    @abstractmethod
    def _put_in_repo(
        self,
        type: str,
        id: str,
        data: dict[str, Any],
    ) -> None:
        ...

    @abstractmethod
    def _get_from_repo(
        self,
        type: str,
        id: str,
    ) -> dict[str, Any]:
        """
        Return raw repository data without resolving references.
        """
        ...

    def delete(self, type: str, id: str) -> None:
        self._delete_from_repo(type, id)
        self.cache.pop((type, id), None)

    @abstractmethod
    def _delete_from_repo(self, type: str, id: str) -> None:
        ...