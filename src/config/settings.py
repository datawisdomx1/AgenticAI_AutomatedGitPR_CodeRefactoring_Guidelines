"""
Configuration settings for the Enterprise Code Refactor system.
"""

import os
from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    url: str = Field("postgresql://coderefactor:coderefactor123@localhost:5432/enterprise_code_refactor")
    host: str = Field("localhost")
    port: int = Field(5432)
    name: str = Field("enterprise_code_refactor")
    user: str = Field("coderefactor")
    password: str = Field("coderefactor123")
    db_schema: str = Field("code_refactor")
    
    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


class LLMSettings(BaseSettings):
    """LLM configuration settings."""
    
    openai_api_key: Optional[str] = Field(None)
    anthropic_api_key: Optional[str] = Field(None)
    default_provider: str = Field("openai")
    default_model: str = Field("gpt-3.5-turbo")
    temperature: float = Field(0.1)
    max_tokens: int = Field(2048)
    timeout: int = Field(60)
    
    @field_validator("default_provider")
    @classmethod
    def validate_provider(cls, v):
        if v not in ["openai", "anthropic"]:
            raise ValueError("Provider must be 'openai' or 'anthropic'")
        return v
    
    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v):
        if not 0 <= v <= 2:
            raise ValueError("Temperature must be between 0 and 2")
        return v
    
    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


class VectorDatabaseSettings(BaseSettings):
    """Vector database configuration settings."""
    
    embedding_model: str = Field("sentence-transformers/all-MiniLM-L6-v2")
    embedding_dimension: int = Field(384)
    similarity_threshold: float = Field(0.7)
    max_similar_rules: int = Field(10)
    
    @field_validator("similarity_threshold")
    @classmethod
    def validate_similarity_threshold(cls, v):
        if not 0 <= v <= 1:
            raise ValueError("Similarity threshold must be between 0 and 1")
        return v
    
    model_config = SettingsConfigDict(
        env_prefix="VECTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


class GitSettings(BaseSettings):
    """Git configuration settings."""
    
    username: Optional[str] = Field(None)
    token: Optional[str] = Field(None)
    default_branch_prefix: str = Field("code-refactor")
    default_commit_message: str = Field("Code refactoring based on standards analysis")
    
    model_config = SettingsConfigDict(
        env_prefix="GIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


class ApplicationSettings(BaseSettings):
    """Application configuration settings."""
    
    max_workers: int = Field(4)
    batch_size: int = Field(10)
    log_level: str = Field("INFO")
    output_dir: str = Field("./output")
    temp_dir: str = Field("./temp")
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        if v.upper() not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError("Invalid log level")
        return v.upper()
    
    @field_validator("max_workers")
    @classmethod
    def validate_max_workers(cls, v):
        if v < 1:
            raise ValueError("Max workers must be at least 1")
        return v
    
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


class Settings:
    """Main settings class that combines all configuration sections."""
    
    def __init__(self):
        self.database = DatabaseSettings()
        self.llm = LLMSettings()
        self.vector_db = VectorDatabaseSettings()
        self.git = GitSettings()
        self.app = ApplicationSettings()
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure required directories exist."""
        Path(self.app.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.app.temp_dir).mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()

