from flask_migrate import Migrate

from models import Base

migrate = None


def init_migrate(app):
    global migrate
    migrate = Migrate(app, Base, directory="../migrations", render_as_batch=True)
    return migrate
