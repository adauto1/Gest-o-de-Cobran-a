"""
Configurações centralizadas da aplicação usando Pydantic BaseSettings.
"""
import os
from typing import Optional
from decimal import Decimal
from datetime import time
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

class Settings(BaseSettings):
    # Server / Authentication
    session_secret: str = "CHANGE-ME-IN-PROD"
    default_admin_email: str = "admin@portalmoveis.local"
    default_admin_password: str = "admin123"

    # Database
    data_dir: str = "./data"
    database_url: Optional[str] = None

    # Environment
    debug: bool = False

    # Application Preferences
    app_timezone: str = "America/Campo_Grande"
    business_hour_start: int = 9
    business_hour_end: int = 20
    recovery_target_pct: Decimal = Decimal("0.70")
    
    # Priority Triggers
    priority_critical_days: int = 60
    priority_alert_days: int = 30
    priority_moderate_days: int = 1

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def get_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        os.makedirs(self.data_dir, exist_ok=True)
        return f"sqlite:///{self.data_dir}/app.db"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)

settings = Settings()

# Compatibilidade retroativa para imports diretos existentes
TIMEZONE = settings.tz
BUSINESS_HOUR_START = time(settings.business_hour_start, 0)
BUSINESS_HOUR_END = time(settings.business_hour_end, 0)
RECOVERY_TARGET_PCT = settings.recovery_target_pct
PRIORITY_CRITICAL_DAYS = settings.priority_critical_days
PRIORITY_ALERT_DAYS = settings.priority_alert_days
PRIORITY_MODERATE_DAYS = settings.priority_moderate_days
