from datetime import datetime
import json

import jwt
from jwt.exceptions import InvalidTokenError
from sqlmodel import Session, select
from fastapi import Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse
from app.config import get_settings
from app.database import engine
from app.models.user import Student, Instructor, Message, User
from app.dependencies.session import SessionDep
from app.dependencies.auth import AuthDep
from app.services.websocket_service import websocket_service
from . import router, api_router, templates


def chat_room_id(user_a_id: int, user_b_id: int) -> str:
    ordered_ids = sorted([user_a_id, user_b_id])
    return f"chat:{ordered_ids[0]}:{ordered_ids[1]}"


def get_websocket_user(websocket: WebSocket, db: SessionDep) -> User | None:
    token = websocket.cookies.get("access_token")
    if token is None:
        return None

    try:
        payload = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[get_settings().jwt_algorithm],
        )
        user_id = payload.get("sub")
    except InvalidTokenError:
        return None

    if user_id is None:
        return None

    return db.exec(select(User).where(User.id == user_id)).first()


def can_user_chat_with_partner(db: SessionDep, user: User, partner_user_id: int) -> bool:
    if user.id is None:
        return False

    if user.role == "student":
        student = db.exec(select(Student).where(Student.user_id == user.id)).first()
        if student is None or student.instructor is None:
            return False
        return student.instructor.user_id == partner_user_id

    if user.role == "instructor":
        instructor = db.exec(select(Instructor).where(Instructor.user_id == user.id)).first()
        if instructor is None:
            return False
        student = db.exec(
            select(Student).where(
                Student.instructor_id == instructor.id,
                Student.user_id == partner_user_id,
            )
        ).first()
        return student is not None

    return False

async def get_chat_messages(
    first_user_id: int | None,
    second_user_id: int | None,
    db: SessionDep,
):
    if first_user_id is None or second_user_id is None:
        return []

    return db.exec(
        select(Message)
        .where(
            ((Message.sender_id == first_user_id) & (Message.receiver_id == second_user_id))
            | ((Message.sender_id == second_user_id) & (Message.receiver_id == first_user_id))
        )
    ).all()

@router.get("/chat", response_class=HTMLResponse)
async def chat_with_instructor(
    request: Request,
    user: AuthDep,
    db: SessionDep,
):
    if user.role == "student":
        student = db.exec(select(Student).where(Student.user_id == user.id)).first()
        if student is None:
            return templates.TemplateResponse(
                request=request,
                name="chat.html",
                context={
                    "user": user,
                    "isStudent": True,
                    "error": "Student profile not found."
                }
            )
        
        
        if student.instructor_id is None:
            return templates.TemplateResponse(
                request=request,
                name="chat.html",
                context={
                    "user": user,
                    "isStudent": True,
                    "student": student,
                    "messages": [],
                    "error": "No instructor assigned yet. Please wait for an instructor to be assigned to you before using the chat feature."
                }
            )

        instructor = db.exec(select(Instructor).where(Instructor.id == student.instructor_id)).first()
        instructor_user_id = instructor.user_id if instructor else None
        messages = []
        if instructor_user_id is not None:
            messages = await get_chat_messages(user.id, instructor_user_id, db)

        return templates.TemplateResponse(
            request=request,
            name="chat.html",
            context={
                "user": user,
                "isStudent": True,
                "student": student,
                "messages": messages,
                "chat_partner_user_id": instructor_user_id,
                "chat_partner_name": instructor.user.username if instructor and instructor.user else "Instructor",
            }
        )
    
    if user.role == "instructor":
        instructor = db.exec(select(Instructor).where(Instructor.user_id == user.id)).first()
        if instructor is None:
            return templates.TemplateResponse(
                request=request,
                name="401.html",
                context={
                    "user": user,
                    "error": "Instructor profile not found."
                }
            )
        
        return templates.TemplateResponse(
            request=request,
            name="mystudents.html",
            context={
                "user": user,
                "students": instructor.students,
                "isInstructor": True,
                "instructor": instructor,
            }
        )
    

@router.get("/chat/{student_id}", response_class=HTMLResponse)
async def chat_with_student(
    request: Request,
    student_id: int,
    user: AuthDep,
    db: SessionDep,
):
    student = db.exec(select(Student).where(Student.id == student_id)).first()
    if student is None:
        student = db.exec(select(Student).where(Student.user_id == student_id)).first()
    if student is None:
        return templates.TemplateResponse(
            request=request,
            name="chat.html",
            context={
                "user": user,
                "error": "Student not found."
            }
        )
    
    if user.role == "instructor":
        instructor = db.exec(select(Instructor).where(Instructor.user_id == user.id)).first()
        if instructor is None or student.instructor_id != instructor.id:
            print(f"Unauthorized access attempt to chat with student_id: {student_id} by instructor_id: {instructor.id if instructor else 'None'}")
            return templates.TemplateResponse(
                request=request,
                name="401.html",
                context={
                    "user": user,
                    "error": "You are not authorized to chat with this student."
                }
            )
        
        messages = await get_chat_messages(user.id, student.user_id, db)
        
        return templates.TemplateResponse(
            request=request,
            name="chat.html",
            context={
                "user": user,
                "isInstructor": True,
                "student": student,
                "messages": messages,
                "chat_partner_user_id": student.user_id,
                "chat_partner_name": student.user.username if student.user else "Student",
            }
        )
    
    print(f"Unauthorized access attempt to chat with student_id: {student_id} by user_id: {user.id}")
    return templates.TemplateResponse(
        request=request,
        name="401.html",
        context={
            "user": user,
            "error": "Only instructors can chat with students."
        }
    )


@router.websocket("/ws/chat/{partner_user_id}")
async def chat_websocket(websocket: WebSocket, partner_user_id: int, db: SessionDep):
    user = get_websocket_user(websocket, db)
    if user is None or not can_user_chat_with_partner(db, user, partner_user_id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if user.id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    room_id = chat_room_id(user.id, partner_user_id)
    await websocket_service.connect_to_room(room_id, websocket)

    try:
        while True:
            content = (await websocket.receive_text()).strip()
            if not content:
                continue

            message = Message(
                content=content,
                timestamp=datetime.now(),
                sender_id=user.id,
                receiver_id=partner_user_id,
            )
            db.add(message)
            db.commit()
            db.refresh(message)

            payload = json.dumps(
                {
                    "id": message.id,
                    "sender_id": user.id,
                    "content": message.content,
                    "timestamp": message.timestamp.strftime("%I:%M %p"),
                }
            )
            await websocket_service.broadcast_room(room_id, payload)
    except WebSocketDisconnect:
        websocket_service.disconnect_from_room(room_id, websocket)
    
@api_router.post("/chat/send")
async def send_message(
    request: Request,
    user: AuthDep,
    db: SessionDep,
):
    return None