"""
Configuration management module - Manages various configuration parameters for the application
"""
import os
from typing import Optional
from pathlib import Path

# Get project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SERVER_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = SERVER_ROOT / "data"

# Load environment variables from .env files if present (CLI runs may not preload them)
try:
    from dotenv import load_dotenv  # type: ignore
    for _candidate in [
        PROJECT_ROOT / ".env",
        SERVER_ROOT / ".env",
        PROJECT_ROOT / ".env.local",
        SERVER_ROOT / ".env.local",
    ]:
        if _candidate.exists():
            load_dotenv(dotenv_path=_candidate, override=False)
except Exception:
    # dotenv is optional; if missing, rely on process env
    pass

class Config:
    """Application configuration class"""
    
    # Server configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    RELOAD: bool = os.getenv("RELOAD", "True").lower() == "true"
    
    # Database configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/smart.db")
    DATABASE_PATH: Path = DATA_DIR / "smart.db"
    
    # LLM configuration - Multi-provider support (unified keys)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openrouter")  # openrouter, openai, ollama, bedrock
    # Unified model fields. 'LLM_MODEL' kept for backward compatibility (defaults to CHAT model)
    LLM_CHAT_MODEL: str = os.getenv("LLM_CHAT_MODEL", "gpt-3.5-turbo")
    LLM_REASONING_MODEL: str = os.getenv("LLM_REASONING_MODEL", "o3-mini")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "30"))
    
    # Embedding configuration (unified keys)
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "local")  # local, openai, huggingface, bedrock
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "512"))
    EMBEDDING_CACHE_DIR: Path = DATA_DIR / "embeddings_cache"
    
    # Unified API credentials for OpenAI/OpenRouter-compatible providers
    API_KEY: Optional[str] = os.getenv("API_KEY")
    BASE_URL: Optional[str] = os.getenv("BASE_URL")
    
    # Defaults for OpenRouter base URL when provider=openrouter and BASE_URL is not set
    OPENROUTER_DEFAULT_BASE_URL: str = "https://openrouter.ai/api/v1"
    
    # Ollama configuration
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_EMBEDDING_MODEL: str = os.getenv("OLLAMA_EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    
    # AWS Bedrock configuration
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_PROFILE: Optional[str] = os.getenv("AWS_PROFILE")
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    DEPLOYMENT_ENV: str = os.getenv("DEPLOYMENT_ENV", "local")  # local, ecs, ec2
    
    # Bedrock model configuration (use unified chat/reasoning models; legacy ids removed)
    # Bedrock embedding defaults removed; use unified EMBEDDING_MODEL/EMBEDDING_DIMENSION
    
    # Bedrock advanced features
    ENABLE_MODEL_ROUTING: bool = os.getenv("ENABLE_MODEL_ROUTING", "false").lower() == "true"
    ROUTING_CONFIDENCE_THRESHOLD: float = float(os.getenv("ROUTING_CONFIDENCE_THRESHOLD", "0.7"))
    ENABLE_KV_CACHE: bool = os.getenv("ENABLE_KV_CACHE", "false").lower() == "true"
    ENABLE_PROMPT_CACHE: bool = os.getenv("ENABLE_PROMPT_CACHE", "false").lower() == "true"
    MAX_PROMPT_CACHE_SIZE: int = int(os.getenv("MAX_PROMPT_CACHE_SIZE", "100"))
    PROMPT_CACHE_TTL_HOURS: int = int(os.getenv("PROMPT_CACHE_TTL_HOURS", "24"))
    
    # Auto-SSO refresh configuration
    ENABLE_AUTO_SSO_REFRESH: bool = os.getenv("ENABLE_AUTO_SSO_REFRESH", "true").lower() == "true"
    
    # CORS configuration
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        # More origins can be added as needed
    ]
    
    # API configuration
    API_V1_PREFIX: str = "/api/v1"
    API_TITLE: str = "Smart AI Assistant API"
    API_DESCRIPTION: str = "API for interacting with the Smart AI Assistant, powered by LangChain and FastAPI."
    API_VERSION: str = "0.3.0"
    
    # Security configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Pagination configuration
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Cache configuration
    CACHE_TTL: int = 300  # 5 minutes
    
    # Logging configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Business configuration
    DEFAULT_LOW_STOCK_THRESHOLD: int = 50
    DEFAULT_CRITICAL_STOCK_THRESHOLD: int = 10
    
    # Report configuration
    REPORT_STORAGE_PATH: Path = DATA_DIR / "reports"
    MAX_REPORT_AGE_DAYS: int = 30
    
    @classmethod
    def get_ai_config(cls) -> dict:
        """Get AI configuration - Strictly follow LLM_PROVIDER config, no auto-detection"""
        provider = cls.LLM_PROVIDER.lower()
        
        # Strictly follow the specified provider configuration
        if provider == "openai":
            if not cls.API_KEY:
                raise ValueError("LLM_PROVIDER is set to openai, but API_KEY is not configured")
            return {
                "provider": "openai",
                "api_key": cls.API_KEY,
                "base_url": cls.BASE_URL,
                "model": cls.LLM_CHAT_MODEL,
                "reasoning_model": cls.LLM_REASONING_MODEL,
                "temperature": cls.LLM_TEMPERATURE,
                "max_tokens": cls.LLM_MAX_TOKENS,
                "timeout": cls.LLM_TIMEOUT
            }
        elif provider == "openrouter":
            if not cls.API_KEY:
                raise ValueError("LLM_PROVIDER is set to openrouter, but API_KEY is not configured")
            return {
                "provider": "openrouter",
                "api_key": cls.API_KEY,
                "base_url": cls.BASE_URL or cls.OPENROUTER_DEFAULT_BASE_URL,
                "model": cls.LLM_CHAT_MODEL,
                "reasoning_model": cls.LLM_REASONING_MODEL,
                "temperature": cls.LLM_TEMPERATURE,
                "max_tokens": cls.LLM_MAX_TOKENS,
                "timeout": cls.LLM_TIMEOUT
            }
        elif provider == "ollama":
            return {
                "provider": "ollama",
                "base_url": cls.OLLAMA_BASE_URL,
                "model": cls.LLM_CHAT_MODEL,
                "reasoning_model": cls.LLM_REASONING_MODEL,
                "temperature": cls.LLM_TEMPERATURE,
                "max_tokens": cls.LLM_MAX_TOKENS,
                "timeout": cls.LLM_TIMEOUT
            }
        
        elif provider == "bedrock":
            return {
                "provider": "bedrock",
                "region": cls.AWS_REGION,
                "profile": cls.AWS_PROFILE,
                "access_key_id": cls.AWS_ACCESS_KEY_ID,
                "secret_access_key": cls.AWS_SECRET_ACCESS_KEY,
                "deployment_env": cls.DEPLOYMENT_ENV,
                "model": cls.LLM_CHAT_MODEL,
                "reasoning_model": cls.LLM_REASONING_MODEL,
                "temperature": cls.LLM_TEMPERATURE,
                "max_tokens": cls.LLM_MAX_TOKENS,
                "timeout": cls.LLM_TIMEOUT,
                "enable_model_routing": cls.ENABLE_MODEL_ROUTING,
                "routing_confidence_threshold": cls.ROUTING_CONFIDENCE_THRESHOLD,
                "enable_kv_cache": cls.ENABLE_KV_CACHE,
                "enable_prompt_cache": cls.ENABLE_PROMPT_CACHE,
                "max_prompt_cache_size": cls.MAX_PROMPT_CACHE_SIZE,
                "cache_ttl_hours": cls.PROMPT_CACHE_TTL_HOURS
            }
        else:
            raise ValueError(f"Unsupported LLM_PROVIDER: {provider}. Supported values: openai, openrouter, ollama, bedrock")
    
    @classmethod
    def get_embedding_config(cls) -> dict:
        """Get Embedding configuration based on EMBEDDING_PROVIDER"""
        provider = cls.EMBEDDING_PROVIDER.lower()
        
        if provider == "local":
            return {
                "provider": "local",
                "model": cls.EMBEDDING_MODEL,
                "cache_dir": cls.EMBEDDING_CACHE_DIR,
                "dimension": cls.EMBEDDING_DIMENSION
            }
        elif provider == "openai":
            if not cls.API_KEY:
                raise ValueError("EMBEDDING_PROVIDER is set to openai, but API_KEY is not configured")
            return {
                "provider": "openai",
                "api_key": cls.API_KEY,
                "base_url": cls.BASE_URL,
                "model": cls.EMBEDDING_MODEL,
                "dimension": cls.EMBEDDING_DIMENSION
            }
        elif provider == "huggingface":
            return {
                "provider": "huggingface",
                "model": cls.EMBEDDING_MODEL,
                "cache_dir": cls.EMBEDDING_CACHE_DIR,
                "dimension": cls.EMBEDDING_DIMENSION
            }
        elif provider == "ollama":
            return {
                "provider": "ollama",
                "base_url": cls.OLLAMA_BASE_URL,
                "model": cls.OLLAMA_EMBEDDING_MODEL,  # This will be ignored, uses intfloat/multilingual-e5-small internally
                "dimension": cls.EMBEDDING_DIMENSION,
                "cache_dir": cls.EMBEDDING_CACHE_DIR
            }
        
        elif provider == "bedrock":
            return {
                "provider": "bedrock",
                "region": cls.AWS_REGION,
                "profile": cls.AWS_PROFILE,
                "access_key_id": cls.AWS_ACCESS_KEY_ID,
                "secret_access_key": cls.AWS_SECRET_ACCESS_KEY,
                "deployment_env": cls.DEPLOYMENT_ENV,
                "model": cls.EMBEDDING_MODEL,
                "dimension": cls.EMBEDDING_DIMENSION
            }
        else:
            raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider}. Supported values: local, openai, huggingface, ollama, bedrock")
    
    @classmethod
    def is_development(cls) -> bool:
        """Check if in development environment"""
        return cls.DEBUG
    
    @classmethod
    def is_production(cls) -> bool:
        """Check if in production environment"""
        return not cls.DEBUG
    
    @classmethod
    def get_database_config(cls) -> dict:
        """Get database configuration"""
        return {
            "url": cls.DATABASE_URL,
            "path": cls.DATABASE_PATH,
            "create_if_not_exists": True
        }
    
    @classmethod
    def ensure_directories(cls):
        """Ensure necessary directories exist"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.REPORT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
        cls.EMBEDDING_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def validate_config(cls) -> list[str]:
        """Validate configuration and return warning messages"""
        warnings = []
        
        try:
            ai_config = cls.get_ai_config()
            provider = ai_config.get("provider")
            
            # Only check security config in production environment
            if cls.is_production() and cls.SECRET_KEY == "your-secret-key-here":
                warnings.append("Production environment should use a secure SECRET_KEY")
            
            if not DATA_DIR.exists():
                warnings.append(f"Data directory does not exist: {DATA_DIR}")
                
        except Exception as e:
            warnings.append(f"LLM configuration validation failed: {str(e)}")
        
        return warnings

# Create global configuration instance
config = Config()

# Ensure directories exist on import
config.ensure_directories()

# Environment variable loading status check
def check_environment():
    """Check environment configuration status"""
    print("=== Smart AI Agent Environment Configuration Check ===")
    print(f"Running mode: {'Development' if config.is_development() else 'Production'}")
    print(f"Server address: {config.HOST}:{config.PORT}")
    print(f"Database path: {config.DATABASE_PATH}")
    
    ai_config = config.get_ai_config()
    print(f"LLM provider: {ai_config['provider']}")
    print(f"LLM model: {ai_config['model']}")
    if ai_config['provider'] == 'ollama':
        print(f"Ollama address: {ai_config['base_url']}")
    elif ai_config['provider'] in ['openai', 'openrouter']:
        print(f"API Base URL: {ai_config.get('base_url', 'default')}")
    
    warnings = config.validate_config()
    if warnings:
        print("\n⚠️  Configuration warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("✅ Configuration check passed")
    
    print("=" * 40) 