"""
LLM Factory - Factory class supporting multiple LLM providers (no simulation mode)
"""
import logging
from typing import Optional, Dict, Any
from langchain_core.language_models.base import BaseLanguageModel
from ..config.config import config, Config

logger = logging.getLogger(__name__)

def refresh_sso_token(profile: str = "DevOpsPermissionSet-412381743093") -> bool:
    """
    Refresh SSO token by opening browser and running aws sso login
    
    Args:
        profile: AWS profile name
        
    Returns:
        bool: True if SSO refresh was successful, False otherwise
    """
    logger.warning("Attempting SSO token refresh...")
    logger.info("Please complete SSO login in the browser window that will open...")
    
    try:
        import subprocess
        import sys
        import webbrowser
        
        # First, try to get the SSO URL
        try:
            config_result = subprocess.run([
                "aws", "configure", "get", "sso_start_url", 
                "--profile", profile
            ], capture_output=True, text=True, timeout=10)
            
            if config_result.returncode == 0 and config_result.stdout.strip():
                sso_url = config_result.stdout.strip()
                logger.info(f"Opening SSO URL: {sso_url}")
                webbrowser.open(sso_url)
            else:
                logger.warning("Could not get SSO start URL, proceeding with login command...")
        except Exception as url_error:
            logger.warning(f"Could not open SSO URL: {url_error}")
        
        # Use interactive mode to allow browser opening
        result = subprocess.run([
            "aws", "sso", "login", 
            "--profile", profile
        ], stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, timeout=300)  # 5 minutes timeout
        
        if result.returncode == 0:
            logger.info("SSO token refreshed successfully!")
            return True
        else:
            logger.error(f"SSO refresh failed with return code: {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("SSO refresh timed out after 5 minutes")
        return False
    except Exception as sso_error:
        logger.error(f"SSO refresh failed: {str(sso_error)}")
        return False

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
            elif provider == "dify":
                llm = cls._create_dify_llm(ai_config)
            elif provider == "bedrock":
                llm = cls._create_bedrock_llm(ai_config)
            else:
                raise ValueError(f"Unsupported LLM provider: {provider}")
            
            # Verify LLM connection
            if llm and not cls._verify_llm_connection(llm, provider):
                raise ConnectionError(f"LLM connection verification failed: {provider}")
            
            return llm
                
        except Exception as e:
            logger.error(f"Failed to create LLM ({provider}): {e}")
            
            # Auto-SSO refresh logic for Bedrock
            if provider == "bedrock" and Config.ENABLE_AUTO_SSO_REFRESH:
                profile = ai_config.get("profile", "DevOpsPermissionSet-412381743093")
                if refresh_sso_token(profile):
                    logger.info("SSO token refreshed successfully, retrying Bedrock initialization...")
                    # Retry Bedrock initialization
                    retry_llm = cls._create_bedrock_llm(ai_config)
                    if retry_llm and cls._verify_llm_connection(retry_llm, "bedrock"):
                        logger.info("Successfully initialized Bedrock LLM after SSO refresh")
                        return retry_llm
            
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
    def _create_bedrock_llm(cls, ai_config: Dict[str, Any]) -> BaseLanguageModel:
        """Create AWS Bedrock LLM instance"""
        try:
            import boto3
            from langchain_aws import ChatBedrock
            
            # Build boto3 session kwargs
            session_kwargs = {"region_name": ai_config["region"]}
            
            # Authentication based on deployment environment
            deployment_env = ai_config.get("deployment_env", "local")
            
            if deployment_env in ["ecs", "ec2"]:
                # ECS/EC2: Use IAM role credentials (no explicit keys needed)
                logger.info(f"Using IAM role credentials for {deployment_env} environment")
            elif ai_config.get("access_key_id") and ai_config.get("secret_access_key"):
                # Local: Use explicit credentials
                session_kwargs.update({
                    "aws_access_key_id": ai_config["access_key_id"],
                    "aws_secret_access_key": ai_config["secret_access_key"],
                })
                logger.info("Using explicit AWS credentials")
            elif ai_config.get("profile"):
                # Use AWS Profile (SSO or named profile)
                session_kwargs["profile_name"] = ai_config["profile"]
                logger.info(f"Using AWS profile: {ai_config['profile']}")
            else:
                # Try default credential chain
                logger.info("Using default AWS credential chain")
            
            # Create boto3 session
            session = boto3.Session(**session_kwargs)
            
            # Verify credentials
            try:
                sts_client = session.client("sts", region_name=ai_config["region"])
                identity = sts_client.get_caller_identity()
                logger.info(f"AWS identity verified - Account: {identity['Account']}, ARN: {identity['Arn']}")
            except Exception as e:
                logger.error(f"AWS credential verification failed: {e}")
                if "expired" in str(e).lower():
                    raise RuntimeError(
                        f"AWS credentials expired. Please refresh your session.\n"
                        f"For SSO: aws sso login --profile {ai_config.get('profile', 'default')}"
                    )
                raise
            
            # Check model availability (optional)
            try:
                bedrock_control_client = session.client("bedrock", region_name=ai_config["region"])
                available_models = bedrock_control_client.list_foundation_models()
                target_model = ai_config["model"]
                model_found = any(
                    model.get("modelId") == target_model
                    for model in available_models.get("modelSummaries", [])
                )
                if model_found:
                    logger.info(f"Target model {target_model} is available in Bedrock")
                else:
                    logger.warning(f"Target model {target_model} not found in available models list")
            except Exception as e:
                logger.warning(f"Could not verify model availability: {e}")
            
            # Create Bedrock runtime client
            bedrock_client = session.client("bedrock-runtime", region_name=ai_config["region"])
            
            # Initialize ChatBedrock with LangChain
            kwargs = {
                "model_id": ai_config["model"],
                "client": bedrock_client,
                "model_kwargs": {
                    "temperature": ai_config.get("temperature", 0.0),
                    "max_tokens": ai_config.get("max_tokens", 2048),
                },
            }
            
            llm = ChatBedrock(**kwargs)
            logger.info(
                f"Bedrock LLM initialized successfully - Model: {ai_config['model']}, "
                f"Region: {ai_config['region']}, Env: {deployment_env}"
            )
            return llm
            
        except ImportError as e:
            logger.error(f"Bedrock dependencies not installed: {e}")
            logger.error("Please run: pip install boto3 langchain-aws")
            raise
        except Exception as e:
            logger.error(f"Bedrock LLM initialization failed: {e}")
            raise
    
    @classmethod
    def _create_dify_llm(cls, ai_config: Dict[str, Any]) -> BaseLanguageModel:
        """Create Dify.ai LLM instance"""
        try:
            from langchain_community.llms import LlamaCpp
            from langchain_core.language_models.llms import LLM
            from langchain_core.callbacks.manager import CallbackManagerForLLMRun
            from typing import Optional, List, Any
            import requests
            import json
            
            class DifyLLM(LLM):
                """Custom Dify.ai LLM wrapper"""
                
                api_key: str
                base_url: str
                user: Optional[str] = None
                model: str = "gpt-3.5-turbo"
                temperature: float = 0.0
                max_tokens: int = 2048
                timeout: int = 30
                
                class Config:
                    """Pydantic configuration"""
                    arbitrary_types_allowed = True
                
                @property
                def _llm_type(self) -> str:
                    return "dify"
                
                def _call(
                    self,
                    prompt: str,
                    stop: Optional[List[str]] = None,
                    run_manager: Optional[CallbackManagerForLLMRun] = None,
                    **kwargs: Any,
                ) -> str:
                    """Call Dify.ai API"""
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                    
                    if self.user:
                        headers["User"] = self.user
                    
                    # Dify.ai API endpoint for chat completions
                    url = f"{self.base_url.rstrip('/')}/chat-messages"
                    
                    data = {
                        "inputs": {},
                        "query": prompt,
                        "response_mode": "blocking",
                        "user": self.user or "default-user"
                    }
                    
                    try:
                        response = requests.post(
                            url,
                            headers=headers,
                            json=data,
                            timeout=self.timeout
                        )
                        response.raise_for_status()
                        
                        result = response.json()
                        return result.get("answer", "")
                        
                    except Exception as e:
                        logger.error(f"Dify.ai API call failed: {e}")
                        raise
            
            # Create Dify LLM instance
            llm = DifyLLM(
                api_key=ai_config["api_key"],
                base_url=ai_config["base_url"],
                user=ai_config.get("user"),
                model=ai_config["model"],
                temperature=ai_config.get("temperature", 0.0),
                max_tokens=ai_config.get("max_tokens", 2048),
                timeout=ai_config.get("timeout", 30)
            )
            
            logger.info(f"Dify.ai LLM initialized successfully - Model: {ai_config['model']}, Base URL: {ai_config['base_url']}")
            return llm
            
        except Exception as e:
            logger.error(f"Dify.ai LLM initialization failed: {e}")
            raise
    
    @classmethod
    def _verify_llm_connection(cls, llm: BaseLanguageModel, provider: str) -> bool:
        """Verify LLM connection"""
        try:
            # For Dify, skip connection verification as it requires specific app configuration
            if provider == "dify":
                logger.info(f"Dify LLM connection verification skipped (requires app-specific configuration)")
                return True
            
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