from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    username: str
    full_name: Optional[str]
    role: str
    is_active: bool

class StationResponse(BaseModel):
    id: int
    code: str
    name: str
    lat: float
    lon: float
    region: Optional[str]
    status: str

class ReadingResponse(BaseModel):
    id: int
    station_id: int
    observed_at: datetime
    sst: Optional[float]
    temp_air: Optional[float]
    wave_height: Optional[float]
    wave_period: Optional[float]
    wind_speed: Optional[float]
    wind_dir: Optional[int]
    pressure: Optional[float]
    visibility: Optional[float]
    humidity: Optional[float]
    status: Optional[str]

class ForecastResponse(BaseModel):
    station_id: int
    issued_at: datetime
    forecast_hour: int
    sst_gfs: Optional[float]
    sst_corrected: Optional[float]
    wind_speed_gfs: Optional[float]
    wind_speed_corr: Optional[float]
    wave_height_gfs: Optional[float]
    wave_height_corr: Optional[float]
    correction_meta: Optional[dict]

class RequestCreate(BaseModel):
    station_id: Optional[int]
    title: str
    description: Optional[str]
    req_type: str
    priority: str = "normal"
    assigned_to: Optional[int]

class RequestResponse(BaseModel):
    id: int
    station_id: Optional[int]
    created_by: int
    assigned_to: Optional[int]
    title: str
    description: Optional[str]
    req_type: Optional[str]
    status: str
    priority: Optional[str]
    created_at: datetime
    signed_at: Optional[datetime]

class CalendarEventCreate(BaseModel):
    title: str
    description: Optional[str]
    event_type: str
    station_id: Optional[int]
    starts_at: datetime
    ends_at: datetime
    all_day: bool = False
    color: Optional[str]

class CalendarEventResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    event_type: str
    station_id: Optional[int]
    created_by: Optional[int]
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    color: Optional[str]

class AgentInsight(BaseModel):
    agent_name: str
    title: str
    body: Optional[str] = None
    severity: str = "info"
    metadata: Optional[dict] = None

class EquipmentCheckCreate(BaseModel):
    station_id: int
    equipment: str
    result: str
    notes: Optional[str]

class DashboardSummary(BaseModel):
    station_counts: dict
    open_requests: int
    recent_anomalies: int
    active_agents: list

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "P2"
    estimated_minutes: Optional[int] = None
    due_date: Optional[datetime] = None
    station_id: Optional[int] = None
