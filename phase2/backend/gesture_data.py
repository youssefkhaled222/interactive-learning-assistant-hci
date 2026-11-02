"""Validated local trajectories and genuine DollarPy matching; no camera or sockets."""
import hashlib
import json
import math
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

CHANNELS = ('right_wrist', 'thumb', 'index')
LABEL = re.compile(r'^[a-z][a-z0-9_]{0,39}$')


def validate_points(points):
    if not isinstance(points, list) or not 12 <= len(points) <= 5000:
        raise ValueError('Need 12..5000 visible samples; record again')
    clean = []
    previous = -1.0
    for row in points:
        if not isinstance(row, (list, tuple)) or len(row) != 3:
            raise ValueError('Each sample must be [x, y, seconds]')
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
               not math.isfinite(v) for v in row):
            raise ValueError('Coordinates and times must be finite numbers')
        x, y, t = map(float, row)
        if not (0 <= x <= 1 and 0 <= y <= 1 and t >= 0 and t > previous):
            raise ValueError('Coordinates outside image or non-increasing time')
        clean.append([x, y, t])
        previous = t
    if clean[-1][2] - clean[0][2] < .3:
        raise ValueError('Movement is too short (minimum 0.3 seconds)')
    if max(max(p[k] for p in clean) - min(p[k] for p in clean) for k in (0, 1)) < .05:
        raise ValueError('Movement is too small; move clearly across the image')
    return clean


def validate_sample(data):
    if not isinstance(data, dict) or data.get('schema') != 1:
        raise ValueError('Unsupported sample schema; legacy templates need fresh capture')
    if not isinstance(data.get('label'), str) or not LABEL.fullmatch(data['label']):
        raise ValueError('Use a short lowercase label with letters, digits and underscores')
    if data.get('split') not in ('train', 'test') or data.get('channel') not in CHANNELS:
        raise ValueError('Invalid split or landmark channel')
    if data.get('origin') != 'webcam' or data.get('consenting_adult') is not True:
        raise ValueError('Expected a local consenting-adult webcam recording')
    if not isinstance(data.get('sample_id'), str) or not data['sample_id']:
        raise ValueError('Missing sample ID')
    size = data.get('frame_size')
    if (not isinstance(size, list) or len(size) != 2 or
            any(type(v) is not int or not 1 <= v <= 16384 for v in size)):
        raise ValueError('Invalid frame size')
    validate_points(data.get('points'))
    return data


def make_sample(points, label, split, channel, frame_size, camera, model_sha256):
    return validate_sample(dict(
        schema=1, sample_id=uuid.uuid4().hex,
        captured_at=datetime.now(timezone.utc).isoformat(), origin='webcam',
        consenting_adult=True, label=label, split=split, channel=channel,
        frame_size=list(frame_size), camera_index=camera, model_sha256=model_sha256,
        coordinate_space='unmirrored normalized image; x corrected by aspect ratio for matching',
        points=validate_points(points)))


def save_sample(root, sample):
    validate_sample(sample)
    path = Path(root) / sample['channel'] / sample['split'] / sample['label']
    path.mkdir(parents=True, exist_ok=True)
    filename = path / (sample['sample_id'] + '.json')
    with filename.open('x', encoding='utf-8') as out:
        json.dump(sample, out, indent=2, allow_nan=False)
    return filename


def load_samples(root, channel, split):
    result = []
    for path in sorted((Path(root) / channel / split).glob('*/*.json')):
        try:
            if path.stat().st_size > 2_000_000:
                raise ValueError('File too large')
            sample = validate_sample(json.loads(path.read_text(encoding='utf-8')))
            if (sample['channel'], sample['split'], sample['label']) != (channel, split, path.parent.name):
                raise ValueError('Metadata disagrees with sample directory')
            result.append(sample)
        except (ValueError, OSError, TypeError) as exc:
            raise ValueError(f'Invalid recording {path}: {exc}') from exc
    return result


def fingerprint(sample):
    # Ignore IDs/timestamps: copying a training recording into test must fail.
    xy = [[p[0], p[1]] for p in sample['points']]
    return hashlib.sha256(json.dumps(xy, separators=(',', ':')).encode()).hexdigest()


def dollar_points(sample):
    from dollarpy import Point
    ratio = sample['frame_size'][0] / sample['frame_size'][1]
    clean = []
    for x, y, _ in validate_points(sample['points']):
        pair = (x * ratio, y)
        # A stationary frame is valid, but duplicate spatial points can break resampling.
        if not clean or math.dist(pair, clean[-1]) > 1e-9:
            clean.append(pair)
    return [Point(x, y, 1) for x, y in clean]


def classify(sample, training, threshold=.5):
    from dollarpy import Recognizer, Template
    validate_sample(sample)
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('Threshold must be in [0, 1]')
    if len({s['label'] for s in training}) < 2:
        raise ValueError('Record training samples for at least TWO different shapes')
    for s in training:
        validate_sample(s)
        if s['split'] != 'train' or s['channel'] != sample['channel']:
            raise ValueError('Use only training samples from the same landmark channel')
    # DollarPy mutates its input lists during resampling. Build fresh objects EVERY time.
    recognizer = Recognizer([Template(s['label'], dollar_points(s)) for s in training])
    label, score = recognizer.recognize(dollar_points(sample))
    score = float(score)
    if not math.isfinite(score) or not 0 <= score <= 1:
        raise ValueError('DollarPy returned an invalid similarity score')
    return dict(predicted=label, score=score, accepted=bool(label and score >= threshold))


def evaluate(training, testing, threshold=.5, min_test=5):
    if min_test < 1:
        raise ValueError('min_test must be positive')
    ids, hashes = set(), set()
    for sample in training + testing:
        validate_sample(sample)
        digest = fingerprint(sample)
        if sample['sample_id'] in ids or digest in hashes:
            raise ValueError('Duplicate recording or train/test leakage detected')
        ids.add(sample['sample_id']); hashes.add(digest)
    channels = {s['channel'] for s in training + testing}
    if len(channels) != 1:
        raise ValueError('Evaluate one channel at a time; do not mix thumb/index/wrist')
    counts = Counter(s['label'] for s in training)
    tests = Counter(s['label'] for s in testing)
    if len(counts) < 2 or any(n < 2 for n in counts.values()):
        raise ValueError('Need at least two training recordings per class, and two classes')
    if set(tests) != set(counts) or any(n < min_test for n in tests.values()):
        raise ValueError(f'Need at least {min_test} held-out recordings for EVERY trained class')
    rows = []
    for s in testing:
        if s['split'] != 'test':
            raise ValueError('Evaluation input must be the test split')
        prediction = classify(s, training, threshold)
        rows.append(dict(sample_id=s['sample_id'], expected=s['label'], **prediction,
                         correct=prediction['accepted'] and prediction['predicted'] == s['label']))
    confusion = {}
    for row in rows:
        key = row['predicted'] if row['accepted'] else 'REJECTED'
        confusion.setdefault(row['expected'], {})[key] = confusion.get(row['expected'], {}).get(key, 0) + 1
    return dict(channel=next(iter(channels)), train_counts=dict(counts), test_counts=dict(tests),
                threshold=threshold, score_meaning='template similarity; NOT probability',
                accuracy=sum(r['correct'] for r in rows) / len(rows),
                confusion=confusion, predictions=rows,
                provenance_note='Local recording metadata is not independent proof of hardware use')
