from typing import Optional

from app.models.user import Student, User
from app.repositories.user import UserRepository
from app.utilities.security import create_access_token, encrypt_password, verify_password


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo
        self.db = user_repo.db

    def authenticate_user(self, username: str, password: str) -> Optional[str]:
        user = self.user_repo.get_by_username(username)

        if not user or not verify_password(
            plaintext_password=password,
            encrypted_password=user.password,
        ):
            return None

        access_token = create_access_token(data={"sub": f"{user.id}", "role": user.role})
        return access_token

    def register_user(self, username: str, email: str, password: str):
        try:
            new_user = User(
                username=username,
                email=email,
                password=encrypt_password(password),
                role="student",
            )

            self.db.add(new_user)
            self.db.flush()

            new_student = Student(user_id=new_user.id)
            self.db.add(new_student)

            self.db.commit()
            self.db.refresh(new_user)
            self.db.refresh(new_student)

            return new_user
        except Exception:
            self.db.rollback()
            raise