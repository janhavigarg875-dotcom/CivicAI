from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    watsonx_api_key: str = ""
    watsonx_project_id: str = ""
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    model_id: str = "ibm/granite-3-8b-instruct"

    # Generation parameters
    max_new_tokens: int = 1024
    temperature: float = 0.7
    top_p: float = 0.9

    # Classification uses greedy decoding for determinism
    classify_max_new_tokens: int = 256
    classify_temperature: float = 0.0


settings = Settings()
