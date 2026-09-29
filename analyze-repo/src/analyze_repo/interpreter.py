import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class VenvLayout(Protocol):
    def get_interpreter(self, venv: Path) -> Path: ...


class PosixVenvLayout:
    def get_interpreter(self, venv: Path) -> Path:
        return venv / "bin" / "python"


class WindowsVenvLayout:
    def get_interpreter(self, venv: Path) -> Path:
        return venv / "Scripts" / "python.exe"


def platform_venv_layout() -> VenvLayout:
    match os.name:
        case "posix":
            return PosixVenvLayout()
        case "nt":
            return WindowsVenvLayout()
        case other:
            raise RuntimeError(f"unsupported platform {other}")


class AmbiguousInterpreterError(LookupError):
    def __init__(self, root: Path, interpreters: Sequence[Path]) -> None:
        listed = " ".join(str(path) for path in interpreters)
        super().__init__(
            f"{root} holds several virtual environments: {listed}. "
            "Pass the toolchain explicitly."
        )


@dataclass(frozen=True)
class PythonToolchainDiscovery:
    layout: VenvLayout

    def get_venv_interpreter(self, directory: Path) -> Path | None:
        interpreter = self.layout.get_interpreter(directory)
        if not (directory / "pyvenv.cfg").is_file():
            return None
        if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
            return None
        return interpreter

    def get_toolchain(self, root: Path) -> Path | None:
        found = [
            interpreter
            for child in sorted(root.iterdir())
            if child.is_dir()
            and (interpreter := self.get_venv_interpreter(child)) is not None
        ]
        match found:
            case []:
                return None
            case [interpreter]:
                return interpreter
            case _:
                raise AmbiguousInterpreterError(root, found)


__all__ = [
    "AmbiguousInterpreterError",
    "PosixVenvLayout",
    "PythonToolchainDiscovery",
    "VenvLayout",
    "WindowsVenvLayout",
    "platform_venv_layout",
]
