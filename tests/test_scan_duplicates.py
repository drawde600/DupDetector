from dupdetector.lib.database import InMemoryAdapter
from dupdetector.cli import scan


def test_scan_marks_duplicates(tmp_path):
    # create two files with identical contents -> identical md5
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_bytes(b"same")
    b.write_bytes(b"same")

    adapter = InMemoryAdapter()
    session = adapter.session()

    class Args:
        folder = str(tmp_path)

    rc = scan(Args(), session=session)
    assert rc == 0

    from dupdetector.models.file import File

    rows = session.query(File).order_by(File.id).all()
    assert len(rows) == 2
    first, second = rows[0], rows[1]
    assert not first.is_duplicate
    assert second.is_duplicate
    assert second.duplicate_of_id == first.id
