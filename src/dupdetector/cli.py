import argparse


def scan(args):
    print(f"Scanning folder: {args.folder}")
    # placeholder implementation
    return 0


def duplicates(args):
    print("Listing duplicates (none in scaffold)")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dupdetector")
    sub = parser.add_subparsers(dest="cmd")

    p_scan = sub.add_parser("scan")
    p_scan.add_argument("folder", nargs="?", default=".")
    p_scan.set_defaults(func=scan)

    p_dup = sub.add_parser("duplicates")
    p_dup.set_defaults(func=duplicates)

    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return args.func(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
