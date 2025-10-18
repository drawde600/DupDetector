from dupdetector.lib.hashing import hamming_distance, cluster_by_hamming


def test_hamming_distance():
    # 64-bit phash: all zeros vs all ones
    a = "0" * 16  # hex for 0
    b = "f" * 16  # hex for all ones
    dist = hamming_distance(a, b)
    assert dist == 64


def test_cluster_by_hamming():
    # create synthetic phash values where first two are identical, third is far
    items = [
        (1, "0" * 16),
        (2, "0" * 16),
        (3, "f" * 16),
    ]
    clusters = cluster_by_hamming(items, threshold=1)
    # expect first cluster [1,2] and second [3]
    assert any(set(c) == {1, 2} for c in clusters)
    assert any(set(c) == {3} for c in clusters)
