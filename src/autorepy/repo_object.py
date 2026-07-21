from __future__ import annotations

from dataclasses import dataclass, fields, field
from typing import Any, ClassVar, Mapping, Self, TypeAlias
from autorepy.tags import REF_TAG, TYPE_TAG, ID_TAG


RepoData: TypeAlias = dict[str, Any]
RepoRef: TypeAlias = dict[str, dict[str, str]]


class RepoDataError(ValueError):
    """Raised when repository data cannot be deserialized."""
    
    
ID_FIELD = "id"
_REF_METADATA_KEY = object()
_DEEP_REF_METADATA_KEY = object()
_OMIT_METEDATA_KEY = object()


def ref(**kwargs):
    metadata = kwargs.pop("metadata", {})
    metadata = {
        **metadata,
        _REF_METADATA_KEY: True,
    }
    return field(metadata=metadata, **kwargs)


def deep_ref(**kwargs):
    metadata = kwargs.pop("metadata", {})
    metadata = {
        **metadata,
        _DEEP_REF_METADATA_KEY: True,
    }
    return field(metadata=metadata, **kwargs)


def omit(**kwargs):
    metadata = kwargs.pop("metadata", {})
    metadata = {
        **metadata,
        _OMIT_METEDATA_KEY: True,
    }
    return field(metadata=metadata, **kwargs)


@dataclass
class RepoObject:
    id: str

    @classmethod
    def repo_type(cls) -> str:
        return cls.__name__
    
    def to_ref(self) -> RepoRef:
        return {
            REF_TAG: {
                TYPE_TAG: self.repo_type(),
                ID_TAG: self.id,
            }
        }

    def to_dict(self) -> RepoData:
        """
        Convert this object to raw repository data. Subclasses may override this
        """
        data: RepoData = {
            TYPE_TAG: self.repo_type(),
            ID_TAG: self.id
        }
        
        for field in fields(self):
            if self._is_omit_or_id(field):
                continue
            
            value = getattr(self, field.name)
            
            if field.metadata.get(_DEEP_REF_METADATA_KEY):
                value = self._deep_obj_to_ref(value)
            elif field.metadata.get(_REF_METADATA_KEY):
                value = self._obj_to_ref(value)
            else:
                value = self._deep_serialize(value)

            data[field.name] = value

        return data
    
    @staticmethod
    def _obj_to_ref(value: Any) -> RepoRef | None:
        if value is None:
            return None

        if not isinstance(value, RepoObject):
            raise TypeError(f"Called _obj_to_ref on value of type {type(value).__name__}")

        return value.to_ref()
    
    
    @staticmethod
    def _deep_obj_to_ref(value: Any) -> Any:
        if isinstance(value, list):
            return [RepoObject._deep_obj_to_ref(v) for v in value]
        elif isinstance(value, dict):
            return {k: RepoObject._deep_obj_to_ref(v) for k, v in value.items()}
        elif isinstance(value, RepoObject):
            return value.to_ref()
        else:
            return value
        
    @staticmethod
    def _deep_serialize(value: Any) -> Any:
        if isinstance(value, RepoObject):
            return value.to_dict()
        elif isinstance(value, list):
            return [RepoObject._deep_serialize(v) for v in value]
        elif isinstance(value, dict):
            return {
                RepoObject._ensure_string(k): RepoObject._deep_serialize(v) 
                for k, v in value.items()
            }
        else:
            return RepoObject._ensure_primitive(value)
        
    @staticmethod
    def _ensure_string(value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError(f"Expected string, got {type(value).__name__}")
        return value
        
    @staticmethod
    def _ensure_primitive(value: Any) -> Any:
        if not isinstance(value, (int, float, str, bool)):
            raise TypeError(f"Expected primitive type, got {type(value).__name__}")
        return value

    @classmethod
    def from_fields(
        cls,
        data: Mapping[str, Any],
    ) -> Self:
        """
        Construct an instance of cls from raw repository data.
        """
        init_field_names = {
            field.name
            for field in fields(cls)
            if field.init and not cls._is_omit_or_id(field)
        }

        arguments = {
            name: data[name]
            for name in init_field_names
            if name in data
        }
        
        arguments[ID_FIELD] = data[ID_TAG]

        try:
            return cls(**arguments)
        except TypeError as error:
            raise RepoDataError(f"Could not construct {cls.__qualname__} from repo data") from error
        
    @staticmethod
    def _is_omit_or_id(field) -> bool:
        return field.name == ID_FIELD or field.metadata.get(_OMIT_METEDATA_KEY)