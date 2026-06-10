# SPDX-License-Identifier: MIT
from __future__ import annotations

from flask import Flask

from .config import get_settings
from .db import init_app as init_db_app
from .mcp import create_blueprint as create_mcp_blueprint
from .routes import create_blueprint


def create_app(test_config: dict[str, object] | None = None) -> Flask:
    app = Flask(__name__)
    settings = get_settings(test_config)
    app.config.from_mapping(settings.to_mapping())
    if test_config:
        app.config.update(test_config)

    init_db_app(app)
    app.register_blueprint(create_blueprint())
    app.register_blueprint(create_mcp_blueprint())
    return app


__all__ = ["create_app"]
