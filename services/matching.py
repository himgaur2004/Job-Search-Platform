from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def match_score(resume_text: str, jd_text: str) -> float:
    if not resume_text.strip() or not jd_text.strip():
        return 0.0
    vec = TfidfVectorizer(stop_words="english").fit([resume_text, jd_text])
    matrix = vec.transform([resume_text, jd_text])
    return float(cosine_similarity(matrix[0], matrix[1])[0][0])
