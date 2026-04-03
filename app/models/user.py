from datetime import datetime

from sqlmodel import Field, SQLModel, Relationship
from typing import Optional
from pydantic import EmailStr


class UserBase(SQLModel,):
    username: str = Field(index=True, unique=True)
    email: EmailStr = Field(index=True, unique=True)
    password: str
    role:str = ""

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    student: Optional["Student"] = Relationship(back_populates="user")
    instructor: Optional["Instructor"] = Relationship(back_populates="user")

class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    instructor_id: Optional[int] = Field(default=None, foreign_key="instructor.id")
    user: Optional[User] = Relationship(back_populates="student")

    name: str
    
    instructor: Optional["Instructor"] = Relationship(back_populates="students")
    lessons: list["Lesson"] = Relationship(back_populates="student")


class Instructor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    user: Optional["User"] = Relationship(back_populates="instructor")

    name: str
    location: str

    students: list["Student"] = Relationship(back_populates="instructor")
    lessons: list["Lesson"] = Relationship(back_populates="instructor")


#  Lesson model for scheduled lessons between students and instructors.
#  If status is cancelled, each side can delete their connection to it (set to None).
#  If both sides delete their connection, the lesson is deleted from the database.
class Lesson(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    instructor_id: Optional[int] = Field(default=None, foreign_key="instructor.id")
    student_id: Optional[int] = Field(default=None, foreign_key="student.id")

    date: Optional[datetime] = None
    status: str = "scheduled"  # scheduled, completed, cancelled

    instructor: Optional["Instructor"] = Relationship(back_populates="lessons")
    student: Optional["Student"] = Relationship(back_populates="lessons")


#   Message model for chatting between students and instructors.
class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now())

    sender_id: Optional[int] = Field(default=None, foreign_key="user.id")
    receiver_id: Optional[int] = Field(default=None, foreign_key="user.id")