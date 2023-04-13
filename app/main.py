import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from typing import Any, cast

ROOT_PATH = os.path.abspath(os.path.sep)

DOCKER_EXPLORER_PATH = "/usr/local/bin/docker-explorer"


def relpath_from_root(path: str) -> str:
    return os.path.relpath(path, ROOT_PATH)


def newroot_path(path: str, temp_dir: str) -> str:
    return os.path.join(temp_dir, relpath_from_root(path))


def request(url: str, headers: dict[str, str] = {}) -> Any:
    try:
        req = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(req)
        response_data = response.read()
        return json.loads(response_data)
    except urllib.error.HTTPError as e:
        print(e.read().decode())
        raise


def download(url: str, filename: str) -> None:
    urllib.request.urlretrieve(url, filename)


def main() -> None:
    image = sys.argv[2]
    command = sys.argv[3]
    args = sys.argv[4:]

    image_name: str
    tag: str

    image_split = image.split(":")
    if len(image_split) == 1:
        image_name = image
        tag = "latest"
    elif len(image_split) == 2:
        image_name, tag = image_split
    else:
        raise Exception()

    token: str = request(
        f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/{image_name}:pull"
    )['token']

    url_opener = urllib.request.build_opener()
    url_opener.addheaders = [("Authorization", f"Bearer {token}")]
    urllib.request.install_opener(url_opener)

    index = request(
        f"https://registry.hub.docker.com/v2/library/{image_name}/manifests/{tag}",
        headers={"Accept": "application/vnd.oci.image.index.v1+json"},
    )

    if "manifests" in index:
        manifests: list[Any] = index["manifests"]
        manifest_meta = next(filter(
            lambda x: x["platform"]["os"] == "linux" and x["platform"]["architecture"] == "amd64",
            manifests,
        ))
        layer_meta_list: list[Any] = request(
            f"https://registry.hub.docker.com/v2/library/{image_name}/manifests/{manifest_meta['digest']}",
            headers={"Accept": manifest_meta['mediaType']},
        )["layers"]
        blobs = map(lambda x: cast(str, x["digest"]), layer_meta_list)
    elif "fsLayers" in index:
        fs_layers: list[Any] = index["fsLayers"]
        blobs = map(lambda x: cast(str, x["blobSum"]), fs_layers)
    else:
        raise Exception()

    with tempfile.TemporaryDirectory() as temp_dir, \
            tempfile.TemporaryDirectory() as blob_dir:

        for blob in blobs:
            blob_path = os.path.join(blob_dir, blob)
            download(f"https://registry.hub.docker.com/v2/library/{image_name}/blobs/{blob}", blob_path)
            with tarfile.open(blob_path, "r:gz") as tar:
                tar.extractall(temp_dir)

        os.makedirs(newroot_path(os.path.dirname(DOCKER_EXPLORER_PATH), temp_dir), exist_ok=True)
        shutil.copy(DOCKER_EXPLORER_PATH, newroot_path(DOCKER_EXPLORER_PATH, temp_dir))

        completed_process = subprocess.run(
            ["unshare", "--map-root-user", "--fork", "--pid", "chroot", temp_dir, command, *args],
            capture_output=True,
        )

    sys.stdout.buffer.write(completed_process.stdout)
    sys.stderr.buffer.write(completed_process.stderr)

    sys.exit(completed_process.returncode)


if __name__ == "__main__":
    main()
