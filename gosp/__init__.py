from flask import Flask

from config import SECRET_KEY


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY

    from gosp.services import data_store
    data_store.load_all()

    from gosp.routes.pages import bp as pages_bp
    from gosp.routes.exploration import bp as exploration_bp
    from gosp.routes.quartiers import bp as quartiers_bp
    from gosp.routes.api import bp as api_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(exploration_bp)
    app.register_blueprint(quartiers_bp)
    app.register_blueprint(api_bp)

    from gosp.services import presentation
    app.jinja_env.filters["score_color"] = presentation.score_css_var
    app.jinja_env.filters["score_class"] = presentation.score_class
    app.jinja_env.filters["score_label"] = presentation.score_label
    app.jinja_env.filters["nombre"] = presentation.nombre

    @app.context_processor
    def inject_nav():
        from config import RADAR_AXES, ROSACE_WEDGES, FONCTIONS_LABELS
        return {
            "nav_sections": NAV_SECTIONS,
            "radar_axes": RADAR_AXES,
            "rosace_wedges": ROSACE_WEDGES,
            "fonctions_labels_g": FONCTIONS_LABELS,
        }

    return app


NAV_SECTIONS = [
    {
        "label": "Découvrir",
        "links": [
            {"href": "/", "label": "Accueil"},
            {"href": "/methodologie", "label": "Méthodologie"},
        ],
    },
    {
        "label": "Outils",
        "links": [
            {"href": "/exploration", "label": "Exploration interactive"},
            {"href": "/quartiers", "label": "Fiches quartier"},
        ],
    },
    {
        "label": "Ressources",
        "links": [
            {"href": "/documentation", "label": "Documentation / Aide"},
        ],
    },
]
