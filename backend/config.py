"""RecoverAI — Configuration Module."""
import os

class Settings:
    """Centralized configuration from environment variables with safe defaults."""
    
    # LLM
    LLM_PROVIDER: str = "fake"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: str = ""
    LLM_CONFIDENCE_THRESHOLD: float = 0.70
    
    # Execution
    EXECUTION_MODE: str = "simulator"
    
    # Razorpay
    RAZORPAY_MODE: str = "test"
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    
    # Database
    DATABASE_PATH: str = "recoverai.db"
    
    def __init__(self):
        self.LLM_PROVIDER = os.environ.get("LLM_PROVIDER", self.LLM_PROVIDER)
        self.LLM_MODEL = os.environ.get("LLM_MODEL", self.LLM_MODEL)
        self.LLM_API_KEY = os.environ.get("LLM_API_KEY", self.LLM_API_KEY)
        self.LLM_CONFIDENCE_THRESHOLD = float(os.environ.get("LLM_CONFIDENCE_THRESHOLD", str(self.LLM_CONFIDENCE_THRESHOLD)))
        self.EXECUTION_MODE = os.environ.get("EXECUTION_MODE", self.EXECUTION_MODE)
        self.RAZORPAY_MODE = os.environ.get("RAZORPAY_MODE", self.RAZORPAY_MODE)
        self.RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", self.RAZORPAY_KEY_ID)
        self.RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", self.RAZORPAY_KEY_SECRET)
        self.DATABASE_PATH = os.environ.get("DATABASE_PATH", self.DATABASE_PATH)
    
    def validate_razorpay(self) -> bool:
        """Check if Razorpay credentials are available. Does NOT silently fall back."""
        if self.EXECUTION_MODE == "razorpay_test":
            if not self.RAZORPAY_KEY_ID or not self.RAZORPAY_KEY_SECRET:
                return False
        return True

def get_settings() -> Settings:
    return Settings()
