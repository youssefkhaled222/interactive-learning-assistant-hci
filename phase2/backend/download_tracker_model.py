"""Download versioned official Google task bundles; verify before replacing a file."""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

MODELS = {
    'pose': ('pose_landmarker.task',
        'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task',
        '59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a'),
    'hand': ('hand_landmarker.task',
        'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
        'fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1'),
}


def download(kind, directory):
    filename, url, digest = MODELS[kind]
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
        print(f'Already verified: {path}')
        return path
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(30_000_001)
    if len(data) > 30_000_000 or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Official model checksum mismatch; existing model was not changed')
    temporary = path.with_suffix('.task.download')
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    (directory / (filename + '.source.json')).write_text(
        json.dumps(dict(url=url, sha256=digest, bytes=len(data)), indent=2), encoding='utf-8')
    print(f'Verified download: {path} SHA256={digest}')
    return path


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind', choices=MODELS, default='pose')
    p.add_argument('--directory', type=Path, default=Path(__file__).resolve().parent.parent/'models')
    args = p.parse_args()
    try:
        download(args.kind, args.directory)
    except (OSError, ValueError) as exc:
        p.exit(2, f'Model download failed: {exc}\n')
