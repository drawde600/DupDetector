from dupdetector.lib.database import InMemoryAdapter
from dupdetector.models.file import File


def test_inmemory_adapter_basic():
    adapter = InMemoryAdapter()
    session = adapter.session()
    f = File(path="/tmp/a.jpg", original_path="/tmp/a.jpg", name="a.jpg", original_name="a.jpg", size=123, md5_hash="abc123")
    session.add(f)
    session.commit()
    q = session.query(File).filter_by(md5_hash="abc123").one()
    assert q.path == "/tmp/a.jpg"
