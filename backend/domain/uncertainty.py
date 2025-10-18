from backend.domain.entities import TimeCertainty


def precision_score(time_certainty: TimeCertainty) -> int:
    mapping = {
        "exact": 5,
        "morning": 3,
        "afternoon": 3,
        "evening": 3,
        "unknown": 1,
    }
    return mapping.get(time_certainty, 1)
