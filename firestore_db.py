"""
Firestore Database Abstraction Layer
Architectural Rationale: Centralized database operations with type-safe models
ensure data integrity and simplify maintenance.
Edge Cases: Connection retry logic, batch writes for atomicity, index management.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter
from pydantic import BaseModel, Field
import json

from config import config

logger = logging.getLogger(__name__)

# Pydantic Models for type safety
class EventModel(BaseModel):
    event_id: str
    source: str
    event_type: str
    contract_address: str
    block_number: int
    event_data: Dict[str, Any]
    raw_data: Dict[str, Any]
    ingested_at: datetime
    processed: bool = False
    processed_at: Optional[datetime] = None

class RuleModel(BaseModel):
    rule_id: str
    user_id: str
    rule_type: str  # "nft_floor", "new_mint", "transfer"
    condition: Dict[str, Any]  # JSON Logic condition
    collection_address: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    cooldown_seconds: int = 300
    last_triggered: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    active: bool = True

class AlertModel(BaseModel):
    alert_id: str
    rule_id: str
    user_id: str
    alert_type: str
    message: str
    data: Dict[str, Any]
    status: str = "pending"  # pending, delivered, failed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    delivery_attempts: int = 0
    last_attempt: Optional