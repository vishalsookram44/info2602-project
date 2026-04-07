from typing import Annotated, Optional

from sqlmodel import select

from app.models.user import Instructor, InstructorCreate, User
from . import api_router, templates, router
from app.utilities.flash import flash

from app.dependencies import AdminDep, SessionDep
from fastapi import HTTPException, Request, status, Form
from fastapi.responses import RedirectResponse
from app.utilities.security import encrypt_password


@router.get("/instructors")
def get_instructors(request: Request, user: AdminDep, db: SessionDep):
    return templates.TemplateResponse(
        request=request,
        name="instructors.html",
        status_code=200,
        context={
            "user": user,
            "instructors": api_get_instructors(user, db)
        }
    )

@router.get("/instructors/{instructor_id}")
def get_instructor(request: Request, instructor_id: int, user: AdminDep, db: SessionDep):
    instructor = api_get_instructor(instructor_id, user, db)
    return templates.TemplateResponse(
        request=request,
        name="instructor.html",
        status_code=200,
        context={
            "user": user,
            "instructor": instructor
        }
    )


@api_router.get("/instructors")
def api_get_instructors(user: AdminDep, db: SessionDep):
    instructors = db.exec(select(Instructor)).all()
    return instructors

@api_router.get("/instructors/{instructor_id}")
def api_get_instructor(instructor_id: int, user: AdminDep, db: SessionDep):
    instructor = db.exec(select(Instructor).where(Instructor.id == instructor_id)).first()
    if instructor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found")
    return instructor

@api_router.post("/instructors", status_code=status.HTTP_201_CREATED)
def api_create_instructor(user: AdminDep, db: SessionDep, req: Request, username: str = Form(), email: str = Form(), password: str = Form(), location: str = Form()):
    try:
        new_user = User(
            username=username,
            email=email,
            password=encrypt_password(password),
            role="instructor",
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        new_instructor = Instructor(user_id=new_user.id, location=location)

        db.add(new_instructor)
        db.commit()
        db.refresh(new_instructor)


        return RedirectResponse(
            url=f"/instructors", 
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create instructor",
        )
    
@api_router.post("/instructors/{instructor_id}/update")
def api_update_instructor(
    instructor_id: int,
    request: Request,
    user: AdminDep, 
    db: SessionDep, 
    username: str = Form(),
    email: str = Form(),
    password: Optional[str] = Form(None),
    location: str = Form(),
):
    instructor = db.exec(select(Instructor).where(Instructor.id == instructor_id)).first()
    if instructor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found")

    linked_user = instructor.user if instructor.user else db.get(User, instructor.user_id)
    if linked_user is None:
        flash(request, "Instructor user not found!", "danger")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor user not found")
    
    instructor.location = location
    linked_user.username = username
    linked_user.email = email
    if password:
        linked_user.password = encrypt_password(password)
    
    db.add(instructor)
    db.add(linked_user)
    db.commit()
    db.refresh(instructor)

    flash(request, "Instructor updated successfully!")


    return RedirectResponse(
        url=f"/instructors/{instructor_id}", 
        status_code=status.HTTP_303_SEE_OTHER
    )

@api_router.post("/instructors/{instructor_id}/delete")
def api_delete_instructor(instructor_id: int, request: Request, user: AdminDep, db: SessionDep):
    instructor = db.exec(select(Instructor).where(Instructor.id == instructor_id)).first()
    if instructor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found")

    linked_user = instructor.user if instructor.user else db.get(User, instructor.user_id)
    if linked_user is None:
        flash(request, "Instructor user not found!", "danger")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor user not found")
    
    db.delete(instructor)
    db.delete(linked_user)
    db.commit()

    flash(request, "Instructor deleted successfully!")

    return RedirectResponse(
        url=f"/instructors", 
        status_code=status.HTTP_303_SEE_OTHER
    )