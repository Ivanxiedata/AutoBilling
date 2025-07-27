from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import app.db
from app.db import fix_mongo_id
import sys
import asyncio
from .see_bills_refactored import run as fetch_bill_run
import uuid
from bson import ObjectId
from concurrent.futures import ThreadPoolExecutor
import contextlib

router = APIRouter()
security = HTTPBearer()

# Simple in-memory cache: provider_id -> {bill: dict, timestamp: float}
bill_cache = {}
CACHE_TTL_SECONDS = 30 * 60  # 30 minutes

# In-memory job store (use Redis for production)
bill_jobs = {}

# Dedicated pool for long-running Playwright + LLM jobs
JOB_EXECUTOR = ThreadPoolExecutor(max_workers=3)

class ProviderCreate(BaseModel):
    name: str
    type: str
    login_url: str
    username: str
    password: str
    user_id: str
    selectors: Optional[List[dict]] = []

class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    login_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    selectors: Optional[List[dict]] = None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Dummy user check for now; in production, decode JWT and fetch user
    return True

@router.post("/auto-detect")
async def auto_detect_provider(url: str):
    # Dummy implementation
    if "municipalonlinepayments" in url.lower():
        return {"name": "Municipal Online Payments", "type": "water", "detected": True}
    elif "coserv" in url.lower():
        return {"name": "CoServ", "type": "electricity", "detected": True}
    return {"name": "Unknown", "type": "unknown", "detected": False}

@router.post("/create")
async def create_provider(provider: ProviderCreate, user=Depends(get_current_user)):
    doc = provider.dict()
    doc["created_at"] = datetime.utcnow()
    doc["updated_at"] = datetime.utcnow()
    result = await app.db.db.providers.insert_one(doc)
    return {"message": "Provider created", "provider_id": str(result.inserted_id)}

