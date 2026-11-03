import test from 'node:test';
import assert from 'node:assert/strict';
import { snapshotSequence } from '../src/cameraPreviewState.js';

test('live health with valid serial refreshes snapshot', () => {
  assert.equal(snapshotSequence({ active: true, has_frame: true, frame_sequence: 7 }), 7);
});

test('stale, inactive, invalid sequences never refresh browser preview', () => {
  for (const health of [null, {}, { active: false, has_frame: true, frame_sequence: 1 },
    { active: true, has_frame: false, frame_sequence: 1 },
    { active: true, has_frame: true, frame_sequence: -1 },
    { active: true, has_frame: true, frame_sequence: 1.5 },
    { active: true, has_frame: true, frame_sequence: '2' }]) {
    assert.equal(snapshotSequence(health), 0);
  }
});
