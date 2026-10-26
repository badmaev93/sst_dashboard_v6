from datetime import datetime

from pydantic import BaseModel


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
    full_name: str | None
    role: str
    is_active: bool

class StationResponse(BaseModel):
    id: int
    code: str
    name: str
    lat: float
    lon: float
    region: str | None
    status: str

class ReadingResponse(BaseModel):
    id: int
    station_id: int
    observed_at: datetime
    sst: float | None
    temp_air: float | None
    wave_height: float | None
    wave_period: float | None
    wind_speed: float | None
    wind_dir: int | None
    pressure: float | None
    visibility: float | None
    humidity: float | None
    status: str | None

class ForecastResponse(BaseModel):
    station_id: int
    issued_at: datetime
    forecast_hour: int
    sst_gfs: float | None
    sst_corrected: float | None
    wind_speed_gfs: float | None
    wind_speed_corr: float | None
    wave_height_gfs: float | None
    wave_height_corr: float | None
    correction_meta: dict | None

class RequestCreate(BaseModel):
    station_id: int | None
    title: str
    description: str | None
    req_type: str
    priority: str = "normal"
    assigned_to: int | None

class RequestResponse(BaseModel):
    id: int
    station_id: int | None
    created_by: int
    assigned_to: int | None
    title: str
    description: str | None
    req_type: str | None
    status: str
    priority: str | None
    created_at: datetime
    signed_at: datetime | None

class CalendarEventCreate(BaseModel):
    title: str
    description: str | None
    event_type: str
    station_id: int | None
    starts_at: datetime
    ends_at: datetime
    all_day: bool = False
    color: str | None

class CalendarEventResponse(BaseModel):
    id: int
    title: str
    description: str | None
    event_type: str
    station_id: int | None
    created_by: int | None
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    color: str | None

class AgentInsight(BaseModel):
    agent_name: str
    title: str
    body: str | None = None
    severity: str = "info"
    metadata: dict | None = None

class EquipmentCheckCreate(BaseModel):
    station_id: int
    equipment: str
    result: str
    notes: str | None

class DashboardSummary(BaseModel):
    station_counts: dict
    open_requests: int
    recent_anomalies: int
    active_agents: list

class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    priority: str = "P2"
    estimated_minutes: int | None = None
    due_date: datetime | None = None
    station_id: int | None = None

class ReadingCreate(BaseModel):
    station_id: int
    sst: float | None = None
    temp_air: float | None = None
    wave_height: float | None = None
    wave_period: float | None = None
    wind_speed: float | None = None
    wind_dir: int | None = None
    pressure: float | None = None
    visibility: float | None = None
    humidity: float | None = None
    status: str | None = "normal"
