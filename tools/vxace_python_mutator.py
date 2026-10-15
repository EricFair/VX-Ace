#!/usr/bin/env python3
"""Pinned Python Marshal backend for the existing narrow, copy-only patcher."""
from __future__ import annotations
import base64
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "_vendor"))
from rpgvxace_mcp import marshal_rb
from rpgvxace_mcp.rubytypes import RubyObject, RubyString, RubyHash, RubySymbol, Table, Color, Tone

VERSION = "0.26.0"
MAX_BYTES = 64 * 1024 * 1024


def load(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("64 MiB backend file limit exceeded")
    root, warnings = marshal_rb.load_with_warnings(raw)
    if warnings:
        raise ValueError("Codec warnings refuse mutation: " + "; ".join(warnings[:5]))
    # Admission is checked on every command, including direct low-level calls.
    if marshal_rb.dump(root) != raw:
        raise ValueError("Byte-identical no-op gate failed")
    return root, raw


class Encoder:
    def __init__(self):
        self.seen = {}

    def encode(self, obj):
        if obj is None or isinstance(obj, (bool, int)):
            return obj
        if isinstance(obj, float):
            return {"__float__": float(obj).hex()}
        if isinstance(obj, RubySymbol):
            return {"__symbol__": str(obj)}
        if isinstance(obj, RubyString):
            return {"__bytes__": base64.b64encode(obj.data).decode(), "ivars": self.encode(obj.ivars)}
        if isinstance(obj, (str, bytes)):
            return obj if isinstance(obj, str) else {"__binary__": base64.b64encode(obj).decode()}
        identity = id(obj)
        if identity in self.seen:
            return {"__ref__": self.seen[identity]}
        number = len(self.seen) + 1
        self.seen[identity] = number
        out = {"__id__": number}
        if isinstance(obj, list):
            out["__array__"] = [self.encode(x) for x in obj]
        elif isinstance(obj, RubyHash):
            out["__hash__"] = [[self.encode(k), self.encode(v)] for k, v in obj.pairs]
            out["default"] = self.encode(obj.default)
        elif isinstance(obj, dict):
            out["fields"] = {str(k): self.encode(v) for k, v in sorted(obj.items())}
        elif isinstance(obj, RubyObject):
            out["__class__"] = obj.cls
            out.update({k.lstrip("@"): self.encode(v) for k, v in sorted(obj.ivars.items())})
        elif isinstance(obj, Table):
            out.update(__class__="Table", dimensions=obj.dim, xsize=obj.xsize,
                       ysize=obj.ysize, zsize=obj.zsize, data=list(obj.data))
        elif isinstance(obj, (Color, Tone)):
            out.update(__class__=obj.CLASS_NAME, **obj.as_dict())
        else:
            out["__class__"] = type(obj).__name__
            out["opaque"] = {k: self.encode(v) for k, v in sorted(vars(obj).items())}
        return out


def inspect(root):
    encoded = Encoder().encode(root)
    raw = json.dumps(encoded, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return {"data": encoded, "semantic_sha256": hashlib.sha256(raw).hexdigest()}


def integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def object_by_id(root, identifier):
    integer(identifier, "object id", 1)
    if not isinstance(root, list):
        raise ValueError("Expected database array")
    matches = [x for x in root if isinstance(x, RubyObject) and x.get("id") == identifier]
    if len(matches) != 1:
        raise ValueError("Database id must resolve exactly once")
    return matches[0]


def convert(value, old=None):
    if isinstance(value, str):
        if isinstance(old, RubyString):
            ivars = dict(old.ivars)
            if ivars.get("E") is False and not value.isascii():
                raise ValueError("Cannot place non-ASCII text in an ASCII field")
            if "encoding" in ivars:
                raise ValueError("Explicit legacy encodings require separate review")
        else:
            ivars = {"E": True}
        return RubyString(value.encode("utf-8"), ivars)
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, list):
        previous = old if isinstance(old, list) else []
        return [convert(x, previous[i] if i < len(previous) else None) for i, x in enumerate(value)]
    raise ValueError("Only scalar values and event parameter arrays are supported")


def command_holder(root, mutation):
    scope = mutation["scope"]
    if scope == "map":
        events = root.get("events") if isinstance(root, RubyObject) else None
        if not isinstance(events, RubyHash):
            raise ValueError("Expected map event hash")
        event = events.get(integer(mutation["event_id"], "event id", 1))
        if not isinstance(event, RubyObject):
            raise ValueError("Event not found")
        owner = event
    elif scope == "troop":
        owner = object_by_id(root, mutation["troop_id"])
    elif scope == "common_event":
        return object_by_id(root, mutation["common_event_id"])
    else:
        raise ValueError("Unknown event scope")
    pages = owner.get("pages")
    index = integer(mutation["page"], "page", 1) - 1
    if not isinstance(pages, list) or index >= len(pages):
        raise ValueError("Page not found")
    return pages[index]


def apply(root, spec, *, source_path=None):
    mutation = spec["mutation"]
    kind = spec["type"]
    if kind == 'system_version':
        if not isinstance(root,RubyObject) or root.cls!='RPG::System': raise ValueError('Native System required for version update')
        old=root.get('version_id'); integer(old,'version id'); integer(mutation.get('expected_version'),'expected version')
        if old >= 2**31-1 or old != mutation.get('expected_version'): raise ValueError('Project version is stale or exhausted')
        root.set('version_id',old+1)
    elif kind == 'map_event':
        from vxace_map_events import apply as append_dialogue_event
        append_dialogue_event(root,mutation)
    elif kind == 'map_tile':
        from vxace_index_query import unlinked
        if source_path is None:raise ValueError('Upper tile writes require an actual native project source path')
        source_file=unlinked(source_path)
        context=spec.get('context')
        if source_file.parent.name!='Data' or not re.fullmatch(r'Map\d{3,6}\.rvdata2',source_file.name) or not isinstance(context,dict) or set(context)!={'rtp'} or (context['rtp'] is not None and not isinstance(context['rtp'],str)):
            raise ValueError('Upper tile native path/explicit asset context is unsupported')
        from vxace_upper_tiles import apply as paint_upper_tiles
        paint_upper_tiles(root,mutation,source_file.parent.parent,context['rtp'])
    elif kind == 'map_region':
        from vxace_map_regions import apply as region_apply
        region_apply(root, mutation)
    elif kind == 'database_entry':
        from vxace_database_entries import apply as entry_apply
        entry_apply(root, mutation)
    elif kind == "database":
        owner = object_by_id(root, mutation["id"])
        field = mutation["field"]
        if not isinstance(field, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field):
            raise ValueError("Unsafe field")
        key = "@" + field
        if key not in owner.ivars:
            raise ValueError("Database field does not already exist")
        old = owner.ivars[key]
        value = mutation["value"]
        if field == "id":
            raise ValueError("Identity field edits are disabled")
        valid = (isinstance(old, RubyString) and isinstance(value, str)
                 or type(old) is bool and type(value) is bool
                 or type(old) is int and type(value) is int
                 or isinstance(old, float) and type(value) in (int, float)
                 or old is None and value is None)
        if not valid:
            raise ValueError("Database scalar field type mismatch")
        if isinstance(old, float):
            value = float(value)
        if isinstance(value, (list, dict)) or isinstance(old, (list, RubyObject, RubyHash, Table)):
            raise ValueError("Python database edits are scalar-only")
        owner.ivars[key] = convert(value, old)
    elif kind == "event":
        from vxace_event_structure import ACTIONS, apply as structural_apply
        if mutation.get('action') in ACTIONS:
            structural_apply(root, mutation, convert, object_by_id)
            return
        holder = command_holder(root, mutation)
        commands = holder.get("list") if isinstance(holder, RubyObject) else None
        index = integer(mutation["command_index"], "command index")
        if not isinstance(commands, list) or index >= len(commands):
            raise ValueError("Command not found")
        command = commands[index]
        if not isinstance(command, RubyObject) or command.cls != "RPG::EventCommand":
            raise ValueError("Target is not an event command")
        params = command.get("parameters")
        if not isinstance(params, list):
            raise ValueError("Invalid parameter array")
        if mutation["action"] == "set_parameter":
            index = integer(mutation["parameter_index"], "parameter index")
            if index >= len(params):
                raise ValueError("Parameter index out of range")
            params[index] = convert(mutation["value"], params[index])
        elif mutation["action"] == "set_parameters":
            value = mutation["parameters"]
            if not isinstance(value, list):
                raise ValueError("Parameters must be an array")
            command.ivars["@parameters"] = convert(value, params)
        else:
            raise ValueError("Unsupported event mutation")
    elif kind == 'script_slot':
        from vxace_script_slots import apply as insert_script_slot
        insert_script_slot(root,mutation)
    elif kind == "scripts":
        index = integer(mutation["script_index"], "script index")
        if not isinstance(root, list) or index >= len(root):
            raise ValueError("Script index not found")
        entry = root[index]
        if not isinstance(entry, list) or len(entry) < 3 or not isinstance(entry[2], RubyString):
            raise ValueError("Invalid script archive entry")
        inflater = zlib.decompressobj()
        source = inflater.decompress(entry[2].data, MAX_BYTES + 1)
        if len(source) > MAX_BYTES or not inflater.eof or inflater.unused_data:
            raise ValueError("Script decompression limit exceeded or incomplete stream")
        search = mutation["search"].encode("utf-8")
        if not search or source.count(search) != 1:
            raise ValueError("Script search must occur exactly once")
        replacement = mutation["replace"].encode("utf-8")
        entry[2] = RubyString(zlib.compress(source.replace(search, replacement, 1)), entry[2].ivars)
    else:
        raise ValueError("Unsupported mutation type")


def write(root, output):
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = marshal_rb.dump(root)
    # Verify that the candidate decodes, without evaluating game code.
    marshal_rb.load(raw)
    fd, temporary = tempfile.mkstemp(prefix="vxace-", dir=output.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if not args or args[0] not in {"inspect", "roundtrip", "mutate"}:
            raise ValueError("Usage: inspect INPUT | roundtrip INPUT OUTPUT | mutate INPUT OUTPUT SPEC")
        expected = {"inspect": 2, "roundtrip": 3, "mutate": 4}[args[0]]
        if len(args) != expected:
            raise ValueError("Wrong argument count")
        root, raw = load(args[1])
        if args[0] == "inspect":
            result = inspect(root)
        else:
            if Path(args[1]).resolve() == Path(args[2]).resolve():
                raise ValueError("Input and output must differ")
            if args[0] == "mutate":
                apply(root, json.loads(Path(args[3]).read_text(encoding="utf-8")),source_path=args[1])
            write(root, args[2])
            result = {"status": "ok", "backend": "python", "version": VERSION}
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except Exception as exc:
        print(f"Python mutator refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
