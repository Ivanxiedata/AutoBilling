from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import app.db
from app.db import fix_mongo_id

router = APIRouter()
security = HTTPBearer()

class BillCreate(BaseModel):
    provider_id: str
    date: str
    amount: str
    description: Optional[str] = None
    balance: Optional[str] = None

class BillUpdate(BaseModel):
    date: Optional[str] = None
    amount: Optional[str] = None
    description: Optional[str] = None
    balance: Optional[str] = None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return True

@router.get("/{user_id}/bills")
async def get_user_bills(user_id: str, user=Depends(get_current_user)):
    providers = await app.db.db.providers.find({"user_id": user_id}).to_list(length=None)
    provider_ids = [str(p["_id"]) for p in providers]
    bills = await app.db.db.bills.find({"provider_id": {"$in": provider_ids}}).to_list(length=None)
    bills = [fix_mongo_id(bill) for bill in bills]
    return {"bills": bills, "total_count": len(bills)}

@router.get("/{user_id}/bills/summary")
async def get_bills_summary(user_id: str, user=Depends(get_current_user)):
    providers = await app.db.db.providers.find({"user_id": user_id}).to_list(length=None)
    provider_ids = [str(p["_id"]) for p in providers]
    bills = await app.db.db.bills.find({"provider_id": {"$in": provider_ids}}).to_list(length=None)
    bills = [fix_mongo_id(bill) for bill in bills]
    total_amount = sum(float(b.get("amount", 0)) for b in bills if b.get("amount"))
    bill_count = len(bills)
    recent_bills = sorted(bills, key=lambda x: x.get("date", ""), reverse=True)[:10]
    return {
        "total_amount": total_amount,
        "bill_count": bill_count,
        "recent_bills": recent_bills,
        "avg_per_bill": total_amount / bill_count if bill_count > 0 else 0
    }

@router.delete("/{user_id}/bills/{bill_id}")
async def delete_bill(user_id: str, bill_id: str, user=Depends(get_current_user)):
    result = await app.db.db.bills.delete_one({"_id": bill_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Bill not found")
    return {"message": "Bill deleted"}

@router.delete("/{user_id}/bills/category/{category}")
async def delete_bills_by_category(user_id: str, category: str, user=Depends(get_current_user)):
    providers = await app.db.db.providers.find({"user_id": user_id, "type": {"$regex": category, "$options": "i"}}).to_list(length=None)
    provider_ids = [str(p["_id"]) for p in providers]
    result = await app.db.db.bills.delete_many({"provider_id": {"$in": provider_ids}})
    return {"message": f"Deleted {result.deleted_count} bills for category {category}", "deleted_count": result.deleted_count}

@router.delete("/{user_id}/bills/all")
async def delete_all_bills(user_id: str, user=Depends(get_current_user)):
    providers = await app.db.db.providers.find({"user_id": user_id}).to_list(length=None)
    provider_ids = [str(p["_id"]) for p in providers]
    result = await app.db.db.bills.delete_many({"provider_id": {"$in": provider_ids}})
    return {"message": f"Deleted {result.deleted_count} bills", "deleted_count": result.deleted_count} 