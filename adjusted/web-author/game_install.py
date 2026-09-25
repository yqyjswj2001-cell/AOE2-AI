"""Explicit post-build installer for completed AOE2-AI projects.

Creation and build never depend on a local game installation. This module is used
only after an explicit user request to install a completed script into the local
AoE2DE game directory.

The installer never edits the official PromiDE.per2 or Promisory files. It reads
those files only to reproduce the installed game's loader order and to verify the
frozen repository baseline matches the installed game version.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_BASELINE = ROOT / "official/raw/Promisory"
SCRIPT_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}\Z")
LOAD = re.compile(r'(\(load\s+")Promisory[\\/](?P<target>[^"]+)("\))', re.IGNORECASE)
LOAD_LINE = re.compile(r'^\s*\(load\s+"Promisory[\\/][A-Za-z0-9_-]+(?:\.per)?"\)\s*(?:;.*)?$', re.IGNORECASE)
CONDITION = re.compile(r'^\s*#(?:load-if-defined|load-if-not-defined)\s+[A-Za-z0-9_-]+\s*(?:;.*)?$', re.IGNORECASE)
CONTROL = re.compile(r'^\s*#(?:else|end-if)\s*(?:;.*)?$', re.IGNORECASE)
TARGET = re.compile(r"[A-Za-z0-9_-]+(?:\.per)?\Z", re.IGNORECASE)


class GameInstallError(ValueError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GameInstallError("Cannot read completed project metadata") from exc


def _inside(path: Path, root: Path, label: str) -> Path:
    path = Path(path).resolve()
    root = Path(root).resolve()
    if path == root or not path.is_relative_to(root):
        raise GameInstallError(label + " is outside the completed project")
    return path


def _verify_build_artifacts(project: Path, build: dict) -> Path:
    output = _inside(Path(build.get("path", "")), project, "Build output")
    hashes = build.get("artifact_hashes")
    if not isinstance(hashes, dict) or not hashes:
        raise GameInstallError("Completed build is missing artifact hashes")
    for relative, expected in hashes.items():
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise GameInstallError("Completed build has invalid artifact hashes")
        target = (output / relative).resolve()
        if not target.is_relative_to(output) or not target.is_file():
            raise GameInstallError("Completed build artifact is missing: " + relative)
        if _sha256(target.read_bytes()) != expected:
            raise GameInstallError("Completed build changed after validation: " + relative)
    return output


def _read_modules(project: Path) -> tuple[str, dict[str, bytes], str]:
    project = Path(project).resolve()
    state = _parse_json(project / "project.json")
    build = state.get("build")
    if state.get("status") != "completed" or not isinstance(build, dict):
        raise GameInstallError("Install requires a completed build")
    script_name = build.get("script_name")
    if not isinstance(script_name, str) or not SCRIPT_NAME.fullmatch(script_name):
        raise GameInstallError("Completed build has an invalid script name")
    output = _verify_build_artifacts(project, build)
    output_mode = build.get("output_mode", "raw_scripts")

    modules: dict[str, bytes] = {}
    if output_mode == "raw_scripts":
        root = _inside(Path(build.get("script_root", "")), output, "Raw script directory")
        entries = list(root.iterdir())
        if len(entries) != 36 or any(not path.is_file() or path.suffix.lower() != ".per" for path in entries):
            raise GameInstallError("Raw build must contain exactly 36 PER files")
        for path in entries:
            key = path.name.casefold()
            if key in modules:
                raise GameInstallError("Raw build contains duplicate module names")
            modules[key] = path.read_bytes()
    elif output_mode == "share_package":
        package = _inside(Path(build.get("package_file", "")), output, "Share package")
        try:
            with zipfile.ZipFile(package) as archive:
                try:
                    manifest = json.loads(archive.read("manifest.json"))
                except (KeyError, ValueError) as exc:
                    raise GameInstallError("Share package manifest is missing or invalid") from exc
                if manifest.get("script_name") != script_name or manifest.get("script_files") != 36:
                    raise GameInstallError("Share package metadata does not match the completed build")
                prefix = script_name + "/"
                candidates = []
                for info in archive.infolist():
                    if info.is_dir() or not info.filename.lower().endswith(".per"):
                        continue
                    if not info.filename.startswith(prefix):
                        raise GameInstallError("Share package contains a PER file outside the script directory")
                    relative = info.filename[len(prefix):]
                    if not relative or "/" in relative or "\\" in relative:
                        raise GameInstallError("Share package contains an invalid module path")
                    candidates.append((relative, info))
                if len(candidates) != 36:
                    raise GameInstallError("Share package must contain exactly 36 PER files")
                for name, info in candidates:
                    key = name.casefold()
                    if key in modules:
                        raise GameInstallError("Share package contains duplicate module names")
                    modules[key] = archive.read(info)
        except zipfile.BadZipFile as exc:
            raise GameInstallError("Share package is not a valid ZIP file") from exc
    else:
        raise GameInstallError("Completed build has an unsupported output mode")

    if len(modules) != 36:
        raise GameInstallError("Install requires exactly 36 rendered modules")
    return script_name, modules, output_mode


def _steam_roots(environ, home: Path):
    roots = []
    explicit = environ.get("STEAM_DIR")
    if explicit:
        roots.append(Path(explicit).expanduser())
    roots.extend([
        home / ".steam/steam",
        home / ".local/share/Steam",
        home / "Library/Application Support/Steam",
    ])
    for key in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        if environ.get(key):
            roots.append(Path(environ[key]) / "Steam")
    if os.name == "nt":
        try:
            import winreg
            for hive, key, value in (
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            ):
                try:
                    with winreg.OpenKey(hive, key) as handle:
                        roots.append(Path(winreg.QueryValueEx(handle, value)[0]))
                except OSError:
                    pass
        except ImportError:
            pass
    return list(dict.fromkeys(Path(path).expanduser() for path in roots))


def _steam_libraries(steam_root: Path):
    libraries = [steam_root]
    vdf = steam_root / "steamapps/libraryfolders.vdf"
    try:
        text = vdf.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return libraries
    for match in re.finditer(r'"path"\s*"([^"]+)"', text):
        libraries.append(Path(match.group(1).replace("\\\\", "\\")))
    return list(dict.fromkeys(libraries))


def _game_paths(root: Path):
    root = Path(root).expanduser().resolve()
    promide = root / "resources/_common/drs/gamedata_x2/PromiDE.per2"
    ai_root = root / "resources/_common/ai"
    promisory = ai_root / "Promisory"
    if not promide.is_file() or not ai_root.is_dir() or not promisory.is_dir():
        raise GameInstallError(
            "Not a usable AoE2DE install root; expected resources/_common/drs/gamedata_x2/PromiDE.per2 "
            "and resources/_common/ai/Promisory"
        )
    return root, promide, ai_root, promisory


def find_game_root(game_root=None, *, environ=None, home=None) -> Path:
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)

    if game_root is not None:
        return _game_paths(Path(game_root))[0]

    explicit_root = environ.get("AOE2DE_ROOT")
    if explicit_root:
        return _game_paths(Path(explicit_root))[0]

    explicit_loader = environ.get("AOE2DE_PROMIDE_PER2")
    if explicit_loader:
        loader = Path(explicit_loader).expanduser().resolve()
        if not loader.is_file():
            raise GameInstallError("AOE2DE_PROMIDE_PER2 does not point to a file")
        try:
            candidate = loader.parents[4]
        except IndexError as exc:
            raise GameInstallError("Cannot derive the AoE2DE root from AOE2DE_PROMIDE_PER2") from exc
        return _game_paths(candidate)[0]

    candidates = []
    for steam in _steam_roots(environ, home):
        for library in _steam_libraries(steam):
            candidates.append(library / "steamapps/common/AoE2DE")
    valid = []
    for candidate in candidates:
        try:
            root = _game_paths(candidate)[0]
        except GameInstallError:
            continue
        if root not in valid:
            valid.append(root)
    if len(valid) == 1:
        return valid[0]
    if len(valid) > 1:
        raise GameInstallError("Multiple AoE2DE installations were found; pass --game-root to choose the intended game folder")
    raise GameInstallError(
        "AoE2DE installation was not found. Set AOE2DE_ROOT to the game folder or pass --game-root."
    )


def _parse_promide(raw: bytes) -> tuple[str, list[str]]:
    if not raw or len(raw) > 64 * 1024:
        raise GameInstallError("Installed PromiDE.per2 has an unexpected size")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise GameInstallError("Installed PromiDE.per2 is not plain text") from exc
    if "\x00" in text:
        raise GameInstallError("Installed PromiDE.per2 contains NUL bytes")

    loads = []
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        if LOAD_LINE.fullmatch(line):
            match = LOAD.search(line)
            target = match.group("target")
            if not TARGET.fullmatch(target):
                raise GameInstallError(f"PromiDE.per2 line {number} has an unsafe load target")
            loads.append(target)
            continue
        if CONDITION.fullmatch(line) or CONTROL.fullmatch(line):
            continue
        raise GameInstallError(f"PromiDE.per2 line {number} is not a supported load/control line")
    if len(loads) < 10:
        raise GameInstallError("Installed PromiDE.per2 contains too few Promisory loads")
    return text, loads


def _module_name(target: str) -> str:
    return target if target.lower().endswith(".per") else target + ".per"


def _casefold_per_files(root: Path):
    result = {}
    for path in root.glob("*.per"):
        key = path.name.casefold()
        if key in result:
            raise GameInstallError("Duplicate PER filenames in " + str(root))
        result[key] = path
    return result


def _verify_game_baseline(promisory: Path, modules: dict[str, bytes], targets: list[str]):
    baseline = _casefold_per_files(OFFICIAL_BASELINE)
    game = _casefold_per_files(promisory)
    if len(baseline) != 36 or set(modules) != set(baseline):
        raise GameInstallError("Completed build does not match the repository's 36-module AI baseline")

    mismatches = []
    for key, baseline_path in baseline.items():
        game_path = game.get(key)
        if game_path is None:
            mismatches.append(baseline_path.name + " (missing)")
        elif baseline_path.read_bytes() != game_path.read_bytes():
            mismatches.append(baseline_path.name + " (different)")
    if mismatches:
        shown = ", ".join(mismatches[:8]) + (" ..." if len(mismatches) > 8 else "")
        raise GameInstallError(
            "Installed game AI baseline differs from this repository. Update the repository baseline before direct install: "
            + shown
        )

    for target in targets:
        name = _module_name(target)
        if name.casefold() not in modules:
            raise GameInstallError("Installed loader references a module missing from this build: " + name)


def _write_layout(root: Path, script_name: str, modules: dict[str, bytes], loader_text: str, targets: list[str]):
    root.mkdir(parents=True, exist_ok=True)
    module_root = root / script_name
    module_root.mkdir()
    baseline = _casefold_per_files(OFFICIAL_BASELINE)
    for key, data in modules.items():
        # Preserve the canonical repository filename when available.
        name = baseline[key].name if key in baseline else key
        (module_root / name).write_bytes(data)

    rewritten = LOAD.sub(lambda match: match.group(1) + script_name + "\\" + match.group("target") + match.group(3), loader_text)
    (root / (script_name + ".per")).write_text(rewritten, encoding="utf-8")
    (root / (script_name + ".ai")).write_bytes(b"")
    _verify_layout(root, script_name, modules, targets)


def _verify_layout(root: Path, script_name: str, modules: dict[str, bytes], targets: list[str]):
    marker = root / (script_name + ".ai")
    entry = root / (script_name + ".per")
    module_root = root / script_name
    if not marker.is_file() or marker.stat().st_size != 0:
        raise GameInstallError("Custom AI marker file is missing or not empty")
    if not entry.is_file() or not module_root.is_dir():
        raise GameInstallError("Custom AI entrypoint or module directory is missing")

    generated = entry.read_text(encoding="utf-8")
    if "Promisory\\" in generated or "Promisory/" in generated:
        raise GameInstallError("Custom AI entrypoint still points to the official Promisory directory")
    found = re.findall(r'\(load\s+"' + re.escape(script_name) + r'[\\/]([^"]+)"\)', generated, re.IGNORECASE)
    if len(found) != len(targets):
        raise GameInstallError("Custom AI entrypoint did not rewrite every official load")
    files = _casefold_per_files(module_root)
    if len(files) != 36 or set(files) != set(modules):
        raise GameInstallError("Installed custom AI module set is incomplete")
    for key, data in modules.items():
        if files[key].read_bytes() != data:
            raise GameInstallError("Installed module verification failed: " + files[key].name)
    for target in found:
        if _module_name(target).casefold() not in files:
            raise GameInstallError("Custom AI entrypoint points to a missing module: " + target)


def _backup_existing(ai_root: Path, project: Path, script_name: str):
    targets = [ai_root / (script_name + ".ai"), ai_root / (script_name + ".per"), ai_root / script_name]
    existing = [path for path in targets if path.exists() or path.is_symlink()]
    if not existing:
        return None
    if any(path.is_symlink() for path in existing):
        raise GameInstallError("Refusing to replace a symlinked existing custom AI")
    backup = project / "install-backups" / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    backup.mkdir(parents=True)
    for path in existing:
        target = backup / path.name
        if path.is_dir():
            shutil.copytree(path, target)
        elif path.is_file():
            shutil.copy2(path, target)
        else:
            raise GameInstallError("Existing custom AI path has an unsupported type: " + str(path))
    return backup


def _restore_backup(ai_root: Path, backup: Path | None, script_name: str):
    for path in (ai_root / (script_name + ".ai"), ai_root / (script_name + ".per"), ai_root / script_name):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
        else:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
    if backup is None or not backup.is_dir():
        return
    for source in backup.iterdir():
        target = ai_root / source.name
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)


def install_project(project: Path, *, game_root=None, environ=None, home=None) -> dict:
    project = Path(project).resolve()
    script_name, modules, output_mode = _read_modules(project)
    game_root = find_game_root(game_root, environ=environ, home=home)
    game_root, promide, ai_root, promisory = _game_paths(game_root)

    raw_loader = promide.read_bytes()
    loader_text, targets = _parse_promide(raw_loader)
    _verify_game_baseline(promisory, modules, targets)

    staging = Path(tempfile.mkdtemp(prefix=".aoe2-ai-stage-", dir=ai_root))
    backup = None
    modified = False
    try:
        _write_layout(staging, script_name, modules, loader_text, targets)
        backup = _backup_existing(ai_root, project, script_name)

        target_dir = ai_root / script_name
        target_entry = ai_root / (script_name + ".per")
        target_marker = ai_root / (script_name + ".ai")
        modified = True
        if target_dir.is_dir() and not target_dir.is_symlink():
            shutil.rmtree(target_dir)
        elif target_dir.exists() or target_dir.is_symlink():
            target_dir.unlink()
        os.replace(staging / script_name, target_dir)
        os.replace(staging / (script_name + ".per"), target_entry)
        os.replace(staging / (script_name + ".ai"), target_marker)
        _verify_layout(ai_root, script_name, modules, targets)
    except (OSError, GameInstallError) as exc:
        if modified:
            try:
                _restore_backup(ai_root, backup, script_name)
            except OSError:
                pass
        if isinstance(exc, GameInstallError):
            raise
        raise GameInstallError(
            "Direct install failed while writing the game directory. Close the game and verify write permission: " + str(exc)
        ) from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return {
        "installed": True,
        "verification": "PASS",
        "script_name": script_name,
        "expected_ai_type_name": script_name,
        "source_output_mode": output_mode,
        "game_root": str(game_root),
        "ai_root": str(ai_root),
        "marker": str(ai_root / (script_name + ".ai")),
        "entrypoint": str(ai_root / (script_name + ".per")),
        "module_directory": str(ai_root / script_name),
        "module_files": 36,
        "official_files_modified": False,
        "backup": str(backup) if backup is not None else None,
    }
