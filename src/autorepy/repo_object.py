from __future__ import annotations

from dataclasses import dataclass, fields, field
from typing import Any, Callable, ClassVar, Mapping, Self, TypeAlias
from autorepy.tags import FORMAT_VERSION_TAG, REF_TAG, TYPE_TAG, ID_TAG


RepoData: TypeAlias = dict[str, Any]
RepoRef: TypeAlias = dict[str, dict[str, str]]
Migration: TypeAlias = Callable[[dict[str, Any]], dict[str, Any]]


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

    CURRENT_FORMAT_VERSION: ClassVar[int] = 1
    MIGRATIONS: ClassVar[dict[int, Migration]] = {}

    @classmethod
    def type_name(cls) -> str:
        return cls.__name__
    
    def to_ref(self) -> RepoRef:
        return {
            REF_TAG: {
                TYPE_TAG: self.type_name(),
                ID_TAG: self.id,
            }
        }

    def to_dict(self) -> RepoData:
        """
        Convert this object to raw repository data. Subclasses may override this
        """
        self._validate_format_version(
            self.CURRENT_FORMAT_VERSION,
            description=f"{type(self).__qualname__}.CURRENT_FORMAT_VERSION",
        )

        data: RepoData = {
            TYPE_TAG: self.type_name(),
            ID_TAG: self.id,
            FORMAT_VERSION_TAG: self.CURRENT_FORMAT_VERSION,
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
        Construct an instance of cls from initialized repository fields.

        The input is first migrated one version at a time. Data without a
        format-version tag is considered version 0.
        """
        data = cls._migrate_fields(data)

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

    @classmethod
    def _migrate_fields(
        cls,
        data: Mapping[str, Any],
    ) -> dict[str, Any]:
        current_version = cls.CURRENT_FORMAT_VERSION
        cls._validate_format_version(
            current_version,
            description=f"{cls.__qualname__}.CURRENT_FORMAT_VERSION",
        )

        for migration_version in cls.MIGRATIONS:
            cls._validate_format_version(
                migration_version,
                description=f"migration version for {cls.__qualname__}",
            )

        migrated = dict(data)
        stored_version = migrated.get(FORMAT_VERSION_TAG, 0)
        cls._validate_format_version(
            stored_version,
            description=f"stored {FORMAT_VERSION_TAG}",
        )

        if stored_version > current_version:
            raise RepoDataError(
                f"Cannot load {cls.__qualname__} format version "
                f"{stored_version}; current version is {current_version}"
            )

        version = stored_version
        while version < current_version:
            try:
                migration = cls.MIGRATIONS[version]
            except KeyError:
                raise RepoDataError(
                    f"Missing migration for {cls.__qualname__} from "
                    f"format version {version} to {version + 1}"
                ) from None

            result = migration(dict(migrated))
            if not isinstance(result, dict):
                raise RepoDataError(
                    f"Migration for {cls.__qualname__} from format version "
                    f"{version} must return a dict"
                )

            migrated = result
            version += 1

        return migrated

    @staticmethod
    def _validate_format_version(version: Any, *, description: str) -> None:
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise RepoDataError(
                f"{description} must be a nonnegative integer, got {version!r}"
            )
        
    @staticmethod
    def _is_omit_or_id(field) -> bool:
        return field.name == ID_FIELD or field.metadata.get(_OMIT_METEDATA_KEY)
