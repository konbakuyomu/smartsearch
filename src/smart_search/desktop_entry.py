"""Private configurator process; the user CLI is installed separately."""
import sys


def main():
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if sys.argv[1:2] == ["--desktop-backend"]:
        from smart_search.desktop_backend import main as run
    elif sys.argv[1:2] == ["--desktop-worker"]:
        from smart_search.desktop_worker import main as run
    elif sys.argv[1:] == ["--version"]:
        from smart_search.cli import _get_version
        print("smart-search " + _get_version())
        return 0
    else:
        print("This is the App's private helper. Install the Smart Search CLI separately.", file=sys.stderr)
        return 2
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
