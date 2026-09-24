#!/usr/bin/env python3
"""Project-local answer writer. Standard library only; no fixed code or model calls."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

MAX_BYTES = 2 * 1024 * 1024
MODULE = re.compile(r"[A-Za-z0-9_-]+(?:\.json)?\Z")


def safe(path):
    path = Path(os.path.abspath(path))
    if path.resolve() != path:
        raise ValueError("Symlink or junction paths are not allowed")
    return path


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def load(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError("JSON exceeds 2 MiB")
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite number")))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


@contextmanager
def writer_lock(project):
    path = safe(project / ".answer-write.lock")
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if not stream.tell():
            stream.write(b"0"); stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def validate_partial(module, values, contract):
    """Check public constraints only. Defer relations with unanswered members."""
    if contract.get("schema") != "aoe2-author-parameter-contracts-v1":
        raise ValueError("Unsupported parameter contract")
    deferred = 0
    for row in contract.get("constraints", []):
        if row["module"] != module:
            continue
        keys = row["keys"]
        if not keys or not set(keys) <= set(values):
            raise ValueError("Parameter contract keys differ")
        subset = [values[key] for key in keys]
        kind = row["kind"]
        if kind in {"minimum", "range", "less_than"}:
            known = [value for value in subset if value is not None]
            if len(known) != len(subset):
                deferred += 1
            if kind == "minimum":
                ok = all(value >= row["value"] for value in known)
            elif kind == "range":
                ok = all(row["minimum"] <= value <= row["maximum"] for value in known)
            else:
                ok = all(value < row["value"] for value in known)
        else:
            if any(value is None for value in subset):
                deferred += 1
                continue
            if kind == "sum_equal":
                ok = sum(subset) == row["value"]
            elif kind == "less_equal":
                ok = len(subset) == 2 and subset[0] <= subset[1]
            elif kind == "equal":
                ok = len(set(subset)) == 1
            elif kind == "forbidden_pair":
                ok = subset != row["values"]
            else:
                raise ValueError("Unsupported constraint: " + kind)
        if not ok:
            raise ValueError("Constraint failed: " + row["reason"] + "; keys=" + ", ".join(keys))
    return deferred


def context(project, module):
    project = safe(project)
    if not isinstance(module, str) or not MODULE.fullmatch(module):
        raise ValueError("Use a module name, not a path")
    name = module if module.endswith(".json") else module + ".json"
    task = load(safe(project / "author-session/task.json").read_bytes())
    state = load(safe(project / "project.json").read_bytes())
    if (task.get("schema") != "aoe2-author-task-v1" or task.get("project_id") != state.get("project_id")
            or task.get("task_sha256") != state.get("task_sha256")
            or task.get("input_sha256") != state.get("input_sha256")
            or task.get("request") != state.get("request")):
        raise ValueError("Author handoff is stale; ask the host to refresh handoff")
    if state.get("status") not in {"authoring", "invalid", "ready"} or state["request"]["civilization"] == "auto":
        raise ValueError("Answers may be submitted only after civilization is frozen and before build")
    root = safe(project / "author-input")
    manifest = load(safe(root / "manifest.json").read_bytes())
    if digest(encoded(manifest)) != state["input_sha256"]:
        raise ValueError("Author manifest changed")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != set(manifest["files"]) | {"manifest.json"}:
        raise ValueError("Unexpected files in read-only input; keep patches in submissions")
    def asset(relative):
        raw = safe(root / relative).read_bytes()
        if digest(raw) != manifest["files"].get(relative):
            raise ValueError("Read-only input changed: " + relative)
        return load(raw)
    nulls = asset("answers/" + name)
    if not isinstance(nulls, dict) or any(value is not None for value in nulls.values()):
        raise ValueError("Input answer sheet must remain all null")
    contract = asset("PARAMETER_CONSTRAINTS.json")
    output = safe(project / "answers" / name)
    raw = output.read_bytes()
    current = load(raw)
    if not isinstance(current, dict) or set(current) != set(nulls):
        raise ValueError("Stored answer keys differ; do not overwrite the original sheet")
    if any(value is not None and type(value) is not int for value in current.values()):
        raise ValueError("Stored answers contain non-integers")
    return output, current, contract, raw


def submit_patch(project, patch, *, status_only=False):
    project = safe(project)
    if not isinstance(patch, dict) or not set(patch) <= {"module", "answers", "expected_sha256"}:
        raise ValueError("Patch fields: module, answers, optional expected_sha256")
    with writer_lock(project):
        output, current, contract, original = context(project, patch.get("module"))
        before = digest(original)
        if status_only:
            return {"ok": True, "module": output.stem, "sha256": before,
                    "filled": sum(v is not None for v in current.values()), "total": len(current)}
        changes = patch.get("answers")
        if not isinstance(changes, dict) or not changes or not set(changes) <= set(current):
            raise ValueError("Submit only a nonempty subset of this module's existing keys")
        if any(type(value) is not int for value in changes.values()):
            raise ValueError("Answers must be integers; null, boolean, text and decimals are rejected")
        merged = {**current, **changes}
        changed = [key for key in changes if changes[key] != current[key]]
        if changed:
            expected = patch.get("expected_sha256")
            replacing = any(current[key] is not None for key in changed)
            if (expected is not None or replacing) and expected != before:
                raise ValueError("Answer revision conflict: get module status, then submit expected_sha256")
        deferred = validate_partial(output.stem + ".per", merged, contract)
        raw = encoded(merged) if changed else original
        if changed:
            temporary = safe(project / (".answer-write-" + uuid.uuid4().hex + ".tmp"))
            try:
                with temporary.open("xb") as stream:
                    stream.write(raw); stream.flush(); os.fsync(stream.fileno())
                if digest(output.read_bytes()) != before:
                    raise ValueError("Answers changed outside the writer; patch was not applied")
                os.replace(temporary, output)
            finally:
                temporary.unlink(missing_ok=True)
        return {"ok": True, "module": output.stem, "changed": len(changed), "sha256": digest(raw),
                "filled": sum(v is not None for v in merged.values()), "total": len(merged),
                "deferred_constraints": deferred, "final_validation_required": True}


def complete_answers(project):
    """Author calls this after its own review, not merely when the last field is filled."""
    project = safe(project)
    with writer_lock(project):
        manifest = load(safe(project / "author-input/manifest.json").read_bytes())
        names = sorted(Path(name).name for name in manifest["files"] if name.startswith("answers/"))
        actual = sorted(p.name for p in safe(project / "answers").iterdir())
        if names != actual or not names:
            raise ValueError("Answer file set differs from the manifest")
        hashes = {}
        total = 0
        for name in names:
            output, values, contract, raw = context(project, name)
            if any(value is None for value in values.values()):
                raise ValueError(name + ": unfinished parameters; complete the author review before marking done")
            validate_partial(output.stem + ".per", values, contract)
            total += len(values)
            hashes[name] = digest(raw)
        if total != manifest["dynamic_slots"]:
            raise ValueError("Answer count differs from the manifest")
        if any(digest(safe(project / "answers" / name).read_bytes()) != value for name, value in hashes.items()):
            raise ValueError("Answers changed during completion check")
        task = load(safe(project / "author-session/task.json").read_bytes())
        receipt = {"schema": "aoe2-author-complete-v1", "project_id": task["project_id"],
                   "task_sha256": task["task_sha256"],
                   "answers_sha256": digest(encoded({"files": hashes, "names": names, "errors": []})),
                   "filled": total, "final_validation_required": True}
        target = safe(project / "author-session/completion.json")
        temporary = safe(project / (".author-complete-" + uuid.uuid4().hex + ".tmp"))
        try:
            temporary.write_bytes(encoded(receipt)); os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return {"ok": True, **receipt}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--patch", type=Path, help="JSON with module and this group's answers")
    group.add_argument("--status", metavar="MODULE", help="Return current module hash and progress")
    group.add_argument("--complete", action="store_true", help="Mark finished after author review; final host validation remains required")
    args = parser.parse_args(argv)
    try:
        here = safe(Path(__file__).absolute()).parent
        if here.name != "author-session":
            raise ValueError("Run the project-local author-session/submit_answers.py from the handoff")
        if args.complete:
            result = complete_answers(here.parent)
        else:
            if args.patch and not safe(args.patch).is_relative_to(safe(here.parent / "submissions")):
                raise ValueError("Patch JSON must be stored under this project's submissions directory")
            patch = {"module": args.status} if args.status else load(safe(args.patch).read_bytes())
            result = submit_patch(here.parent, patch, status_only=bool(args.status))
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
