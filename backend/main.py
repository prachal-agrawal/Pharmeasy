import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings
from routes.auth_router      import router as auth_router
from routes.medicines_router import router as meds_router
from routes.cart_router      import router as cart_router
from routes.orders_router    import router as orders_router
from routes.addresses_router import router as addr_router
from routes.admin_router     import router as admin_router
from routes.payment_router   import router as payment_router
from routes.delivery_router  import router as delivery_router

settings = get_settings()

app = FastAPI(
    title="MathuraPharmeasy API",
    version="2.0.0",
    description="Online Pharmacy — FastAPI + React + Razorpay",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(meds_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(addr_router)
app.include_router(admin_router)
app.include_router(payment_router)
app.include_router(delivery_router)

os.makedirs("./public/uploads",  exist_ok=True)
os.makedirs("./public/invoices", exist_ok=True)

app.mount("/uploads",  StaticFiles(directory="./public/uploads"),  name="uploads")
app.mount("/invoices", StaticFiles(directory="./public/invoices"), name="invoices")

@app.get("/health")
def health():
    return {"status": "ok", "app": "MathuraPharmeasy API v2"}

if __name__ == "__main__":
    import uvicorn
    print(f"\n🚀  MathuraPharmeasy API  →  http://localhost:{settings.PORT}")
    print(f"📚  Swagger Docs →  http://localhost:{settings.PORT}/docs\n")
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=settings.DEBUG)
