from typing import Optional

from fastapi import Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlmodel import select

from app.dependencies import AdminDep, SessionDep
from app.models.user import Instructor, Lesson, Message, Student, User
from app.utilities.flash import flash
from app.utilities.security import encrypt_password

from . import api_router, router, templates


def get_student_or_404(db, student_id: int) -> Student:
    student = db.exec(select(Student).where(Student.id == student_id)).first()

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    return student


def get_all_instructors(db):
    return db.exec(select(Instructor)).all()


def parse_instructor_id(instructor_id: Optional[str]) -> Optional[int]:
    if instructor_id is None:
        return None

    cleaned = instructor_id.strip()

    if cleaned == "":
        return None

    try:
        return int(cleaned)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid instructor id",
        )


def validate_instructor_id(db, instructor_id: Optional[int]) -> Optional[int]:
    if instructor_id is None:
        return None

    instructor = db.exec(
        select(Instructor).where(Instructor.id == instructor_id)
    ).first()

    if instructor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instructor not found",
        )

    return instructor.id


@router.get("/students")
def get_students(request: Request, user: AdminDep, db: SessionDep):
    students = db.exec(select(Student)).all()
    instructors = get_all_instructors(db)

    students = sorted(students, key=lambda row: row.id or 0, reverse=True)

    return templates.TemplateResponse(
        request=request,
        name="students.html",
        context={
            "user": user,
            "students": students,
            "instructors": instructors,
        },
    )


@router.get("/students/{student_id}")
def get_student(request: Request, student_id: int, user: AdminDep, db: SessionDep):
    student = get_student_or_404(db, student_id)
    instructors = get_all_instructors(db)

    return templates.TemplateResponse(
        request=request,
        name="student.html",
        context={
            "user": user,
            "student": student,
            "instructors": instructors,
        },
    )


@api_router.get("/students")
def api_get_students(user: AdminDep, db: SessionDep):
    return db.exec(select(Student)).all()


@api_router.get("/students/{student_id}")
def api_get_student(student_id: int, user: AdminDep, db: SessionDep):
    return get_student_or_404(db, student_id)


@api_router.post("/students", status_code=status.HTTP_201_CREATED)
def api_create_student(
    request: Request,
    user: AdminDep,
    db: SessionDep,
    username: str = Form(),
    email: str = Form(),
    password: str = Form(),
    instructor_id: Optional[str] = Form(None),
):
    try:
        parsed_instructor_id = validate_instructor_id(
            db,
            parse_instructor_id(instructor_id),
        )

        new_user = User(
            username=username,
            email=email,
            password=encrypt_password(password),
            role="student",
        )

        db.add(new_user)
        db.flush()

        new_student = Student(
            user_id=new_user.id,
            instructor_id=parsed_instructor_id,
        )

        db.add(new_student)
        db.commit()
        db.refresh(new_user)
        db.refresh(new_student)

        flash(request, "Student created successfully!")
        return RedirectResponse(url="/students", status_code=status.HTTP_303_SEE_OTHER)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        flash(request, "Could not create student. Username or email may already exist.", "danger")
        return RedirectResponse(url="/students", status_code=status.HTTP_303_SEE_OTHER)


@api_router.post("/students/{student_id}/update")
def api_update_student(
    student_id: int,
    request: Request,
    user: AdminDep,
    db: SessionDep,
    username: str = Form(),
    email: str = Form(),
    password: Optional[str] = Form(None),
    instructor_id: Optional[str] = Form(None),
):
    student = get_student_or_404(db, student_id)
    linked_user = student.user if student.user else db.get(User, student.user_id)

    if linked_user is None:
        flash(request, "Student user not found!", "danger")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student user not found",
        )

    try:
        parsed_instructor_id = validate_instructor_id(
            db,
            parse_instructor_id(instructor_id),
        )

        linked_user.username = username
        linked_user.email = email

        if password and password.strip():
            linked_user.password = encrypt_password(password)

        student.instructor_id = parsed_instructor_id

        db.add(linked_user)
        db.add(student)
        db.commit()
        db.refresh(linked_user)
        db.refresh(student)

        flash(request, "Student updated successfully!")
        return RedirectResponse(
            url=f"/students/{student_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        flash(request, "Could not update student. Username or email may already exist.", "danger")
        return RedirectResponse(
            url=f"/students/{student_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@api_router.post("/students/{student_id}/delete")
def api_delete_student(
    student_id: int,
    request: Request,
    user: AdminDep,
    db: SessionDep,
):
    student = get_student_or_404(db, student_id)
    linked_user = student.user if student.user else db.get(User, student.user_id)

    if linked_user is None:
        flash(request, "Student user not found!", "danger")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student user not found",
        )

    try:
        lessons = db.exec(select(Lesson).where(Lesson.student_id == student.id)).all()
        for lesson in lessons:
            db.delete(lesson)

        messages = db.exec(
            select(Message).where(
                (Message.sender_id == linked_user.id) | (Message.receiver_id == linked_user.id)
            )
        ).all()

        for message in messages:
            db.delete(message)

        db.delete(student)
        db.delete(linked_user)
        db.commit()

        flash(request, "Student deleted successfully!")
        return RedirectResponse(url="/students", status_code=status.HTTP_303_SEE_OTHER)
    except Exception:
        db.rollback()
        flash(request, "Could not delete student.", "danger")
        return RedirectResponse(
            url=f"/students/{student_id}",
            status_code=status.HTTP_303_SEE_OTHER,
        )