// Pure presentation helpers. Never authorize a hardware or game.select event here.
export function feedbackChange(previous, current) {
  if (!previous || !current) return null;
  if (previous.user_id !== current.user_id || previous.level !== current.level) return null;
  if ((current.wrong_attempts ?? 0) > (previous.wrong_attempts ?? 0)) return 'incorrect';
  if (Number.isInteger(current.questions_completed)) {
    return current.questions_completed > (previous.questions_completed ?? 0) ? 'correct' : null;
  }
  // Only support legacy auto-advance state when questions_completed is absent.
  return (current.question_index ?? 0) > (previous.question_index ?? 0) ? 'correct' : null;
}

export function feedbackNextAction(state, feedbackType) {
  if (feedbackType !== 'correct') return 'retry';
  if (state?.completed) return 'results';
  if (state?.awaiting_next) return 'game.next';
  return 'continue';
}

export function visibleDetections(state) {
  if (!state?.object_detection_active || !Array.isArray(state.detected_objects)) return [];
  return state.detected_objects.filter(item =>
    ['apple', 'book', 'cup'].includes(item?.object) && typeof item.target_id === 'string'
  );
}

// Progress markers show completed questions, never unearned gold stars.
export function earnedStars(completed, total, starCount = 5) {
  const count = Number.isInteger(starCount) && starCount > 0 ? Math.min(starCount, 20) : 5;
  const totalSafe = Number.isFinite(total) && total > 0 ? total : 0;
  const done = Number.isFinite(completed) ? Math.max(0, completed) : 0;
  const filled = totalSafe ? Math.round(Math.min(done, totalSafe) / totalSafe * count) : 0;
  return Array.from({ length: count }, (_, i) => i < filled);
}

// Reopening the journey after a previously completed session must not show
// an empty gameplay panel; the backend is the authority on completion.
export function nextScreenAfterSetup(state) {
  return state?.completed ? 'results' : 'game';
}
