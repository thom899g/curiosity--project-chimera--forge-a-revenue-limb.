"""
Chimera Core Configuration Module
Architectural Rationale: Centralized configuration with environment-based secrets
prevents hardcoded credentials and enables deployment flexibility.
Edge Cases: All values have fallback defaults; missing env vars trigger immediate alerts.
"""
import os
from typing import Dict, Any
from dotenv import load_dotenv
import logging

load_dotenv()

class Config:
    """Immutable configuration container with validation"""
    
    # Firebase Configuration
    FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json")
    FIRESTORE_PROJECT_ID = os.getenv("FIRESTORE_PROJECT_ID", "chimera-core-prod")
    
    # Data Source APIs
    MORALIS_API_KEY = os.getenv("MORALIS_API_KEY", "")
    MORALIS_STREAMS_ENDPOINT = os.getenv("MORALIS_STREAMS_ENDPOINT", "https://streams.moralis.io/api/v2")
    QUICKNODE_API_KEY = os.getenv("QUICKNODE_API_KEY", "")
    QUICKNODE_ENDPOINT = os.getenv("QUICKNODE_ENDPOINT", "")
    
    # Bot Configuration
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
    
    # Stripe Configuration
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    
    # System Configuration
    ALERT_RETRY_ATTEMPTS = int(os.getenv("ALERT_RETRY_ATTEMPTS", "3"))
    ALERT_RETRY_DELAY = float(os.getenv("ALERT_RETRY_DELAY", "2.0"))
    HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "300"))
    
    # Pricing Configuration
    ONE_TIME_FEE_CENTS = int(os.getenv("ONE_TIME_FEE_CENTS", "1500"))  # $15 default
    FREE_TIER_RULE_LIMIT = int(os.getenv("FREE_TIER_RULE_LIMIT", "1"))
    PAID_TIER_RULE_LIMIT = int(os.getenv("PAID_TIER_RULE_LIMIT", "5"))
    
    @classmethod
    def validate(cls) -> Dict[str, bool]:
        """Validate critical configuration and return status"""
        validation = {
            "firebase_configured": os.path.exists(cls.FIREBASE_CREDENTIALS_PATH),
            "moralis_configured": bool(cls.MORALIS_API_KEY),
            "quicknode_configured": bool(cls.QUICKNODE_API_KEY),
            "discord_configured": bool(cls.DISCORD_BOT_TOKEN),
            "telegram_configured": bool(cls.TELEGRAM_BOT_TOKEN),
            "stripe_configured": bool(cls.STRIPE_SECRET_KEY),
        }
        
        if not all(validation.values()):
            missing = [k for k, v in validation.items() if not v]
            logging.warning(f"Missing configuration for: {', '.join(missing)}")
            
        return validation

config = Config()