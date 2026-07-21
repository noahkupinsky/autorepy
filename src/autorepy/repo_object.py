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


def ref(**kwargs):
    metadata = kwargs.pop("metadata", {})
    metadata = {
        **metadata,
        _REF_METADATA_KEY: True,
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

    def to_repo_data(self) -> RepoData:
        """
        Convert this object to raw repository data. Subclasses may override this
        """
        data: RepoData = {
            TYPE_TAG: self.repo_type(),
            ID_TAG: self.id
        }
        
        for field in fields(self):
            if field.name == ID_FIELD:
                continue
            
            value = getattr(self, field.name)
            
            if field.metadata.get(_REF_METADATA_KEY):
                value = self._obj_to_ref(field_name=field.name, value=value)

            data[field.name] = value

        return data
    
    @staticmethod
    def _obj_to_ref(*, field_name: str, value: Any) -> RepoRef | None:
        if value is None:
            return None

        if not isinstance(value, RepoObject):
            raise TypeError(
                f"Reference field {field_name!r} must contain a "
                f"RepoObject or None, not {type(value).__name__}"
            )

        return value.to_ref()

    @classmethod
    def from_repo_data(
        cls,
        data: Mapping[str, Any],
    ) -> Self:
        """
        Construct an instance of cls from raw repository data.
        """
        init_field_names = {
            field.name
            for field in fields(cls)
            if field.init and field.name != ID_FIELD
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