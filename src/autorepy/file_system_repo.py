from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from autorepy.registry import Registry
from autorepy.repo import Repo


class FileSystemRepo(Repo):
    """Store repository objects as JSON files grouped by repository type.

    An object with type ``Dog`` and id ``fido`` is stored at
    ``<root_dir>/Dog/fido.json``.
    """

    def __init__(
        self,
        root_dir: str | os.PathLike[str],
        registry: Registry,
    ) -> None:
        super().__init__(registry)
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

        # Include aliases as well as canonical class names. Old data may still
        # be addressed by an alias, and Repo.load() uses that stored type name.
        for type_name in registry.type_name_to_class_map:
            self._type_dir(type_name).mkdir(exist_ok=True)
            
    def _get_all_ids_for_type_name(self, type):
        return [
            object_id
            for object_id in os.listdir(self._type_dir(type))
            if object_id.endswith(".json")
        ]
        
    def _has_in_repo(self, type: str, id: str) -> bool:
        return self._object_path(type, id).exists()

    def _put_in_repo(
        self,
        type: str,
        id: str,
        data: dict[str, Any],
    ) -> None:
        type_dir = self._type_dir(type)
        type_dir.mkdir(exist_ok=True)

        path = self._object_path(type, id)
        temporary_path = path.with_suffix(path.suffix + ".tmp")

        try:
            with temporary_path.open("w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
                file.write("\n")
            temporary_path.replace(path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    def _get_from_repo(self, type: str, id: str) -> dict[str, Any]:
        path = self._object_path(type, id)

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError(
                f"Repository file {path} must contain a JSON object"
            )

        return data

    def _delete_from_repo(self, type: str, id: str) -> None:
        self._object_path(type, id).unlink()

    def _type_dir(self, type_name: str) -> Path:
        self._validate_path_component(type_name, name="type")
        return self.root_dir / type_name

    def _object_path(self, type_name: str, object_id: str) -> Path:
        self._validate_path_component(object_id, name="id")
        return self._type_dir(type_name) / f"{object_id}.json"

    @staticmethod
    def _validate_path_component(value: str, *, name: str) -> None:
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")

        separators = {os.sep}
        if os.altsep is not None:
            separators.add(os.altsep)

        if (
            not value
            or value in {".", ".."}
            or any(separator in value for separator in separators)
        ):
            raise ValueError(
                f"{name} must be a single non-empty path component"
            )
