from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

# FastAPI app
app = FastAPI()

# Auth via APIKey header (Bearer token)
oauth2_scheme = APIKeyHeader(name="Authorization")

# MongoDB Connection
client = AsyncIOMotorClient("mongodb://localhost:27017")
db = client.cloud_access_db

# Mock token-auth users
USERS_DB = {}

# Models
class Permission(BaseModel):
    id: str
    name: str
    endpoint: str
    description: str

class Plan(BaseModel):
    id: str
    name: str
    description: str
    api_permissions: List[str]
    api_limits: Dict[str, int]

class User(BaseModel):
    id: str
    name: str
    role: str

class Subscription(BaseModel):
    user_id: str
    plan_id: str
    start_date: datetime
    end_date: Optional[datetime] = None

class UsageRecord(BaseModel):
    user_id: str
    api_name: str
    count: int
    last_reset: datetime

# Auth handler
async def get_current_user(token: str = Depends(oauth2_scheme)):
    token = token.replace("Bearer ", "")
    user = USERS_DB.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

# --------------------
# Admin: Permissions
# --------------------
@app.post("/permissions")
async def add_permission(permission: Permission, user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    await db.permissions.insert_one(permission.dict())
    return {"status": "Permission added"}

@app.get("/permissions")
async def get_permissions(user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    permissions = await db.permissions.find().to_list(100)
    return permissions

@app.delete("/permissions/{perm_id}")
async def delete_permission(perm_id: str, user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    result = await db.permissions.delete_one({"id": perm_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Permission not found")
    return {"status": f"Permission {perm_id} deleted"}

# --------------------
# Admin: Plans
# --------------------
@app.post("/plans")
async def create_plan(plan: Plan, user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    await db.plans.insert_one(plan.dict())
    return {"status": "Plan created"}

@app.put("/plans/{plan_id}")
async def modify_plan(plan_id: str, plan: Plan, user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    await db.plans.replace_one({"id": plan_id}, plan.dict(), upsert=True)
    return {"status": "Plan updated"}

@app.get("/plans")
async def get_plans(user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    plans = await db.plans.find().to_list(100)
    return plans

@app.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str, user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    result = await db.plans.delete_one({"id": plan_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"status": f"Plan {plan_id} deleted"}

# ----------------------------
# Customer: Subscriptions
# ----------------------------
@app.post("/subscriptions")
async def subscribe(sub: Subscription, user: User = Depends(get_current_user)):
    if user.role != "customer":
        raise HTTPException(status_code=403, detail="Not authorized")
    await db.subscriptions.replace_one({"user_id": user.id}, sub.dict(), upsert=True)
    return {"status": "Subscribed"}

@app.get("/subscriptions/{user_id}")
async def view_subscription(user_id: str):
    subscription = await db.subscriptions.find_one({"user_id": user_id})
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription

@app.delete("/subscriptions/{user_id}")
async def delete_subscription(user_id: str, user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    result = await db.subscriptions.delete_one({"user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"status": f"Subscription for user {user_id} deleted"}

# ------------------------
# Usage Tracking with MongoDB
# ------------------------
@app.get("/access/{user_id}/{api_name}")
async def check_access(user_id: str, api_name: str):
    subscription = await db.subscriptions.find_one({"user_id": user_id})
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    plan = await db.plans.find_one({"id": subscription["plan_id"]})
    if not plan or api_name not in plan["api_permissions"]:
        raise HTTPException(status_code=403, detail="API not allowed")

    usage = await db.usage.find_one({"user_id": user_id, "api_name": api_name})
    if usage and usage["count"] >= plan["api_limits"].get(api_name, 0):
        raise HTTPException(status_code=429, detail="API limit exceeded")

    return {"access": True}

@app.post("/usage/{user_id}/{api_name}")
async def track_usage(user_id: str, api_name: str):
    usage = await db.usage.find_one({"user_id": user_id, "api_name": api_name})
    if not usage:
        usage_record = {
            "user_id": user_id,
            "api_name": api_name,
            "count": 1,
            "last_reset": datetime.utcnow()
        }
        await db.usage.insert_one(usage_record)
        return {"count": 1}
    else:
        new_count = usage["count"] + 1
        await db.usage.update_one(
            {"user_id": user_id, "api_name": api_name},
            {"$set": {"count": new_count}}
        )
        return {"count": new_count}

@app.delete("/usage/{user_id}/{api_name}")
async def delete_usage(user_id: str, api_name: str, user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    result = await db.usage.delete_one({"user_id": user_id, "api_name": api_name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Usage record not found")
    return {"status": f"Usage for {api_name} by {user_id} deleted"}

# -----------------------
# Dummy Cloud API Endpoint
# -----------------------
@app.get("/cloudapi/{service_name}")
async def dummy_cloud_api(service_name: str, user: User = Depends(get_current_user)):
    await check_access(user.id, service_name)
    await track_usage(user.id, service_name)
    return {"service": service_name, "status": "OK"}

# -----------------------
# Startup: Setup Mock Users
# -----------------------
@app.on_event("startup")
async def setup_mock():
    USERS_DB["admin-token"] = User(id="admin1", name="Admin", role="admin")
    USERS_DB["user-token"] = User(id="user1", name="Customer", role="customer")
