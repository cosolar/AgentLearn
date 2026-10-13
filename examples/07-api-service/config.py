"""config.py —— 统一配置（pydantic-settings）

所有配置从环境变量 / .env 读取，避免硬编码密钥。对应教程 7.1「配置」一节。
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- LLM ----
    llm_model_name: str = "gpt-5.5"
    llm_api_key: str | None = None
    llm_base_url: str | None = None

    # ---- 服务 ----
    service_api_key: str = "dev-secret-key"     # 调用方需带 X-API-Key
    rate_limit_per_minute: int = 30             # 每 Key 每分钟请求上限
    cors_origins: list[str] = ["*"]

    # ---- 版本 ----
    version: str = "1.0.0"


settings = Settings()
