import test from 'node:test';
import assert from 'node:assert/strict';
import { earnedStars, nextScreenAfterSetup, feedbackNextAction, feedbackChange } from '../src/gameUiState.js';

test('stars do not appear earned before answering', () => {
  assert.deepEqual(earnedStars(0, 5), [false, false, false, false, false]);
});
test('stars reflect the backend count after one and five questions', () => {
  assert.deepEqual(earnedStars(1, 5), [true, false, false, false, false]);
  assert.deepEqual(earnedStars(5, 5), [true, true, true, true, true]);
});
test('stars clamp malformed or missing counts safely', () => {
  assert.deepEqual(earnedStars(-1, 5), [false, false, false, false, false]);
  assert.deepEqual(earnedStars(99, 5), [true, true, true, true, true]);
  assert.deepEqual(earnedStars(5, 0), [false, false, false, false, false]);
  assert.deepEqual(earnedStars(undefined, undefined), [false, false, false, false, false]);
});
test('opening game with a completed session sends the user to results', () => {
  assert.equal(nextScreenAfterSetup({completed: true}), 'results');
  assert.equal(nextScreenAfterSetup({completed: false}), 'game');
  assert.equal(nextScreenAfterSetup(null), 'game');
});
test('Next Object is chosen only when backend is awaiting it', () => {
  assert.equal(feedbackNextAction({ awaiting_next: true, completed: false }, 'correct'), 'game.next');
  assert.equal(feedbackNextAction({ awaiting_next: false, completed: true }, 'correct'), 'results');
  assert.equal(feedbackNextAction({ awaiting_next: false, completed: false }, 'incorrect'), 'retry');
});
test('live progress update is tied to backend counters, not local mouse preview', () => {
  const a = { user_id: 'guest', level: 'guest', questions_completed: 0, wrong_attempts: 0, question_index: 0 };
  const b = { ...a, questions_completed: 1, awaiting_next: true };
  assert.equal(feedbackChange(a, b), 'correct');
  assert.equal(feedbackChange(a, a), null);
});
