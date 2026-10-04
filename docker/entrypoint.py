"""Prepare a dedicated fresh data volume, then run the command as UID/GID 1000."""
import os
import sys


def main():
    if os.geteuid() == 0:
        # Only the mount directory: existing database ownership is an explicit migration.
        os.chown("/data", 1000, 1000)
        os.setgroups([])
        os.setgid(1000)
        os.setuid(1000)
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
