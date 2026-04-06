from sqlmodel import select

from fastapi import Request
from fastapi.responses import HTMLResponse
from app.models.user import Instructor, Lesson, Student, User
from app.dependencies.session import SessionDep
from app.dependencies.auth import AdminDep
from . import router, templates


@router.get("/admin", response_class=HTMLResponse)
async def admin_home_view(
    request: Request,
    user: AdminDep,
    db: SessionDep,
):
    total_users = len(db.exec(select(User)).all())
    total_instructors = len(db.exec(select(Instructor)).all())
    total_students = len(db.exec(select(Student)).all())
    scheduled_lessons = len(
        db.exec(select(Lesson).where(Lesson.status == "scheduled")).all()
    )

    recent_users = db.exec(select(User)).all()
    recent_users = sorted(recent_users, key=lambda row: row.id or 0, reverse=True)

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "user": user,
            "metrics": {
                "total_users": total_users,
                "total_instructors": total_instructors,
                "total_students": total_students,
                "scheduled_lessons": scheduled_lessons,
            },
            "recent_users": recent_users,
        },
    )
