from flask.cli import FlaskGroup
from flask_migrate import Migrate

from app import server
from models import Base

migrate = Migrate(server, Base, directory="../migrations")

cli = FlaskGroup(server)

if __name__ == "__main__":
    cli()
