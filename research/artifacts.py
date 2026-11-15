"""Read losslessly compressed evidence and separate frozen runs from live code."""

import gzip
import hashlib
import json
from pathlib import Path


def read_bytes(path):
    """Resolve a logical artifact name, preferring its original plain file."""
    path = Path(path)
    if path.is_file():
        return path.read_bytes()
    return gzip.decompress(path.with_name(path.name + ".gz").read_bytes())


def read_json(path):
    return json.loads(read_bytes(path))


def digest(path):
    """Hash original artifact bytes, never the gzip envelope."""
    return hashlib.sha256(read_bytes(path)).hexdigest()


def trace_paths(directory):
    """Return unique logical trace paths for plain and compressed attempts."""
    directory = Path(directory)
    paths = set(directory.glob("*-start-*.json"))
    paths.update(path.with_suffix("") for path in directory.glob("*-start-*.json.gz"))
    return sorted(paths)


def verify_source(root, name, expected, archive=None, *, completed=False):
    """An unfinished plan requires current source; a completed run has an archive.

    Numerical verification still uses the current model/circuit independently.
    This check proves which source was recorded, not that later code is identical.
    """
    if completed and archive is not None:
        if digest(archive) == expected:
            return
    elif digest(Path(root) / name) == expected:
        return
    raise ValueError(f"recorded source changed without a matching archive: {name}")


def verify_preserved(root, manifest, *, completed=False):
    """Protect evidence, without requiring live docs/tests to remain frozen forever.

    Before completion every recorded file is protected. After completion the
    original manifest remains historical evidence; scientific data/results and
    original model implementations are still checked byte-for-byte. Research
    runners are checked separately against their frozen source archives.
    """
    checked = 0
    for name, expected in manifest.items():
        path = Path(name)
        scientific = (name.startswith(("results/", "data/")) and path.suffix != ".md")
        original_model = name in ("scoring.py", "classical.py", "quantum.py")
        if completed and not (scientific or original_model):
            continue
        if digest(Path(root) / name) != expected:
            raise ValueError(f"preserved scientific file changed: {name}")
        checked += 1
    return checked
