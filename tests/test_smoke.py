import dupdetector.cli as cli


def test_scan_smoke():
    # smoke test: calling the scan command should return 0
    rc = cli.main(["scan", "."])
    assert rc == 0
