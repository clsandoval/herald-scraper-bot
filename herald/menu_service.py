"""Co-locate the SQLite writer and menu; exit if either child stops."""
import signal
import subprocess
import sys
import time


def main():
    children = []
    def stop(_signum, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        subprocess.run([sys.executable, '-m', 'herald.ingest', '--init-db'], check=True)
        for module, args in [('herald.ingest', ['--loop', '1800']), ('herald.board', [])]:
            children.append(subprocess.Popen([sys.executable, '-m', module, *args]))
        while all(child.poll() is None for child in children):
            time.sleep(.5)
        return 1  # A stale menu is not a healthy service; let the supervisor restart both.
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == '__main__':
    sys.exit(main())
