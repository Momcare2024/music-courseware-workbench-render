from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    vectorengine_api_key: str = ""
    vectorengine_base_url: str = "https://api.vectorengine.ai/v1"
    text_model: str = "claude-sonnet-4-5"
    image_model: str = "doubao-seedream-4-5-251128"
    volcengine_access_key: str = ""
    volcengine_secret_key: str = ""
    jimeng_endpoint: str = "https://visual.volcengineapi.com"
    jimeng_req_key: str = "jimeng_t2i_v40"
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_image_model: str = "doubao-seedream-4-0-250828"
    ppt_master_root: Path = PROJECT_ROOT / "ppt-master"
    workbench_data_dir: Path = PROJECT_ROOT / "data"
    access_code: str = ""
    allow_web_config: bool = True

    @property
    def runs_dir(self) -> Path:
        return self.workbench_data_dir / "runs"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.runs_dir.mkdir(parents=True, exist_ok=True)
    return settings
