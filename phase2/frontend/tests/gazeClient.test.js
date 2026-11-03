import test from 'node:test';
import assert from 'node:assert/strict';
import { previewRectFromImage, TARGETS } from '../src/gazeClient.js';

test('nine distinct targets end with held-out center', () => {
  assert.equal(TARGETS.length, 9);
  assert.deepEqual(TARGETS[8], [0.5, 0.5]);
  assert.equal(new Set(TARGETS.map(p => p.join(','))).size, 9);
});

test('actual painted image rectangle accounts for letterboxing', () => {
  const img = {naturalWidth: 640, naturalHeight: 480,
    getBoundingClientRect: () => ({left:100, top:100,width:800,height:450})};
  const measurement = previewRectFromImage(img,1000,800);
  assert.deepEqual(measurement.rect,[0.2, 0.125,0.8,0.6875]);
});

test('missing or out-of-viewport preview cannot provide gaze mapping', () => {
  assert.equal(previewRectFromImage(null,1000,800),null);
  assert.equal(previewRectFromImage({naturalWidth:0,naturalHeight:0},1000,800),null);
  const img = {naturalWidth:640, naturalHeight:480,
    getBoundingClientRect:() => ({left:-10,top:0,width:400,height:300})};
  assert.equal(previewRectFromImage(img,1000,800),null);
});
