from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    BOT_TOKEN: str
    ADMIN_TELEGRAM_IDS: str  # comma-separated, e.g. "360588089, 2017430487"

    @property
    def admin_ids(self) -> list[int]:
        return [int(x.strip()) for x in self.ADMIN_TELEGRAM_IDS.split(",") if x.strip()]

    GOOGLE_CALENDAR_ID: str = ""
    GOOGLE_SERVICE_ACCOUNT_FILE: str = "./credentials/service-account.json"

    TIMEZONE: str = "Europe/Kyiv"
    THERAPIST_NAME: str = "Масажист"
    LOCATION: str = ""

    DATABASE_PATH: str = "./data/bot.db"


settings = Settings()
