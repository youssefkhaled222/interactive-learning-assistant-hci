import test from 'node:test';
import assert from 'node:assert/strict';
import { previewReady } from '../src/cameraPreviewState.js';

test('fresh active camera frames allow preview', () => {
  assert.equal(previewReady({active: true, has_frame: true}), true);
});
test('camera has no frames yet: show offline placeholder', () => {
  assert.equal(previewReady({active: true, has_frame: false}), false);
});
test('closed or malformed camera status never displays stale frame', () => {
  assert.equal(previewReady({active: false, has_frame: true}), false);
  assert.equal(previewReady({active: 'true', has_frame: true}), false);
  assert.equal(previewReady(null), false);
});
