from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, ClassVar, Mapping, Self


RepoData = dict[str, Any]


@dataclass
class RepoObject:
    id: str

    # Every concrete subclass must override this.
    REPO_OBJECT_TYPE: ClassVar[str]

    # Maps stored "type" values to Python classes.
    _type_registry: ClassVar[dict[str, type[RepoObject]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        repo_type = getattr(cls, "REPO_OBJECT_TYPE", None)

        if not isinstance(repo_type, str) or not repo_type:
            raise TypeError(
                f"{cls.__name__} must define a nonempty string "
                f"REPO_OBJECT_TYPE"
            )

        existing = RepoObject._type_registry.get(repo_type)
        if existing is not None and existing is not cls:
            raise TypeError(
                f"Repo object type {repo_type!r} is already registered "
                f"to {existing.__name__}"
            )

        RepoObject._type_registry[repo_type] = cls

    def to_repo_data(self) -> RepoData:
        """
        Convert this object into data suitable for crossing the repository
        boundary.

        Subclasses may override this when they need custom serialization.
        """
        data = {
            field.name: getattr(self, field.name)
            for field in fields(self)
        }

        return {
            "type": self.REPO_OBJECT_TYPE,
            **data,
        }

    @classmethod
    def from_repo_data(cls, data: Mapping[str, Any]) -> Self:
        """
        Construct an object from repository data.

        When called on RepoObject itself, dispatch according to data["type"].
        When called on a subclass, construct that particular subclass.
        """
        repo_type = data.get("type")

        if not isinstance(repo_type, str):
            raise ValueError("Repo data must contain a string 'type' field")

        if cls is RepoObject:
            try:
                concrete_class = cls._type_registry[repo_type]
            except KeyError:
                raise ValueError(
                    f"Unknown repo object type: {repo_type!r}"
                ) from None

            return concrete_class.from_repo_data(data)

        if repo_type != cls.REPO_OBJECT_TYPE:
            raise ValueError(
                f"Cannot deserialize type {repo_type!r} as "
                f"{cls.__name__}; expected {cls.REPO_OBJECT_TYPE!r}"
            )

        field_names = {field.name for field in fields(cls)}
        constructor_data = {
            key: value
            for key, value in data.items()
            if key in field_names
        }

        return cls(**constructor_data)