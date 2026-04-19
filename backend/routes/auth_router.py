import re
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, field_validator
from database import DB
from auth import hash_password, verify_password, create_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])

_PHONE_RE = re.compile(r"^\+?[0-9\s\-]{7,15}$")


class RegisterIn(BaseModel):
    """Registration payload.

    Attributes:
        name: Customer's full name.
        email: Unique email address.
        password: Plain-text password (min 6 chars enforced on frontend).
        phone: Mobile number — required for order notifications (10–15 digits).
    """

    name: str
    email: EmailStr
    password: str
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Ensure phone is non-empty and looks like a valid number.

        Args:
            v: Raw phone string from the request.

        Returns:
            Stripped phone string.

        Raises:
            ValueError: If the phone is empty or does not match the expected pattern.
        """
        stripped = v.strip()
        if not stripped:
            raise ValueError("Phone number is required for order notifications")
        if not _PHONE_RE.match(stripped):
            raise ValueError("Enter a valid phone number (7–15 digits, optional + or spaces)")
        return stripped

class LoginIn(BaseModel):
    email: EmailStr
    password: str

@router.post("/register")
def register(body: RegisterIn):
    with DB() as db:
        if db.fetchone("SELECT id FROM users WHERE email=%s", (body.email,)):
            raise HTTPException(409, "Email already registered")
        uid = db.insert(
            "INSERT INTO users (name,email,password_hash,phone,role) VALUES (%s,%s,%s,%s,'customer')",
            (body.name, body.email, hash_password(body.password), body.phone or None)
        )
    token = create_token({"sub": str(uid), "name": body.name, "email": body.email, "role": "customer"})
    return {"token": token, "user": {"id": uid, "name": body.name, "email": body.email, "role": "customer"}}

@router.post("/login")
def login(body: LoginIn):
    with DB() as db:
        user = db.fetchone("SELECT * FROM users WHERE email=%s AND is_active=1", (body.email,))
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    token = create_token({"sub": str(user["id"]), "name": user["name"], "email": user["email"], "role": user["role"]})
    return {"token": token, "user": {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}}

@router.get("/me")
def me(current=Depends(get_current_user)):
    return {"user": current}
