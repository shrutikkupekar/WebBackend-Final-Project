from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import uuid

app = FastAPI()

oauth2_scheme = APIKeyHeader(name="Authorization")

# Mock Databases
USERS_DB = {}
PLANS_DB = {}
PERMISSIONS_DB = {}
SUBSCRIPTIONS_DB = {}
USAGE_DB = {}

# Authentication
async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = USERS_DB.get(token.replace("Bearer ", ""))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

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

# Admin Endpoints
@app.post("/permissions")
async def add_permission(permission: Permission, user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    PERMISSIONS_DB[permission.id] = permission
    return {"status": "Permission added"}

@app.post("/plans")
async def create_plan(plan: Plan, user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    PLANS_DB[plan.id] = plan
    return {"status": "Plan created"}

@app.put("/plans/{plan_id}")
async def modify_plan(plan_id: str, plan: Plan, user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    PLANS_DB[plan_id] = plan
    return {"status": "Plan updated"}

# Customer Subscription
@app.post("/subscriptions")
async def subscribe(sub: Subscription, user: User = Depends(get_current_user)):
    if user.role != "customer":
        raise HTTPException(status_code=403, detail="Not authorized")
    SUBSCRIPTIONS_DB[user.id] = sub
    return {"status": "Subscribed"}

@app.get("/subscriptions/{user_id}")
async def view_subscription(user_id: str):
    return SUBSCRIPTIONS_DB.get(user_id)

# Access Control
@app.get("/access/{user_id}/{api_name}")
async def check_access(user_id: str, api_name: str):
    subscription = SUBSCRIPTIONS_DB.get(user_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    plan = PLANS_DB.get(subscription.plan_id)
    if not plan or api_name not in plan.api_permissions:
        raise HTTPException(status_code=403, detail="API not allowed")
    usage_key = f"{user_id}:{api_name}"
    usage = USAGE_DB.get(usage_key, UsageRecord(user_id=user_id, api_name=api_name, count=0, last_reset=datetime.utcnow()))
    if usage.count >= plan.api_limits.get(api_name, 0):
        raise HTTPException(status_code=429, detail="API limit exceeded")
    return {"access": True}

# Usage Tracking
@app.post("/usage/{user_id}/{api_name}")
async def track_usage(user_id: str, api_name: str):
    usage_key = f"{user_id}:{api_name}"
    usage = USAGE_DB.get(usage_key)
    if not usage:
        usage = UsageRecord(user_id=user_id, api_name=api_name, count=1, last_reset=datetime.utcnow())
    else:
        usage.count += 1
    USAGE_DB[usage_key] = usage
    return {"count": usage.count}

# Dummy Cloud API
@app.get("/cloudapi/{service_name}")
async def dummy_cloud_api(service_name: str, user: User = Depends(get_current_user)):
    await check_access(user.id, service_name)
    await track_usage(user.id, service_name)
    return {"service": service_name, "status": "OK"}

# Mock Tokens and Users
@app.on_event("startup")
async def setup_mock():
    USERS_DB["admin-token"] = User(id="admin1", name="Admin", role="admin")
    USERS_DB["user-token"] = User(id="user1", name="Customer", role="customer")
