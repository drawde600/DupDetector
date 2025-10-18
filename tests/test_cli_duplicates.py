from types import SimpleNamespace
from dupdetector.lib.database import get_engine, get_sessionmaker, init_db
from dupdetector.services.repository import Repository
from dupdetector.lib.hashing import md5_file
from dupdetector.cli import duplicates


def make_session():
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    Session = get_sessionmaker(engine)
    return Session()


def test_cli_duplicates_prints_clusters(tmp_path, capsys):
    session = make_session()
    repo = Repository(session)

    # create two similar files (we'll fake photo_hash equality)
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("one")
    b.write_text("one")

    md5_a = md5_file(str(a))
    md5_b = md5_file(str(b))

    f1 = repo.create_file(path=str(a), original_path=str(a), name="a.txt", original_name="a.txt", size=a.stat().st_size, md5_hash=md5_a, photo_hash="abcd")
    f2 = repo.create_file(path=str(b), original_path=str(b), name="b.txt", original_name="b.txt", size=b.stat().st_size, md5_hash=md5_b, photo_hash="abcd")

    args = SimpleNamespace(session=session, threshold=1)
    rc = duplicates(args)
    captured = capsys.readouterr()
    assert rc == 0
    assert "Cluster 1" in captured.out
    assert str(f1.path) in captured.out
    assert str(f2.path) in captured.out
