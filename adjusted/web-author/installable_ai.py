"""Build a custom AoE2DE AI entrypoint from the installed game's own PromiDE.per2.

The loader order is never guessed.  A package is emitted only when every module
referenced by the installed entrypoint matches this repository's frozen official
Promisory baseline byte-for-byte.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re

SCRIPT_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}\Z")
LOAD = re.compile(r'(\(load\s+")Promisory[\\/](?P<target>[^"]+)("\))', re.IGNORECASE)
LOAD_LINE = re.compile(r'^\s*\(load\s+"Promisory[\\/][A-Za-z0-9_-]+(?:\.per)?"\)\s*(?:;.*)?$', re.IGNORECASE)
CONDITION = re.compile(r'^\s*#(?:load-if-defined|load-if-not-defined)\s+[A-Za-z0-9_-]+\s*(?:;.*)?$', re.IGNORECASE)
CONTROL = re.compile(r'^\s*#(?:else|end-if)\s*(?:;.*)?$', re.IGNORECASE)
TARGET = re.compile(r"[A-Za-z0-9_-]+(?:\.per)?\Z", re.IGNORECASE)


class InstallableAIError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _steam_roots(environ, home):
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
    return list(dict.fromkeys(Path(p).expanduser() for p in roots))


def _steam_libraries(steam_root: Path):
    libraries = [steam_root]
    vdf = steam_root / "steamapps/libraryfolders.vdf"
    try:
        text = vdf.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return libraries
    for match in re.finditer(r'"path"\s*"([^"]+)"', text):
        value = match.group(1).replace("\\\\", "\\")
        libraries.append(Path(value))
    return list(dict.fromkeys(libraries))


def find_promide(*, environ=None, home=None) -> Path:
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    explicit = environ.get("AOE2DE_PROMIDE_PER2")
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_file():
            return path.resolve()
        raise InstallableAIError("AOE2DE_PROMIDE_PER2 does not point to a file")
    game_root = environ.get("AOE2DE_ROOT")
    if game_root:
        path = Path(game_root).expanduser() / "resources/_common/drs/gamedata_x2/PromiDE.per2"
        if path.is_file():
            return path.resolve()
        raise InstallableAIError("AOE2DE_ROOT does not contain resources/_common/drs/gamedata_x2/PromiDE.per2")
    candidates = []
    for steam in _steam_roots(environ, home):
        for library in _steam_libraries(steam):
            candidates.append(library / "steamapps/common/AoE2DE/resources/_common/drs/gamedata_x2/PromiDE.per2")
    for path in candidates:
        if path.is_file():
            return path.resolve()
    raise InstallableAIError(
        "AoE2DE PromiDE.per2 was not found. Set AOE2DE_PROMIDE_PER2 to the installed game's "
        "resources/_common/drs/gamedata_x2/PromiDE.per2"
    )


def parse_promide(raw: bytes) -> tuple[str, list[str]]:
    if not raw or len(raw) > 64 * 1024:
        raise InstallableAIError("PromiDE.per2 has an unexpected size")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InstallableAIError("PromiDE.per2 is not plain text") from exc
    if "\x00" in text:
        raise InstallableAIError("PromiDE.per2 contains NUL bytes")
    loads = []
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        if LOAD_LINE.fullmatch(line):
            match = LOAD.search(line)
            target = match.group("target")
            if not TARGET.fullmatch(target):
                raise InstallableAIError(f"PromiDE.per2 line {number} has an unsafe load target")
            loads.append(target)
            continue
        if CONDITION.fullmatch(line) or CONTROL.fullmatch(line):
            continue
        raise InstallableAIError(f"PromiDE.per2 line {number} is not a load/control line")
    if len(loads) < 10:
        raise InstallableAIError("PromiDE.per2 contains too few Promisory loads")
    return text, loads


def _module_name(target: str) -> str:
    return target if target.lower().endswith(".per") else target + ".per"


def package_installable_ai(modules: Path, script_name: str, output: Path, official_baseline: Path,
                           *, promide: Path | None = None, game_promisory: Path | None = None,
                           environ=None, home=None) -> dict:
    modules = Path(modules)
    output = Path(output)
    official_baseline = Path(official_baseline)
    if not SCRIPT_NAME.fullmatch(script_name):
        raise InstallableAIError("Invalid AI script name")
    rendered = {path.name.casefold(): path for path in modules.glob("*.per") if path.is_file()}
    if len(rendered) != 36:
        raise InstallableAIError("Installable package requires exactly 36 rendered PER modules")

    promide = Path(promide).resolve() if promide is not None else find_promide(environ=environ, home=home)
    raw = promide.read_bytes()
    text, targets = parse_promide(raw)
    if game_promisory is None:
        try:
            game_promisory = promide.parents[2] / "ai/Promisory"
        except IndexError as exc:
            raise InstallableAIError("Cannot locate the installed Promisory directory from PromiDE.per2") from exc
    game_promisory = Path(game_promisory)

    loaded = []
    mismatches = []
    for target in targets:
        name = _module_name(target)
        key = name.casefold()
        if key not in rendered:
            raise InstallableAIError("Installed PromiDE.per2 loads a module missing from this build: " + name)
        repo_file = official_baseline / rendered[key].name
        game_file = game_promisory / rendered[key].name
        try:
            repo_bytes, game_bytes = repo_file.read_bytes(), game_file.read_bytes()
        except OSError:
            mismatches.append(name + " (missing)")
            continue
        if repo_bytes != game_bytes:
            mismatches.append(name + " (different)")
        loaded.append(rendered[key].name)
    if mismatches:
        shown = ", ".join(mismatches[:8]) + (" ..." if len(mismatches) > 8 else "")
        raise InstallableAIError(
            "Installed DE AI baseline differs from official/raw; refresh the frozen official baseline before packaging: " + shown
        )

    rewritten = LOAD.sub(lambda m: m.group(1) + script_name + "\\" + m.group("target") + m.group(3), text)
    ai_root = output / "resources/_common/ai"
    module_root = ai_root / script_name
    ai_root.mkdir(parents=True)
    module_root.mkdir()
    for source in sorted(rendered.values(), key=lambda p: p.name.casefold()):
        (module_root / source.name).write_bytes(source.read_bytes())
    entrypoint = ai_root / (script_name + ".per")
    marker = ai_root / (script_name + ".ai")
    entrypoint.write_bytes(rewritten.encode("utf-8"))
    marker.write_bytes(b"")

    # Final structural check against the generated paths.
    generated_text = entrypoint.read_text(encoding="utf-8")
    generated_loads = re.findall(r'\(load\s+"' + re.escape(script_name) + r'[\\/]([^"]+)"\)', generated_text, re.IGNORECASE)
    if len(generated_loads) != len(targets) or "Promisory\\" in generated_text or "Promisory/" in generated_text:
        raise InstallableAIError("Generated entrypoint did not rewrite every official load")
    for target in generated_loads:
        if not (module_root / _module_name(target)).is_file():
            raise InstallableAIError("Generated entrypoint points to a missing module: " + target)
    if marker.stat().st_size != 0:
        raise InstallableAIError("AoE2 AI marker file must be empty")

    loaded_set = {name.casefold() for name in loaded}
    unreferenced = [path.name for key, path in sorted(rendered.items()) if key not in loaded_set]
    return {
        "entrypoint_validation": "PASS",
        "entrypoint_source": str(promide),
        "official_entrypoint_sha256": sha256(raw),
        "loaded_modules": loaded,
        "unreferenced_modules": unreferenced,
        "ai_root": "resources/_common/ai",
        "entrypoint": "resources/_common/ai/" + script_name + ".per",
        "marker": "resources/_common/ai/" + script_name + ".ai",
        "module_directory": "resources/_common/ai/" + script_name,
    }
