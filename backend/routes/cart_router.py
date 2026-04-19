from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database import DB
from auth import get_current_user

router = APIRouter(prefix="/api/cart", tags=["Cart"])

class AddItem(BaseModel):
    variant_id: int
    quantity: int = 1

class UpdateItem(BaseModel):
    quantity: int

@router.get("")
def get_cart(user=Depends(get_current_user)):
    with DB() as db:
        rows = db.fetchall("""
            SELECT ci.id, ci.quantity,
                   mv.id AS variant_id, mv.label, mv.price, mv.mrp, mv.stock,
                   m.id AS medicine_id, m.name, m.brand, m.image_url, m.requires_rx
            FROM cart_items ci
            JOIN medicine_variants mv ON mv.id = ci.variant_id
            JOIN medicines m ON m.id = mv.medicine_id
            WHERE ci.user_id = %s
        """, (int(user["sub"]),))
        return [dict(r) for r in rows]

@router.post("/add")
def add_to_cart(body: AddItem, user=Depends(get_current_user)):
    with DB() as db:
        db.execute("""
            INSERT INTO cart_items (user_id, variant_id, quantity) VALUES (%s,%s,%s)
            ON DUPLICATE KEY UPDATE quantity = quantity + %s
        """, (int(user["sub"]), body.variant_id, body.quantity, body.quantity))
    return {"ok": True}

@router.put("/{item_id}")
def update_item(item_id: int, body: UpdateItem, user=Depends(get_current_user)):
    with DB() as db:
        if body.quantity < 1:
            db.execute("DELETE FROM cart_items WHERE id=%s AND user_id=%s", (item_id, int(user["sub"])))
        else:
            db.execute("UPDATE cart_items SET quantity=%s WHERE id=%s AND user_id=%s",
                       (body.quantity, item_id, int(user["sub"])))
    return {"ok": True}

@router.delete("/{item_id}")
def remove_item(item_id: int, user=Depends(get_current_user)):
    with DB() as db:
        db.execute("DELETE FROM cart_items WHERE id=%s AND user_id=%s", (item_id, int(user["sub"])))
    return {"ok": True}

@router.delete("")
def clear_cart(user=Depends(get_current_user)):
    with DB() as db:
        db.execute("DELETE FROM cart_items WHERE user_id=%s", (int(user["sub"]),))
    return {"ok": True}
