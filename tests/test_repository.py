import tempfile
from dupdetector.lib.database import get_engine, get_sessionmaker, init_db
from dupdetector.services.repository import Repository
from dupdetector.lib.hashing import md5_file
from dupdetector.models.file import File


def make_session():
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    Session = get_sessionmaker(engine)
    return Session()


def test_repository_crud_and_duplicate_detection(tmp_path):
    session = make_session()
    repo = Repository(session)

    # create a temporary file
    fpath = tmp_path / "a.txt"
    fpath.write_text("hello world")

    md5 = md5_file(str(fpath))

    created = repo.create_file(path=str(fpath), original_path=str(fpath), name="a.txt", original_name="a.txt", size=fpath.stat().st_size, md5_hash=md5)
    assert isinstance(created, File)
    assert created.id is not None

    # get by id
    got = repo.get_file_by_id(created.id)
    assert got is not None
    assert got.md5_hash == md5

    # list files
    all_files = repo.list_files()
    assert len(all_files) == 1

    # create a duplicate (same contents)
    f2 = tmp_path / "b.txt"
    f2.write_text("hello world")
    md5_b = md5_file(str(f2))
    dup = repo.create_file(path=str(f2), original_path=str(f2), name="b.txt", original_name="b.txt", size=f2.stat().st_size, md5_hash=md5_b)
    assert dup.is_duplicate is True
    assert dup.duplicate_of_id == created.id

    # delete original
    ok = repo.delete_file(created.id)
    assert ok is True

    # deleting again should return False
    assert repo.delete_file(created.id) is False
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
