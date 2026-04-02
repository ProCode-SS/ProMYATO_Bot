from pathlib import Path
from tempfile import gettempdir

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
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""

    TIMEZONE: str = "Europe/Kyiv"
    THERAPIST_NAME: str = "РњР°СЃР°Р¶РёСЃС‚"
    LOCATION: str = ""

    DATABASE_PATH: str = "./data/bot.db"

    CANCELLATION_GROUP_ID: str = ""  # Telegram group/channel ID for cancelled slot notifications

    def model_post_init(self, __context) -> None:
        if self.GOOGLE_SERVICE_ACCOUNT_JSON:
            temp_credentials_path = (
                Path(gettempdir()) / "promyato-google-service-account.json"
            )
            temp_credentials_path.write_text(
                self.GOOGLE_SERVICE_ACCOUNT_JSON, encoding="utf-8"
            )
            self.GOOGLE_SERVICE_ACCOUNT_FILE = str(temp_credentials_path)

        Path(self.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
