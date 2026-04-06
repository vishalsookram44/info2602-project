from sqlmodel import select

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

        newUser = User(username="John Doe", email="jonny@mail.com", password=encrypt_password("johnpass"), role="instructor")
        db.add(newUser)
        db.commit()
        db.refresh(newUser)

        testInstructor = Instructor(user_id=newUser.id, name="John Doe", location="Arima")
        db.add(testInstructor)
        db.commit()

        print("Database initialized successfully.")

@cli.command()
def show_users():
    with get_cli_session() as db:
        users = db.exec(select(User)).all()
        print("Users:")
        for user in users:
            print(f"----------\nID: {user.id}\nUsername: {user.username}\nEmail: {user.email}\nRole: {user.role}\n-----------")
            if user.student_profile:
                print(f"----------\nStudent Profile:\nName: {user.student_profile.name}\nInstructor: {user.student_profile.instructor.name}\n")
            if user.instructor_profile:
                print(f"----------\nInstructor Profile:\nName: {user.instructor_profile.name}\nLocation: {user.instructor_profile.location}\n")




if __name__ == "__main__":
    cli()