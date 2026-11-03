"""Trusted startup handshake; never exec a worker before its PID is recorded."""
import os
import sys


if __name__ == "__main__":
    descriptor = int(sys.argv[1])
    try:
        released = os.read(descriptor, 1) == b"G"
    finally:
        os.close(descriptor)
    if not released:
        raise SystemExit(125)
    os.execvpe(sys.argv[2], sys.argv[2:], os.environ)
