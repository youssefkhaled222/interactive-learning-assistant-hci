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
