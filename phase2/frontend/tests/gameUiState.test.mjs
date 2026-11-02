import test from 'node:test';
import assert from 'node:assert/strict';
import { feedbackChange, feedbackNextAction, visibleDetections } from '../src/gameUiState.js';
const base = { user_id: 'guest', level: 'guest', wrong_attempts: 0, questions_completed: 0, question_index: 0 };

test('correct answer is detected even when question_index stays put awaiting Next Object', () => {
  assert.equal(feedbackChange(base, { ...base, questions_completed: 1, awaiting_next: true }), 'correct');
});
test('incorrect attempt opens retry feedback', () => {
  assert.equal(feedbackChange(base, { ...base, wrong_attempts: 1 }), 'incorrect');
});
test('clicking Next does not show duplicate correct feedback', () => {
  const last = { ...base, questions_completed: 1, question_index: 0 };
  assert.equal(feedbackChange(last, { ...last, question_index: 1, awaiting_next: false }), null);
});
test('switching Bluetooth profile never invents correct feedback', () => {
  assert.equal(feedbackChange(base, { ...base, level: 'advanced', user_id: 'learner_02', questions_completed: 1 }), null);
});
test('legacy auto advance still emits correct feedback', () => {
  const { questions_completed, ...legacy } = base;
  assert.equal(feedbackChange(legacy, { ...legacy, question_index: 1 }), 'correct');
});
test('Next Object sends the command only when backend awaits it', () => {
  assert.equal(feedbackNextAction({ awaiting_next: true, completed: false }, 'correct'), 'game.next');
  assert.equal(feedbackNextAction({ awaiting_next: false, completed: false }, 'correct'), 'continue');
  assert.equal(feedbackNextAction({ completed: true }, 'correct'), 'results');
  assert.equal(feedbackNextAction({ awaiting_next: true }, 'incorrect'), 'retry');
});
test('detected object list is hidden when detector is stopped', () => {
  const state = { object_detection_active: false, detected_objects: [{ object: 'cup', target_id: 'obj-1' }] };
  assert.deepEqual(visibleDetections(state), []);
});
test('only recognized object metadata with IDs is shown', () => {
  const state = { object_detection_active: true, detected_objects: [
    { object: 'cup', target_id: 'obj-1' }, { object: 'person', target_id: 'obj-2' }, { object: 'book' }
  ] };
  assert.deepEqual(visibleDetections(state), [{ object: 'cup', target_id: 'obj-1' }]);
});
