"""Petits helpers de présentation (couleurs/labels de score) partagés entre
les routes et les templates Jinja. L'échelle de seuils (0-3/3-5/5-7/7-9/9-10)
est une proposition de travail non normée — voir /methodologie."""

THRESHOLDS = [
    (3, "score-0", "très faible"),
    (5, "score-3", "faible"),
    (7, "score-5", "moyen"),
    (9, "score-7", "bon"),
    (10.01, "score-9", "très bon"),
]


def score_css_var(value) -> str:
    if value is None:
        return "var(--score-nodata)"
    for ceiling, token, _ in THRESHOLDS:
        if value < ceiling:
            return f"var(--{token})"
    return "var(--score-9)"


def score_class(value) -> str:
    if value is None:
        return "score-color-nodata"
    for ceiling, token, _ in THRESHOLDS:
        if value < ceiling:
            return f"score-color-{token.split('-')[1]}"
    return "score-color-9"


def score_label(value) -> str:
    if value is None:
        return "donnée indisponible"
    for ceiling, _, label in THRESHOLDS:
        if value < ceiling:
            return label
    return "très bon"
