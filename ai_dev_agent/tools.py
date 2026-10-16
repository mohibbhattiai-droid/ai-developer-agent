"""Workspace-limited tools for the AI Developer Agent.

Only files under the configured workspace can be accessed. No arbitrary shell
commands are accepted by this tool layer.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path, PureWindowsPath
from typing import Any


IGNORED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build"
}
TEXT_EXTENSIONS = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".html", ".css", ".js", ".ts", ".tsx", ".jsx", ".csv", ".sql",
    ".sh", ".ps1", ".xml", ".env.example"
}
MAX_READ_BYTES = 256_000
MAX_WRITE_BYTES = 100_000
MAX_SEARCH_FILES = 250
MAX_LIST_FILES = 300
SENSITIVE_NAMES = {".env", ".env.local", ".env.development", ".env.production", "credentials", "credentials.json", "secrets.json", "id_rsa", "id_ed25519"}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
SENSITIVE_DIRS = {".ssh", ".aws", ".azure", "secrets"}


class ToolError(Exception):
    """Expected, user-safe tool failure."""


class WorkspaceTools:
    """Execute a small allowlist of development tools in a confined folder."""

    def __init__(self, workspace: str | Path):
        self.workspace = Path(workspace).expanduser().resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._tools = {
            "list_files": self.list_files,
            "read_file": self.read_file,
            "search_files": self.search_files,
            "write_file": self.write_file,
            "check_python_syntax": self.check_python_syntax,
        }

    @property
    def descriptions(self) -> list[dict[str, Any]]:
        """Return the tool catalogue exposed to the LLM."""
        return [
            {
                "name": "list_files",
                "description": "List project files under a relative directory (default '.').",
                "arguments": {"path": "relative directory path; optional, defaults to '.'"},
            },
            {
                "name": "read_file",
                "description": "Read a UTF-8 text file inside the workspace.",
                "arguments": {"path": "relative file path"},
            },
            {
                "name": "search_files",
                "description": "Find a literal, case-insensitive text query in supported text files.",
                "arguments": {"query": "text to search for", "path": "relative directory; optional, defaults to '.'"},
            },
            {
                "name": "write_file",
                "description": "Create a UTF-8 text file inside the workspace. Existing files are protected unless overwrite=true is explicitly supplied.",
                "arguments": {"path": "relative file path", "content": "complete file contents", "overwrite": "boolean; use true only when the task explicitly asks to modify/replace an existing file"},
            },
            {
                "name": "check_python_syntax",
                "description": "Parse a Python file with ast.parse without executing it.",
                "arguments": {"path": "relative .py file path"},
            },
        ]

    def execute(self, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
        """Call one allowlisted tool, capturing expected and unexpected errors."""
        if name not in self._tools:
            return {"ok": False, "error": f"Unknown tool '{name}'. Allowed tools: {', '.join(self._tools)}"}
        if not isinstance(arguments, dict):
            return {"ok": False, "error": "Tool arguments must be a JSON object."}
        try:
            data = self._tools[name](**arguments)
            return {"ok": True, "result": data}
        except (ToolError, OSError, UnicodeError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # Final safety net so a bad tool call does not crash the agent.
            return {"ok": False, "error": f"Unexpected {type(exc).__name__}: {exc}"}

    def _safe_path(self, raw_path: Any, *, allow_dot: bool = False) -> Path:
        if raw_path is None and allow_dot:
            raw_path = "."
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ToolError("A non-empty relative path is required.")
        if "\x00" in raw_path:
            raise ToolError("The path contains an invalid null character.")
        # Also reject Windows absolute paths when running tests on non-Windows hosts.
        windows_path = PureWindowsPath(raw_path)
        candidate_path = Path(raw_path)
        if candidate_path.is_absolute() or windows_path.is_absolute() or windows_path.drive:
            raise ToolError("Absolute paths are not allowed; use a path relative to the workspace.")
        if ".." in candidate_path.parts or ".." in windows_path.parts:
            raise ToolError("Path traversal ('..') is not allowed.")
        candidate = (self.workspace / candidate_path).resolve()
        try:
            candidate.relative_to(self.workspace)
        except ValueError as exc:
            raise ToolError("This path resolves outside the workspace and is not allowed.") from exc
        return candidate

    def _is_sensitive_path(self, file_path: Path) -> bool:
        try:
            relative_parts = [part.lower() for part in file_path.relative_to(self.workspace).parts]
        except ValueError:
            return True
        if any(part in SENSITIVE_DIRS for part in relative_parts[:-1]):
            return True
        name = file_path.name.lower()
        if name in SENSITIVE_NAMES or name.endswith(tuple(SENSITIVE_SUFFIXES)):
            return True
        # Treat dotenv variants as sensitive except the documented template file.
        if name.startswith(".env.") and name != ".env.example":
            return True
        return False

    def _walk_files(self, base: Path):
        for current, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = sorted(
                d for d in dirs
                if d not in IGNORED_DIRS
                and d.lower() not in SENSITIVE_DIRS
                and not (Path(current) / d).is_symlink()
            )
            for filename in sorted(files):
                file_path = Path(current) / filename
                if file_path.is_symlink() or not file_path.is_file() or self._is_sensitive_path(file_path):
                    continue
                yield file_path

    def list_files(self, path: str = ".") -> dict[str, Any]:
        base = self._safe_path(path, allow_dot=True)
        if not base.exists():
            raise ToolError(f"Directory not found: {path}")
        if not base.is_dir():
            raise ToolError(f"Not a directory: {path}")
        found: list[str] = []
        truncated = False
        for file_path in self._walk_files(base):
            try:
                relative = file_path.relative_to(self.workspace).as_posix()
            except ValueError:
                continue
            found.append(relative)
            if len(found) >= MAX_LIST_FILES:
                truncated = True
                break
        return {"directory": path, "files": found, "count": len(found), "truncated": truncated}

    def read_file(self, path: str) -> dict[str, Any]:
        file_path = self._safe_path(path)
        if self._is_sensitive_path(file_path):
            raise ToolError("Access to likely credential/secret files is blocked.")
        if not file_path.exists() or not file_path.is_file():
            raise ToolError(f"File not found: {path}")
        size = file_path.stat().st_size
        if size > MAX_READ_BYTES:
            raise ToolError(f"File is too large to read safely ({size} bytes; limit {MAX_READ_BYTES}).")
        content = file_path.read_text(encoding="utf-8")
        return {"path": file_path.relative_to(self.workspace).as_posix(), "content": content, "bytes": size}

    def search_files(self, query: str, path: str = ".") -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise ToolError("A non-empty search query is required.")
        base = self._safe_path(path, allow_dot=True)
        if not base.exists() or not base.is_dir():
            raise ToolError(f"Directory not found: {path}")
        needle = query.casefold()
        matches: list[dict[str, Any]] = []
        scanned = 0
        truncated = False
        for file_path in self._walk_files(base):
            if file_path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            scanned += 1
            if scanned > MAX_SEARCH_FILES:
                truncated = True
                break
            try:
                if file_path.stat().st_size > MAX_READ_BYTES:
                    continue
                text = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if needle in line.casefold():
                    matches.append({
                        "path": file_path.relative_to(self.workspace).as_posix(),
                        "line": line_number,
                        "text": line[:500],
                    })
                    if len(matches) >= 50:
                        truncated = True
                        break
            if len(matches) >= 50:
                break
        return {"query": query, "matches": matches, "match_count": len(matches), "files_scanned": min(scanned, MAX_SEARCH_FILES), "truncated": truncated}

    def write_file(self, path: str, content: str, overwrite: bool = False) -> dict[str, Any]:
        file_path = self._safe_path(path)
        if self._is_sensitive_path(file_path):
            raise ToolError("Writing to likely credential/secret files is blocked.")
        if not isinstance(overwrite, bool):
            raise ToolError("overwrite must be a JSON boolean (true or false).")
        if not isinstance(content, str):
            raise ToolError("File content must be a string.")
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_WRITE_BYTES:
            raise ToolError(f"Content is too large ({len(encoded)} bytes; limit {MAX_WRITE_BYTES}).")
        was_existing = file_path.exists()
        if was_existing and not overwrite:
            raise ToolError(f"File already exists: {path}. No changes made. Set overwrite=true only when the task explicitly requests an update.")
        if file_path.exists() and not file_path.is_file():
            raise ToolError(f"Cannot write to a directory: {path}")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # Resolve again after making parent directories to catch symlink changes.
        file_path = self._safe_path(path)
        if file_path.exists() and not overwrite:
            raise ToolError(f"File already exists: {path}. No changes made.")
        file_path.write_text(content, encoding="utf-8", newline="\n")
        return {
            "path": file_path.relative_to(self.workspace).as_posix(),
            "action": "updated" if was_existing else "created",
            "bytes_written": len(encoded),
        }

    def check_python_syntax(self, path: str) -> dict[str, Any]:
        file_path = self._safe_path(path)
        if self._is_sensitive_path(file_path):
            raise ToolError("Access to likely credential/secret files is blocked.")
        if file_path.suffix.lower() != ".py":
            raise ToolError("Syntax check only supports .py files.")
        if not file_path.exists() or not file_path.is_file():
            raise ToolError(f"Python file not found: {path}")
        if file_path.stat().st_size > MAX_READ_BYTES:
            raise ToolError(f"Python file exceeds the syntax-check size limit ({MAX_READ_BYTES} bytes).")
        source = file_path.read_text(encoding="utf-8")
        try:
            ast.parse(source, filename=str(file_path))
        except SyntaxError as exc:
            return {
                "path": file_path.relative_to(self.workspace).as_posix(),
                "valid": False,
                "error": exc.msg,
                "line": exc.lineno,
                "column": exc.offset,
            }
        return {"path": file_path.relative_to(self.workspace).as_posix(), "valid": True, "message": "Python syntax is valid. File was parsed but not executed."}
