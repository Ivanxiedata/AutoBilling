from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import motor.motor_asyncio
import os
from dotenv import load_dotenv
import logging, sys

# Load environment variables
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "autobilling")

db = None

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure root logger so that INFO+ messages from all modules appear
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)

@app.on_event("startup")
async def startup_event():
    global db
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URL)
    db = client[DATABASE_NAME]
    import app.db
    app.db.db = db

@app.on_event("shutdown")
async def shutdown_event():
    global db
    if db is not None:
        db.client.close()

from app.routes import users, providers, bills, tenants, dashboard, email

app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(providers.router, prefix="/providers", tags=["providers"])
app.include_router(bills.router, prefix="/bills", tags=["bills"])
app.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(email.router, prefix="/email", tags=["email"])

@app.get("/")
async def root():
    return {"message": "AutoBilling API is running"} 