"""Five-question learning packs for the Find the Object game.

Each pack follows the Phase I session rules: exactly five prompts, only the
three demonstration objects (apple, cup, book), every object asked at least
once and never the same object twice in a row. The same packs are used in
gaze and gesture mode so both techniques get an identical task.
"""

SUPPORTED_OBJECTS = ("apple", "cup", "book")
QUESTIONS_PER_PACK = 5

PACK_INFO = {
    "guest": {
        "pack_title": "Guest pack",
        "age_range": "5-10",
        "pack_description": "Simple 'Can you find...?' prompts for an unregistered player.",
    },
    "beginner": {
        "pack_title": "Beginner pack",
        "age_range": "5-7",
        "pack_description": "Short object-name prompts with simple picture-like hints.",
    },
    "advanced": {
        "pack_title": "Advanced pack",
        "age_range": "8-10",
        "pack_description": "Prompts describe what an object is used for instead of naming it.",
    },
}

PACKS = {
    # Order apple, book, cup, apple, book (the Phase I scenario order).
    "guest": [
        {"prompt": "Can you find the apple?", "answer": "apple",
         "choices": ["apple", "book", "cup"], "hint": "It is round and red."},
        {"prompt": "Can you find the book?", "answer": "book",
         "choices": ["cup", "book", "apple"], "hint": "It has pages with pictures and words."},
        {"prompt": "Can you find the cup?", "answer": "cup",
         "choices": ["book", "apple", "cup"], "hint": "You can drink from it."},
        {"prompt": "Find the apple one more time!", "answer": "apple",
         "choices": ["cup", "apple", "book"], "hint": "Look for the fruit."},
        {"prompt": "Last one! Can you find the book?", "answer": "book",
         "choices": ["book", "cup", "apple"], "hint": "It opens and closes like a door."},
    ],
    # Ages 5-7: plain recognition, very short prompts that name the object.
    "beginner": [
        {"prompt": "Find the red apple", "answer": "apple",
         "choices": ["apple", "cup", "book"], "hint": "It is round and red, like a ball."},
        {"prompt": "Find the cup", "answer": "cup",
         "choices": ["book", "cup", "apple"], "hint": "It is the one you drink from."},
        {"prompt": "Find the book", "answer": "book",
         "choices": ["apple", "book", "cup"], "hint": "It has pages."},
        {"prompt": "Where is the apple?", "answer": "apple",
         "choices": ["cup", "book", "apple"], "hint": "Look for the red fruit."},
        {"prompt": "Where is the cup?", "answer": "cup",
         "choices": ["cup", "apple", "book"], "hint": "Look for the cup you drink from."},
    ],
    # Ages 8-10: the prompt describes a use or category, never the object name.
    "advanced": [
        {"prompt": "Which object do we use for reading?", "answer": "book",
         "choices": ["book", "cup", "apple"], "hint": "It has pages full of words."},
        {"prompt": "Which object do we use for drinking?", "answer": "cup",
         "choices": ["apple", "book", "cup"], "hint": "You can pour water or juice into it."},
        {"prompt": "Which object is a fruit we can eat?", "answer": "apple",
         "choices": ["book", "apple", "cup"], "hint": "It grows on a tree."},
        {"prompt": "Which object has pages you can turn?", "answer": "book",
         "choices": ["cup", "apple", "book"], "hint": "Stories are printed inside it."},
        {"prompt": "If you are thirsty, which object do you need?", "answer": "cup",
         "choices": ["cup", "book", "apple"], "hint": "You hold it and sip from it."},
    ],
}


def validate_packs(packs=None, info=None):
    """Raise ValueError if any pack breaks the Phase I session rules."""
    packs = PACKS if packs is None else packs
    info = PACK_INFO if info is None else info
    if set(packs) != set(info):
        raise ValueError("Every pack needs matching PACK_INFO")
    prompts_seen = {}
    for pack_id, questions in packs.items():
        if len(questions) != QUESTIONS_PER_PACK:
            raise ValueError(f"{pack_id}: needs exactly {QUESTIONS_PER_PACK} questions")
        answers = []
        for i, q in enumerate(questions, start=1):
            for key in ("prompt", "answer", "choices", "hint"):
                if key not in q:
                    raise ValueError(f"{pack_id} Q{i}: missing '{key}'")
            if not q["prompt"].strip() or not q["hint"].strip():
                raise ValueError(f"{pack_id} Q{i}: empty prompt or hint")
            choices = q["choices"]
            if len(choices) != len(set(choices)):
                raise ValueError(f"{pack_id} Q{i}: duplicate choices")
            if len(choices) != len(SUPPORTED_OBJECTS) or set(choices) != set(SUPPORTED_OBJECTS):
                raise ValueError(f"{pack_id} Q{i}: choices must contain exactly apple, cup and book")
            if q["answer"] not in choices:
                raise ValueError(f"{pack_id} Q{i}: answer is not one of the choices")
            if q["prompt"] in prompts_seen:
                raise ValueError(f"{pack_id} Q{i}: prompt reused from {prompts_seen[q['prompt']]}")
            prompts_seen[q["prompt"]] = pack_id
            answers.append(q["answer"])
        if set(answers) != set(SUPPORTED_OBJECTS):
            raise ValueError(f"{pack_id}: every object must be asked at least once")
        for a, b in zip(answers, answers[1:]):
            if a == b:
                raise ValueError(f"{pack_id}: same object asked twice in a row ({a})")
    return True
