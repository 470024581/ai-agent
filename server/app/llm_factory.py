"""
LLM Factory - Factory class supporting multiple LLM providers (no simulation mode)
"""
import logging
from typing import Optional, Dict, Any
from langchain_core.language_models.base import BaseLanguageModel
from config import config

logger = logging.getLogger(__name__)

class LLMFactory:
    """LLM Factory class - Manages creation and management of different LLM providers (strict configuration mode)"""
    
    _instance: Optional[BaseLanguageModel] = None
    _current_config: Optional[Dict[str, Any]] = None
    
    @classmethod
    def get_llm(cls) -> BaseLanguageModel:
        """Get LLM instance, create if not exists"""
        ai_config = config.get_ai_config()
        
        # If configuration unchanged and instance exists, return directly
        if cls._instance and cls._current_config == ai_config:
            return cls._instance
        
        # Configuration changed or first creation, reinitialize
        cls._current_config = ai_config
        cls._instance = cls._create_llm(ai_config)
        
        if not cls._instance:
            raise RuntimeError(f"Unable to create LLM instance: {ai_config.get('provider')}")
        
        return cls._instance
    
    @classmethod
    def _create_llm(cls, ai_config: Dict[str, Any]) -> BaseLanguageModel:
        """Create corresponding LLM instance based on configuration"""
        provider = ai_config.get("provider")
        
        if not provider:
            raise ValueError("LLM provider configuration missing")
        
        try:
            if provider == "openai":
                llm = cls._create_openai_llm(ai_config)
            elif provider == "openrouter":
                llm = cls._create_openrouter_llm(ai_config)
            elif provider == "ollama":
                llm = cls._create_ollama_llm(ai_config)
            else:
                raise ValueError(f"Unsupported LLM provider: {provider}")
            
            # Verify LLM connection
            if llm and not cls._verify_llm_connection(llm, provider):
                raise ConnectionError(f"LLM connection verification failed: {provider}")
            
            return llm
                
        except Exception as e:
            logger.error(f"Failed to create LLM ({provider}): {e}")
            raise
    
    @classmethod
    def _create_openai_llm(cls, ai_config: Dict[str, Any]) -> BaseLanguageModel:
        """Create OpenAI LLM instance"""
        try:
            from langchain_openai import ChatOpenAI
            
            kwargs = {
                "model_name": ai_config["model"],
                "openai_api_key": ai_config["api_key"],  # This is OPENAI_API_KEY
                "temperature": ai_config.get("temperature", 0.0),
                "max_tokens": ai_config.get("max_tokens", 2048),
            }
            
            # Only set base URL if explicitly configured (for custom OpenAI endpoints)
            if ai_config.get("base_url"):
                kwargs["openai_api_base"] = ai_config["base_url"]  # This is OPENAI_BASE_URL
            
            # Add timeout if configured
            if ai_config.get("timeout"):
                kwargs["request_timeout"] = ai_config.get("timeout")
            
            llm = ChatOpenAI(**kwargs)
            base_url_info = f", Base URL: {ai_config['base_url']}" if ai_config.get("base_url") else ""
            logger.info(f"OpenAI LLM initialized successfully - Model: {ai_config['model']}{base_url_info}")
            return llm
            
        except Exception as e:
            logger.error(f"OpenAI LLM initialization failed: {e}")
            raise
    
    @classmethod
    def _create_openrouter_llm(cls, ai_config: Dict[str, Any]) -> BaseLanguageModel:
        """Create OpenRouter LLM instance"""
        try:
            from langchain_openai import ChatOpenAI
            
            # OpenRouter uses OpenAI-compatible API but with different key and base URL
            kwargs = {
                "model_name": ai_config["model"],
                "openai_api_key": ai_config["api_key"],  # This is OPENROUTER_API_KEY
                "openai_api_base": ai_config["base_url"],  # This is OPENROUTER_BASE_URL
                "temperature": ai_config.get("temperature", 0.0),
                "max_tokens": ai_config.get("max_tokens", 2048),
            }
            
            # Add timeout if configured
            if ai_config.get("timeout"):
                kwargs["request_timeout"] = ai_config.get("timeout")
            
            llm = ChatOpenAI(**kwargs)
            logger.info(f"OpenRouter LLM initialized successfully - Model: {ai_config['model']}, Base URL: {ai_config['base_url']}")
            return llm
            
        except Exception as e:
            logger.error(f"OpenRouter LLM initialization failed: {e}")
            raise
    
    @classmethod
    def _create_ollama_llm(cls, ai_config: Dict[str, Any]) -> BaseLanguageModel:
        """Create Ollama LLM instance"""
        try:
            from langchain_community.llms import Ollama
            
            llm = Ollama(
                model=ai_config["model"],
                base_url=ai_config["base_url"],
                temperature=ai_config.get("temperature", 0.0),
            )
            
            logger.info(f"Ollama LLM initialized successfully - Model: {ai_config['model']}, Address: {ai_config['base_url']}")
            return llm
            
        except ImportError:
            logger.error("Ollama dependencies not installed, please run: pip install langchain-community")
            raise
        except Exception as e:
            logger.error(f"Ollama LLM initialization failed: {e}")
            raise
    
    @classmethod
    def _verify_llm_connection(cls, llm: BaseLanguageModel, provider: str) -> bool:
        """Verify LLM connection"""
        try:
            # Send simple test message
            test_prompt = "Hello"
            response = llm.invoke(test_prompt)
            
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
            
            if response_text and len(response_text.strip()) > 0:
                logger.info(f"{provider} LLM connection verification successful")
                return True
            else:
                logger.error(f"{provider} LLM connection verification failed: empty response")
                return False
            
        except Exception as e:
            logger.error(f"{provider} LLM connection verification failed: {e}")
            return False
    
    @classmethod
    def test_llm_connection(cls) -> Dict[str, Any]:
        """Test LLM connection"""
        try:
            llm = cls.get_llm()
            ai_config = config.get_ai_config()
            
            # Send test message
            test_prompt = "Hello, please reply 'Test successful'."
            response = llm.invoke(test_prompt)
            
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
            
            return {
                "success": True,
                "provider": ai_config.get("provider"),
                "model": ai_config.get("model"),
                "test_response": response_text[:100],  # Limit response length
                "base_url": ai_config.get("base_url", "default")
            }
            
        except Exception as e:
            ai_config = config.get_ai_config()
            return {
                "success": False,
                "provider": ai_config.get("provider"),
                "error": str(e)
            }
    
    @classmethod
    def get_llm_status(cls) -> Dict[str, Any]:
        """Get current LLM status"""
        try:
            ai_config = config.get_ai_config()
            llm = cls.get_llm()
            
            status = {
                "provider": ai_config.get("provider"),
                "model": ai_config.get("model"),
                "available": llm is not None,
                "config": {
                    "temperature": ai_config.get("temperature", 0.0),
                    "max_tokens": ai_config.get("max_tokens", 2048),
                    "base_url": ai_config.get("base_url", "default")
                }
            }
            

            
            return status
            
        except Exception as e:
            return {
                "provider": "unknown",
                "available": False,
                "error": str(e)
            }
    
    @classmethod
    def reset_llm(cls) -> bool:
        """Reset LLM instance (force recreate on next call)"""
        try:
            cls._instance = None
            cls._current_config = None
            logger.info("LLM instance reset successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reset LLM instance: {e}")
            return False

# Convenience functions for global access
def get_llm() -> BaseLanguageModel:
    """Get global LLM instance"""
    return LLMFactory.get_llm()

def get_llm_status() -> Dict[str, Any]:
    """Get global LLM status"""
    return LLMFactory.get_llm_status()

def reset_llm() -> bool:
    """Reset global LLM instance"""
    return LLMFactory.reset_llm()

def test_llm_connection() -> Dict[str, Any]:
    """Test global LLM connection"""
    return LLMFactory.test_llm_connection() 