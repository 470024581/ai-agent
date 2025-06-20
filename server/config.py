"""
配置管理模块 - 管理应用程序的各种配置参数
"""
import os
from typing import Optional
from pathlib import Path

# 获取项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER_ROOT = Path(__file__).resolve().parent
DATA_DIR = SERVER_ROOT / "data"

class Config:
    """应用程序配置类"""
    
    # 服务器配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    RELOAD: bool = os.getenv("RELOAD", "True").lower() == "true"
    
    # 数据库配置
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/smart.db")
    DATABASE_PATH: Path = DATA_DIR / "smart.db"
    
    # AI/LLM 配置
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL: Optional[str] = os.getenv("OPENAI_BASE_URL")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    
    # OpenRouter 配置（备选）
    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    
    # CORS 配置
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        # 可以根据需要添加更多源
    ]
    
    # API 配置
    API_V1_PREFIX: str = "/api/v1"
    API_TITLE: str = "Smart AI Assistant API"
    API_DESCRIPTION: str = "API for interacting with the Smart AI Assistant, powered by LangChain and FastAPI."
    API_VERSION: str = "0.3.0"
    
    # 安全配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # 分页配置
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # 缓存配置
    CACHE_TTL: int = 300  # 5分钟
    
    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 业务配置
    DEFAULT_LOW_STOCK_THRESHOLD: int = 50
    DEFAULT_CRITICAL_STOCK_THRESHOLD: int = 10
    
    # 报表配置
    REPORT_STORAGE_PATH: Path = DATA_DIR / "reports"
    MAX_REPORT_AGE_DAYS: int = 30
    
    @classmethod
    def get_ai_config(cls) -> dict:
        """获取AI配置"""
        if cls.OPENAI_API_KEY:
            return {
                "api_key": cls.OPENAI_API_KEY,
                "base_url": cls.OPENAI_BASE_URL,
                "model": cls.OPENAI_MODEL,
                "provider": "openai"
            }
        elif cls.OPENROUTER_API_KEY:
            return {
                "api_key": cls.OPENROUTER_API_KEY,
                "base_url": cls.OPENROUTER_BASE_URL,
                "model": cls.OPENAI_MODEL,
                "provider": "openrouter"
            }
        else:
            return {
                "api_key": None,
                "base_url": None,
                "model": "mock",
                "provider": "mock"
            }
    
    @classmethod
    def is_development(cls) -> bool:
        """检查是否为开发环境"""
        return cls.DEBUG
    
    @classmethod
    def is_production(cls) -> bool:
        """检查是否为生产环境"""
        return not cls.DEBUG
    
    @classmethod
    def get_database_config(cls) -> dict:
        """获取数据库配置"""
        return {
            "url": cls.DATABASE_URL,
            "path": cls.DATABASE_PATH,
            "create_if_not_exists": True
        }
    
    @classmethod
    def ensure_directories(cls):
        """确保必要的目录存在"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.REPORT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def validate_config(cls) -> list[str]:
        """验证配置并返回警告信息"""
        warnings = []
        
        if not cls.OPENAI_API_KEY and not cls.OPENROUTER_API_KEY:
            warnings.append("未配置AI API密钥，将使用模拟模式")
        
        if cls.is_production() and cls.SECRET_KEY == "your-secret-key-here":
            warnings.append("生产环境应使用安全的SECRET_KEY")
        
        if not DATA_DIR.exists():
            warnings.append(f"数据目录不存在: {DATA_DIR}")
        
        return warnings

# 创建全局配置实例
config = Config()

# 环境变量加载状态检查
def check_environment():
    """检查环境配置状态"""
    print("=== Smart 环境配置检查 ===")
    print(f"运行模式: {'开发' if config.is_development() else '生产'}")
    print(f"服务器地址: {config.HOST}:{config.PORT}")
    print(f"数据库路径: {config.DATABASE_PATH}")
    
    ai_config = config.get_ai_config()
    print(f"AI提供商: {ai_config['provider']}")
    print(f"AI模型: {ai_config['model']}")
    
    warnings = config.validate_config()
    if warnings:
        print("\n⚠️  配置警告:")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("✅ 配置检查通过")
    
    print("=" * 30) 