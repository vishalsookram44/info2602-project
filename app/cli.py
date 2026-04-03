from app.database import create_db_and_tables, drop_all, get_cli_session
import typer

from app.models.user import *
from app.utilities.security import encrypt_password

cli = typer.Typer()

@cli.command()
def initialize():
    with get_cli_session() as db:
        drop_all()
        create_db_and_tables()

        bob = User(username="bob",email="bob@mail.com",password=encrypt_password("bobpass"),role="admin")
        testmsg = Message(content="Hello, this is a test message!", sender_id=1, receiver_id=1)

        db.add(bob)
        db.add(testmsg)
        db.commit()

        print("Database initialized successfully.")


if __name__ == "__main__":
    cli()