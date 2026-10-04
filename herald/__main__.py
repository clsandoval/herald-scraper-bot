"""Explicit product modes; running without a mode only shows help."""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Herald match reports and private menu")
    parser.add_argument("mode", choices=["scheduled", "ingest", "menu"], nargs="?")
    # Preserve the selected mode's own help and option parser.
    modes = {"scheduled", "ingest", "menu"}
    if len(sys.argv) > 1 and sys.argv[1] in modes:
        args = parser.parse_args([sys.argv[1]])
        remaining = sys.argv[2:]
    else:
        args, remaining = parser.parse_known_args()
    if args.mode is None:
        parser.print_help()
    elif args.mode == "scheduled":
        from .scheduled import main as run
        run(remaining)
    elif args.mode == "ingest":
        from .ingest import main as run
        sys.argv = [sys.argv[0], *remaining]
        run()
    else:
        if remaining:
            parser.error("menu takes no arguments")
        from .board import main as run
        run()


if __name__ == "__main__":
    main()
