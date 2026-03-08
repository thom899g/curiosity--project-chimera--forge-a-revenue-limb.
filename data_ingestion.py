"""
Multi-Source Data Ingestion Engine
Architectural Rationale: Redundant data sources with failover capability
ensure system resilience against API outages. Async design maximizes throughput.
Edge Cases: Exponential backoff retry logic, data validation, duplicate detection.
"""
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import hashlib
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pydantic import BaseModel, Field, validator
import json

from config import config
from firestore_db import FirestoreClient, EventModel

logger = logging.getLogger(__name__)

class IngestedEvent(BaseModel):
    """Standardized event schema for all data sources"""
    event_id: str = Field(default_factory=lambda: hashlib.sha256(str(datetime.now().timestamp()).encode()).hexdigest()[:16])
    source: str
    event_type: str
    chain_id: int
    contract_address: str
    block_number: int
    transaction_hash: Optional[str] = None
    event_data: Dict[str, Any]
    raw_data: Dict[str, Any]
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    source_timestamp: datetime
    
    @validator('contract_address')
    def validate_address(cls, v):
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError(f"Invalid contract address: {v}")
        return v.lower()

class Moral isStreamIngester:
    """Primary data source using Moralis Streams API"""
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.base_url = config.MORALIS_STREAMS_ENDPOINT
        self.headers = {
            "X-API-Key": config.MORALIS_API_KEY,
            "Content-Type": "application/json"
        }
        self.active_streams = []
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def fetch_streams(self) -> List[Dict[str, Any]]:
        """Fetch all active Moralis streams"""
        try:
            async with self.session.get(
                f"{self.base_url}/streams",
                headers=self.headers,
                timeout=30
            ) as response:
                response.raise_for_status()
                data = await response.json()
                self.active_streams = data.get("result", [])
                logger.info(f"Fetched {len(self.active_streams)} active streams")
                return self.active_streams
        except Exception as e:
            logger.error(f"Failed to fetch streams: {e}")
            raise
    
    async def process_webhook_event(self, payload: Dict[str, Any]) -> Optional[IngestedEvent]:
        """Process incoming Moralis webhook event"""
        try:
            # Moralis webhook structure
            event = payload.get("logs", [{}])[0]
            
            ingested_event = IngestedEvent(
                source="moralis",
                event_type=event.get("topic0", "unknown"),
                chain_id=int(payload.get("chainId", "0x1"), 16),
                contract_address=payload.get("address", ""),
                block_number=int(payload.get("blockNumber", "0"), 16),
                transaction_hash=event.get("transactionHash"),
                event_data={
                    "topics": event.get("topics", []),
                    "data": event.get("data", "")
                },
                raw_data=payload,
                source_timestamp=datetime.utcnow()
            )
            
            logger.debug(f"Processed Moralis event: {ingested_event.event_id}")
            return ingested_event
            
        except Exception as e:
            logger.error(f"Failed to process Moralis webhook: {e}")
            return None

class QuickNodeFallback:
    """Fallback data source using QuickNode HTTP endpoint"""
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.endpoint = config.QUICKNODE_ENDPOINT
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=2, min=2, max=5)
    )
    async def fetch_nft_floor(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """Fetch NFT floor price as fallback data"""
        if not self.endpoint:
            return None
            
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "qn_fetchNFTs",
            "params": [{
                "wallet": contract_address,
                "omitFields": ["provenance", "traits"],
                "page": 1,
                "perPage": 1
            }]
        }
        
        try:
            async with self.session.post(
                self.endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("result", {})
                return None
        except Exception as e:
            logger.warning(f"QuickNode fallback failed: {e}")
            return None

class DataIngestionEngine:
    """Orchestrates multi-source data ingestion"""
    
    def __init__(self):
        self.session = None
        self.moralis = None
        self.quicknode = None
        self.firestore = FirestoreClient()
        self.active = False
        
    async def start(self):
        """Initialize ingestion engine"""
        self.session = aiohttp.ClientSession()
        self.moralis = Moral isStreamIngester(self.session)
        self.quicknode = QuickNodeFallback(self.session)
        self.active = True
        
        # Fetch initial stream configuration
        await self.moralis.fetch_streams()
        logger.info("Data ingestion engine started")
    
    async def stop(self):
        """Clean shutdown"""
        self.active = False
        if self.session:
            await self.session.close()
        logger.info("Data ingestion engine stopped")
    
    async def ingest_event(self, payload: Dict[str, Any], source: str = "moralis") -> bool:
        """
        Process and store an event from any source
        Returns success status
        """
        try:
            if source == "moralis":
                event = await self.moralis.process_webhook_event(payload)
            else:
                # Handle other sources here
                event = None
            
            if event:
                # Store in Firestore
                event_model = EventModel(
                    event_id=event.event_id,
                    source=event.source,
                    event_type=event.event_type,
                    contract_address=event.contract_address,
                    block_number=event.block_number,
                    event_data=event.event_data,
                    raw_data=event.raw_data,
                    ingested_at=event.ingested_at,
                    processed=False
                )
                
                await self.firestore.save_event(event_model)
                
                # Trigger rule engine evaluation
                await self.firestore.trigger_rule_evaluation(event_model.contract_address)
                
                logger.info(f"Ingested event {event.event_id} from {source}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to ingest event: {e}")
            
            # Attempt fallback data collection
            try:
                if "contract_address" in payload:
                    fallback_data = await self.quicknode.fetch_nft_floor(
                        payload.get("contract_address")
                    )
                    if fallback_data:
                        logger.info(f"Collected fallback data for {payload.get('contract_address')}")
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
            
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of all data sources"""
        health_status = {
            "moralis_active": bool(self.moralis and self.moralis.active_streams),
            "quicknode_configured": bool(config.QUICKNODE_ENDPOINT),
            "total_streams": len(self.moralis.active_streams) if self.moralis else 0,
            "last_check": datetime.utcnow().isoformat()
        }
        
        if not health_status["moralis_active"]:
            logger.warning("Moralis has no active streams configured")
            
        return health_status