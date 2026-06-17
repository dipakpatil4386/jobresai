"""Calibrate raw TF-IDF cosine scores to realistic 0-100 match percentages."""

from typing import List


def calibrate_cosine_percent(similarity: float) -> float:
    sim = max(0.0, min(1.0, float(similarity)))
    if sim <= 0.06:
        return round(sim / 0.06 * 18, 1)
    if sim >= 0.38:
        return round(72 + min((sim - 0.38) / 0.35, 1.0) * 28, 1)
    return round(18 + (sim - 0.06) / 0.32 * 54, 1)


def calibrate_cosine_unit(similarity: float) -> float:
    return calibrate_cosine_percent(similarity) / 100.0


def calibrate_similarity_batch(similarities: List[float]) -> List[float]:
    if not similarities:
        return []
    calibrated = [calibrate_cosine_unit(s) for s in similarities]
    if len(calibrated) <= 1:
        return calibrated

    percents = [c * 100 for c in calibrated]
    top = max(percents)
    if top > 88:
        scale = 82 / top
        percents = [round(p * scale, 1) for p in percents]
    spread = max(percents) - min(percents)
    if spread < 8 and len(percents) > 1:
        for i, p in enumerate(sorted(range(len(percents)), key=lambda j: percents[j], reverse=True)):
            percents[p] = round(percents[p] - i * 4, 1)
    return [max(0.05, min(0.98, p / 100)) for p in percents]


def combined_job_match(text_similarity_unit: float, skill_match_percent: float) -> float:
    text_pct = text_similarity_unit * 100
    combined = 0.55 * text_pct + 0.45 * skill_match_percent
    return round(max(0.0, min(100.0, combined)), 1)
