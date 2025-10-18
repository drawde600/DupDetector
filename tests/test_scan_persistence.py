import tempfile
from pathlib import Path

from dupdetector.lib.database import InMemoryAdapter
from dupdetector.cli import scan


def test_scan_persists_files(tmp_path: Path):
    # create two small files
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_bytes(b"hello")
    b.write_bytes(b"world")

    adapter = InMemoryAdapter()
    session = adapter.session()

    class Args:
        folder = str(tmp_path)

    rc = scan(Args(), session=session)
    assert rc == 0

    # assert rows were created
    from dupdetector.models.file import File

    rows = session.query(File).all()
    assert len(rows) == 2
