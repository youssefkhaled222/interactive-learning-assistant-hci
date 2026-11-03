"""Download official MediaPipe Face Landmarker bundle once from Google servers."""
from pathlib import Path
from urllib.request import urlopen
from tempfile import NamedTemporaryFile
import os

URL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'
DEST = Path(__file__).resolve().parents[1] / 'models/face_landmarker.task'
MAX_SIZE = 15_000_000
MIN_SIZE = 1_000_000


def main():
    if DEST.is_file() and DEST.stat().st_size >= MIN_SIZE:
        print(f'Existing face model found: {DEST} ({DEST.stat().st_size} bytes).')
        return
    DEST.parent.mkdir(parents=True, exist_ok=True)
    print('Downloading official MediaPipe Face Landmarker model (one time, HTTPS)...', flush=True)
    with urlopen(URL, timeout=35) as response:
        content = response.read(MAX_SIZE + 1)
    if not MIN_SIZE <= len(content) <= MAX_SIZE:
        raise RuntimeError('Unexpected model download size; no model replaced')
    with NamedTemporaryFile(dir=DEST.parent, prefix='.gaze-model-', delete=False) as file:
        temp = Path(file.name)
        file.write(content)
    try:
        os.replace(temp, DEST)
    finally:
        if temp.exists():
            temp.unlink()
    print(f'Model saved to {DEST}. Files remain local after download.')


if __name__ == '__main__':
    main()
