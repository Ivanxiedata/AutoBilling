from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import app.db
from app.db import fix_mongo_id

router = APIRouter()
security = HTTPBearer()

class TenantCreate(BaseModel):
    user_id: str
    name: str
    email: str
    phone: Optional[str] = None
    house_id: Optional[str] = None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return True

@router.post("/add")
async def add_tenant(tenant: TenantCreate, user=Depends(get_current_user)):
    existing = await app.db.db.tenants.find_one({"user_id": tenant.user_id, "email": tenant.email})
    if existing:
        raise HTTPException(status_code=400, detail="Tenant with this email already exists")
    doc = tenant.dict()
    doc["created_at"] = datetime.utcnow()
    doc["updated_at"] = datetime.utcnow()
    result = await app.db.db.tenants.insert_one(doc)
    return {"message": "Tenant added", "tenant_id": str(result.inserted_id)}

@router.get("/list")
async def list_tenants(user_id: str, user=Depends(get_current_user)):
    tenants = await app.db.db.tenants.find({"user_id": user_id}).to_list(length=None)
    tenants = [fix_mongo_id(tenant) for tenant in tenants]
    return {"tenants": tenants, "total_count": len(tenants)}

@router.post("/delete")
async def delete_tenant(user_id: str, tenant_email: str, user=Depends(get_current_user)):
    result = await app.db.db.tenants.delete_one({"user_id": user_id, "email": tenant_email})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"message": "Tenant deleted"} 