from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from database import DB
from auth import get_current_user

router = APIRouter(prefix="/api/addresses", tags=["Addresses"])

class AddressIn(BaseModel):
    label: str = "Home"
    name: str
    phone: Optional[str] = None
    line1: str
    line2: Optional[str] = None
    city: str
    state: str
    pin: str
    is_default: bool = False

@router.get("")
def list_addresses(user=Depends(get_current_user)):
    with DB() as db:
        return [dict(r) for r in db.fetchall(
            "SELECT * FROM addresses WHERE user_id=%s ORDER BY is_default DESC, id ASC",
            (int(user["sub"]),)
        )]

@router.post("")
def add_address(body: AddressIn, user=Depends(get_current_user)):
    uid = int(user["sub"])
    with DB() as db:
        if body.is_default:
            db.execute("UPDATE addresses SET is_default=0 WHERE user_id=%s", (uid,))
        aid = db.insert(
            "INSERT INTO addresses (user_id,label,name,phone,line1,line2,city,state,pin,is_default) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (uid, body.label, body.name, body.phone, body.line1, body.line2, body.city, body.state, body.pin, 1 if body.is_default else 0)
        )
        return {"id": aid}

@router.put("/{addr_id}")
def update_address(addr_id: int, body: AddressIn, user=Depends(get_current_user)):
    uid = int(user["sub"])
    with DB() as db:
        if body.is_default:
            db.execute("UPDATE addresses SET is_default=0 WHERE user_id=%s", (uid,))
        db.execute(
            "UPDATE addresses SET label=%s,name=%s,phone=%s,line1=%s,line2=%s,city=%s,state=%s,pin=%s,is_default=%s WHERE id=%s AND user_id=%s",
            (body.label, body.name, body.phone, body.line1, body.line2, body.city, body.state, body.pin, 1 if body.is_default else 0, addr_id, uid)
        )
    return {"ok": True}

@router.delete("/{addr_id}")
def delete_address(addr_id: int, user=Depends(get_current_user)):
    with DB() as db:
        db.execute("DELETE FROM addresses WHERE id=%s AND user_id=%s", (addr_id, int(user["sub"])))
    return {"ok": True}
