import os
import shutil
import subprocess
import sys
import tempfile

ROOT_PATH = os.path.abspath(os.path.sep)


def relpath_from_root(path: str) -> str:
    return os.path.relpath(path, ROOT_PATH)


def newroot_path(path: str, temp_dir: str) -> str:
    return os.path.join(temp_dir, relpath_from_root(path))


def main() -> None:
    command = sys.argv[3]
    args = sys.argv[4:]

    with tempfile.TemporaryDirectory() as temp_dir:
        os.makedirs(newroot_path(os.path.dirname(command), temp_dir))
        shutil.copy(command, newroot_path(command, temp_dir))
        completed_process = subprocess.run(
            ["unshare", "--map-root-user", "--fork", "--pid", "chroot", temp_dir, command, *args],
            capture_output=True,
        )

    sys.stdout.buffer.write(completed_process.stdout)
    sys.stderr.buffer.write(completed_process.stderr)

    sys.exit(completed_process.returncode)


if __name__ == "__main__":
    main()
