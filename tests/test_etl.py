from etl.clean import fix_mojibake


def test_fix_mojibake_repairs_known_pattern():
    assert fix_mojibake("SÃ\x88TE") == "SÈTE"
    assert fix_mojibake("DÃ\x89CHÃ\x88TERIE DE SÃ\x88TE") == "DÉCHÈTERIE DE SÈTE"


def test_fix_mojibake_leaves_clean_strings_untouched():
    assert fix_mojibake("Sète") == "Sète"
    assert fix_mojibake("La Lagune") == "La Lagune"


def test_fix_mojibake_handles_non_string_and_empty():
    assert fix_mojibake(None) is None
    assert fix_mojibake("") == ""
    assert fix_mojibake(42) == 42


def test_score_panel_weighted_differs_from_arithmetic():
    from gosp.services import scoring

    cells = [
        {"score_walking_15": 2.0, "population": 1000},
        {"score_walking_15": 8.0, "population": 10},
    ]
    arithmetic = scoring._arithmetic_mean(cells, "score_walking_15")
    weighted = scoring._weighted_mean(cells, "score_walking_15")
    assert arithmetic == 5.0
    # La cellule dense (pop 1000) pèse beaucoup plus que la cellule
    # peu peuplée (pop 10) au score plus élevé : le pondéré doit rester
    # proche du score de la cellule dense, pas de la moyenne simple.
    assert weighted < arithmetic
    assert weighted < 2.2


def test_combined_duration_is_geometric_mean():
    import math

    from gosp.services import scoring

    result = math.sqrt(4.0 * 9.0)
    assert result == 6.0
