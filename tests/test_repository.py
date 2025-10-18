from dupdetector.lib.database import InMemoryAdapter
from dupdetector.services.repository import Repository


def test_repository_file_crud():
    adapter = InMemoryAdapter()
    session = adapter.session()
    repo = Repository(session)

    f = repo.create_file(path="/tmp/x.jpg", original_path="/tmp/x.jpg", name="x.jpg", original_name="x.jpg", size=10, md5_hash="h1")
    assert f.id is not None

    got = repo.get_file_by_id(f.id)
    assert got is not None and got.md5_hash == "h1"

    files = repo.get_files_by_md5("h1")
    assert len(files) == 1

    all_files = repo.list_files()
    assert len(all_files) >= 1

    deleted = repo.delete_file(f.id)
    assert deleted is True

    assert repo.get_file_by_id(f.id) is None


def test_duplicate_detection_md5():
    adapter = InMemoryAdapter()
    session = adapter.session()
    repo = Repository(session)

    a = repo.create_file(path="/tmp/a.jpg", original_path="/tmp/a.jpg", name="a.jpg", original_name="a.jpg", size=10, md5_hash="dup1")
    b = repo.create_file(path="/tmp/b.jpg", original_path="/tmp/b.jpg", name="b.jpg", original_name="b.jpg", size=10, md5_hash="dup1")

    assert not a.is_duplicate
    assert b.is_duplicate
    assert b.duplicate_of_id == a.id