@router.delete("/{provider_id}")
async def delete_provider(provider_id: str, user=Depends(get_current_user)):
    try:
        provider_object_id = ObjectId(provider_id)
        result = await app.db.db.providers.delete_one({"_id": provider_object_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Provider not found")
        await app.db.db.bills.delete_many({"provider_id": provider_id})
        return {"message": "Provider deleted"}
    except Exception as e:
        if "invalid ObjectId" in str(e):
            raise HTTPException(status_code=400, detail="Invalid provider ID format")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/{provider_id}")
async def update_provider(provider_id: str, provider: ProviderUpdate, user=Depends(get_current_user)):
    try:
        provider_object_id = ObjectId(provider_id)
        update_data = {k: v for k, v in provider.dict(exclude_unset=True).items() if v is not None}
        update_data["updated_at"] = datetime.utcnow()
        result = await app.db.db.providers.update_one({"_id": provider_object_id}, {"$set": update_data})
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Provider not found")
        return {"message": "Provider updated"}
    except Exception as e:
        if "invalid ObjectId" in str(e):
            raise HTTPException(status_code=400, detail="Invalid provider ID format")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{provider_id}/bills")
async def get_provider_bills(provider_id: str, user=Depends(get_current_user)):
    try:
        provider_object_id = ObjectId(provider_id)
        bills = await app.db.db.bills.find({"provider_id": provider_id}).to_list(length=None)
        bills = [fix_mongo_id(bill) for bill in bills]
        return {"bills": bills, "total_count": len(bills)}
    except Exception as e:
        if "invalid ObjectId" in str(e):
            raise HTTPException(status_code=400, detail="Invalid provider ID format")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

async def bill_fetch_job(job_id, provider_id, url, username, password):
    bill_jobs[job_id] = {"status": "in_progress", "progress": 10, "bill": None, "error": None}

    async def _smooth_progress():
        """Increment progress toward 80% so UI bar moves steadily."""
        try:
            while bill_jobs[job_id]["status"] == "in_progress":
                await asyncio.sleep(5)
                # Only increment if still under 80
                current = bill_jobs[job_id]["progress"]
                if current < 80:
                    bill_jobs[job_id]["progress"] = min(current + 5, 80)
        except asyncio.CancelledError:
            pass

    pumper_task = asyncio.create_task(_smooth_progress())
    try:
        result = await fetch_bill_run(url, username, password)
        bill_jobs[job_id]["progress"] = 90
        if result.get("success"):
            bill_jobs[job_id]["status"] = "done"
            bill_jobs[job_id]["progress"] = 100
            bill_data = result.get("bill") or {}
            bill_data["provider_id"] = provider_id

            # Persist to database (bills collection)
            try:
                bill_doc = {
                    "provider_id": provider_id,
                    "amount": bill_data.get("current_bill_amount"),
                    "due_date": bill_data.get("due_date"),
                    "raw": bill_data,
                    "created_at": datetime.utcnow(),
                }
                await app.db.db.bills.insert_one(bill_doc)

                # Update provider document with latest bill summary
                await app.db.db.providers.update_one(
                    {"_id": ObjectId(provider_id)},
                    {"$set": {"latest_bill": {"amount": bill_data.get("current_bill_amount"), "due_date": bill_data.get("due_date"), "updated_at": datetime.utcnow()}}}
                )
            except Exception as db_err:
                print(f"Failed to persist bill: {db_err}")

            bill_jobs[job_id]["bill"] = bill_data

            # Cache for 30 min
            if provider_id:
                bill_cache[provider_id] = {"bill": bill_data, "timestamp": datetime.utcnow().timestamp()}
        else:
            bill_jobs[job_id]["status"] = "error"
            bill_jobs[job_id]["error"] = result.get("error", "Unknown error")
            bill_jobs[job_id]["progress"] = 100
    except Exception as e:
        bill_jobs[job_id]["status"] = "error"
        bill_jobs[job_id]["error"] = str(e)
        bill_jobs[job_id]["progress"] = 100
    finally:
        # Stop the progress pumper
        if not pumper_task.done():
            pumper_task.cancel()
            with contextlib.suppress(Exception):
                await pumper_task

        # ------------------------------------------------------------------
        # 🧹  Cleanup screenshots to save disk space
        # ------------------------------------------------------------------
        try:
            import os, shutil
            screenshots_dir = os.path.join(os.path.dirname(__file__), "..", "..", "screenshots")
            screenshots_dir = os.path.abspath(screenshots_dir)
            if os.path.isdir(screenshots_dir):
                # Remove all files inside (keep folder)
                for file_name in os.listdir(screenshots_dir):
                    file_path = os.path.join(screenshots_dir, file_name)
                    if os.path.isfile(file_path):
                        with contextlib.suppress(Exception):
                            os.remove(file_path)
        except Exception as cleanup_err:
            print(f"[cleanup] Failed to remove screenshots: {cleanup_err}")

@router.post("/{provider_id}/fetch-bill")
async def fetch_provider_bill(
    provider_id: str,
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Set to true to bypass cache and force a fresh extraction"),
    user=Depends(get_current_user),
):
    try:
        # Convert string ID to ObjectId
        provider_object_id = ObjectId(provider_id)
        provider = await app.db.db.providers.find_one({"_id": provider_object_id})
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        url = provider.get("login_url")
        username = provider.get("username")
        password = provider.get("password")
        if not all([url, username, password]):
            raise HTTPException(status_code=400, detail="Provider credentials incomplete")

        # Check cache first unless force refresh is requested
        cache_entry = bill_cache.get(provider_id)
        if not force and cache_entry and (datetime.utcnow().timestamp() - cache_entry["timestamp"] < CACHE_TTL_SECONDS):
            # Return immediate done job with cached bill
            job_id = str(uuid.uuid4())
            bill_jobs[job_id] = {"status": "done", "progress": 100, "bill": cache_entry["bill"], "error": None}
            return {"job_id": job_id}

        job_id = str(uuid.uuid4())
        bill_jobs[job_id] = {"status": "pending", "progress": 0, "bill": None, "error": None}
        # Launch the heavy job in a separate thread so the event loop remains responsive
        def _run_job_sync():
            # Run the async bill_fetch_job inside this thread
            asyncio.run(bill_fetch_job(job_id, provider_id, url, username, password))

        loop = asyncio.get_running_loop()
        loop.run_in_executor(JOB_EXECUTOR, _run_job_sync)
        return {"job_id": job_id}
    except Exception as e:
        if "invalid ObjectId" in str(e):
            raise HTTPException(status_code=400, detail="Invalid provider ID format")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/fetch-bill-status/{job_id}")
async def fetch_bill_status(job_id: str, user=Depends(get_current_user)):
    job = bill_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job 