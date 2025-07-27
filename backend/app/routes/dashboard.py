from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import app.db
from app.db import fix_mongo_id

router = APIRouter()
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return True

@router.get("")
async def get_dashboard(user_id: str, user=Depends(get_current_user)):
    providers = await app.db.db.providers.find({"user_id": user_id}).to_list(length=None)
    providers = [fix_mongo_id(p) for p in providers]
    tenants = await app.db.db.tenants.find({"user_id": user_id}).to_list(length=None)
    tenants = [fix_mongo_id(t) for t in tenants]
    bills = []
    for provider in providers:
        provider_bills = await app.db.db.bills.find({"provider_id": provider["_id"]}).to_list(length=None)
        bills.extend([fix_mongo_id(b) for b in provider_bills])

    def _to_number(val):
        """Convert Mongo stored amount to float, stripping $ and commas."""
        if val is None:
            return 0.0
        try:
            # Handle strings like "$199.00" or "1,234.56"
            if isinstance(val, str):
                val = val.replace("$", "").replace(",", "")
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    total_spent = sum(_to_number(b.get("amount")) for b in bills)
    bill_count = len(bills)
    recent_bills = sorted(bills, key=lambda x: x.get("date", ""), reverse=True)[:10]
    avg_per_bill = total_spent / bill_count if bill_count > 0 else 0
    return {
        "providers": providers,
        "tenants": tenants,
        "recent_bills": recent_bills,
        "stats": {
            "total_spent": total_spent,
            "avg_per_bill": avg_per_bill,
            "bill_count": bill_count
        }
    } 