import hashlib
from pathlib import Path
from typing import Optional
from typing import Iterable


def md5_file(path: str) -> str:
    """Compute MD5 hex digest for a file in streaming fashion."""
    h = hashlib.md5()
    p = Path(path)
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def phash_stub(path: str) -> Optional[str]:
    """A tiny perceptual-hash stub. If Pillow is available, compute a small
    average-hash-ish fingerprint; otherwise return None.

    This is intentionally lightweight for tests — a more robust implementation
    can be added later (imagehash, perceptual hashing libs).
    """
    try:
        from PIL import Image
    except Exception:
        return None

    try:
        img = Image.open(path)
    except Exception:
        return None

    try:
        img = img.convert("L").resize((8, 8))
        pixels = list(img.getdata())
    except Exception:
        return None
    avg = sum(pixels) / len(pixels)
    bits = ["1" if p >= avg else "0" for p in pixels]
    # return as hex string
    bitstring = "".join(bits)
    return hex(int(bitstring, 2))[2:]


def _hex_to_bitstring(hexstr: str, bits: int = 64) -> str:
    """Convert a hex string (without 0x) to a zero-padded bitstring."""
    try:
        i = int(hexstr, 16)
    except Exception:
        return ""
    b = bin(i)[2:].rjust(bits, "0")
    return b[-bits:]


def hamming_distance(hex1: str, hex2: str, bits: int = 64) -> int:
    """Compute Hamming distance between two hex phash strings (default 64-bit)."""
    b1 = _hex_to_bitstring(hex1, bits)
    b2 = _hex_to_bitstring(hex2, bits)
    if not b1 or not b2:
        return bits
    return sum(ch1 != ch2 for ch1, ch2 in zip(b1, b2))


def cluster_by_hamming(items: Iterable[tuple[int, str]], threshold: int = 5, bits: int = 64) -> list[list[int]]:
    """Simple greedy clustering: items is iterable of (id, phash_hex). Returns list of clusters as lists of ids.

    This is O(n^2) and intended for small datasets or tests. It groups items if their phash Hamming
    distance <= threshold.
    """
    items = list(items)
    clusters: list[list[int]] = []
    used = set()
    for i, (id_i, p_i) in enumerate(items):
        if id_i in used:
            continue
        cluster = [id_i]
        used.add(id_i)
        for j in range(i + 1, len(items)):
            id_j, p_j = items[j]
            if id_j in used:
                continue
            if hamming_distance(p_i, p_j, bits) <= threshold:
                cluster.append(id_j)
                used.add(id_j)
        clusters.append(cluster)
    return clusters
