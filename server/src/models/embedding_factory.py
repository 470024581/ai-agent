"""
Embedding Factory - Factory class supporting multiple embedding providers
"""
import logging
from typing import Optional, Dict, Any, Union
from pathlib import Path
from langchain_core.embeddings.embeddings import Embeddings
from ..config.config import config

logger = logging.getLogger(__name__)

class EmbeddingFactory:
    """Embedding Factory class - Manages creation and management of different embedding providers"""
    
    _instance: Optional[Embeddings] = None
    _current_config: Optional[Dict[str, Any]] = None
    
    @classmethod
    def get_embeddings(cls, force_local: bool = False) -> Embeddings:
        """Get embeddings instance, create if not exists"""
        embedding_config = config.get_embedding_config()
        
        # If configuration unchanged and instance exists, return directly
        if cls._instance and cls._current_config == embedding_config:
            return cls._instance
        
        # Configuration changed or first creation, reinitialize
        cls._current_config = embedding_config
        cls._instance = cls._create_embeddings(embedding_config)
        
        if not cls._instance:
            raise RuntimeError(f"Unable to create embeddings instance: {embedding_config.get('provider')}")
        
        return cls._instance
    
    @classmethod
    def _create_embeddings(cls, embedding_config: Dict[str, Any]) -> Embeddings:
        """Create corresponding embeddings instance based on configuration"""
        provider = embedding_config.get("provider")
        
        if not provider:
            raise ValueError("Embedding provider configuration missing")
        
        try:
            if provider == "openai":
                embeddings = cls._create_openai_embeddings(embedding_config)
            elif provider == "local":
                embeddings = cls._create_local_embeddings(embedding_config)
            elif provider == "huggingface":
                embeddings = cls._create_huggingface_embeddings(embedding_config)
            elif provider == "ollama":
                embeddings = cls._create_ollama_embeddings(embedding_config)
            elif provider == "dify":
                embeddings = cls._create_dify_embeddings(embedding_config)
            elif provider == "bedrock":
                embeddings = cls._create_bedrock_embeddings(embedding_config)
            else:
                raise ValueError(f"Unsupported embedding provider: {provider}")
            
            # Verify embeddings connection
            if embeddings and not cls._verify_embeddings_connection(embeddings, provider):
                logger.warning(f"Embeddings connection verification failed: {provider}, but continuing...")
            
            return embeddings
                
        except Exception as e:
            logger.error(f"Failed to create embeddings ({provider}): {e}")
            raise
    
    @classmethod
    def _create_openai_embeddings(cls, embedding_config: Dict[str, Any]) -> Embeddings:
        """Create OpenAI embeddings instance"""
        try:
            from langchain_openai import OpenAIEmbeddings
            
            kwargs = {
                "model": embedding_config["model"],  # This is OPENAI_EMBEDDING_MODEL
                "openai_api_key": embedding_config["api_key"],  # This is OPENAI_API_KEY
            }
            
            # Only set base URL if explicitly configured (for custom OpenAI endpoints)
            if embedding_config.get("base_url"):
                kwargs["openai_api_base"] = embedding_config["base_url"]  # This is OPENAI_BASE_URL
            
            embeddings = OpenAIEmbeddings(**kwargs)
            base_url_info = f", Base URL: {embedding_config['base_url']}" if embedding_config.get("base_url") else ""
            logger.info(f"OpenAI embeddings initialized successfully - Model: {embedding_config['model']}{base_url_info}")
            return embeddings
            
        except Exception as e:
            logger.error(f"OpenAI embeddings initialization failed: {e}")
            raise
    
    @classmethod
    def _create_local_embeddings(cls, embedding_config: Dict[str, Any]) -> Embeddings:
        """Create local (SentenceTransformer) embeddings instance"""
        try:
            from langchain_community.embeddings import SentenceTransformerEmbeddings
            
            # Ensure cache directory exists
            cache_dir = embedding_config.get("cache_dir")
            if cache_dir:
                Path(cache_dir).mkdir(parents=True, exist_ok=True)
                
            kwargs = {
                "model_name": embedding_config["model"]
            }
            
            if cache_dir:
                kwargs["cache_folder"] = str(cache_dir)
            
            embeddings = SentenceTransformerEmbeddings(**kwargs)
            logger.info(f"Local embeddings initialized successfully - Model: {embedding_config['model']}")
            return embeddings
            
        except Exception as e:
            logger.error(f"Local embeddings initialization failed: {e}")
            raise
    
    @classmethod
    def _create_huggingface_embeddings(cls, embedding_config: Dict[str, Any]) -> Embeddings:
        """Create HuggingFace embeddings instance"""
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            
            # Ensure cache directory exists
            cache_dir = embedding_config.get("cache_dir")
            if cache_dir:
                Path(cache_dir).mkdir(parents=True, exist_ok=True)
                
            kwargs = {
                "model_name": embedding_config["model"]
            }
            
            if cache_dir:
                kwargs["cache_folder"] = str(cache_dir)
            
            embeddings = HuggingFaceEmbeddings(**kwargs)
            logger.info(f"HuggingFace embeddings initialized successfully - Model: {embedding_config['model']}")
            return embeddings
            
        except ImportError:
            logger.error("HuggingFace dependencies not installed, please run: pip install langchain-huggingface")
            raise
        except Exception as e:
            logger.error(f"HuggingFace embeddings initialization failed: {e}")
            raise
    
    @classmethod
    def _create_ollama_embeddings(cls, embedding_config: Dict[str, Any]) -> Embeddings:
        """Create Ollama embeddings instance - Uses local SentenceTransformer model for compatibility"""
        try:
            from langchain_community.embeddings import SentenceTransformerEmbeddings
            
            # Use intfloat/multilingual-e5-small model locally instead of Ollama service
            # This provides better compatibility and avoids Ollama embedding service dependency
            local_model = "intfloat/multilingual-e5-small"
            
            # Ensure cache directory exists
            cache_dir = embedding_config.get("cache_dir", str(Path(__file__).parent.parent.parent / "data" / "embeddings_cache"))
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
                
            kwargs = {
                "model_name": local_model,
                "cache_folder": str(cache_dir)
            }
            
            embeddings = SentenceTransformerEmbeddings(**kwargs)
            logger.info(f"Ollama embeddings initialized successfully (using local model) - Model: {local_model}")
            return embeddings
            
        except ImportError:
            logger.error("SentenceTransformer dependencies not installed, please run: pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"Ollama embeddings initialization failed: {e}")
            raise
    
    @classmethod
    def _create_bedrock_embeddings(cls, embedding_config: Dict[str, Any]) -> Embeddings:
        """Create AWS Bedrock embeddings instance (no fallback)"""
        try:
            import boto3
            import json
            from langchain_core.embeddings.embeddings import Embeddings
            
            class BedrockTitanEmbeddings(Embeddings):
                """AWS Bedrock Titan Embeddings (direct, no fallback)"""
                
                def __init__(
                    self,
                    model_id: str,
                    region: str,
                    profile: Optional[str] = None,
                    access_key_id: Optional[str] = None,
                    secret_access_key: Optional[str] = None,
                    deployment_env: str = "local",
                    dimension: int = 1024
                ):
                    self.model_id = model_id
                    self.region = region
                    self.dimension = dimension
                    self.deployment_env = deployment_env
                    
                    # Build boto3 session
                    session_kwargs = {"region_name": region}
                    
                    if deployment_env in ["ecs", "ec2"]:
                        logger.info(f"Bedrock embeddings using IAM role for {deployment_env}")
                    elif access_key_id and secret_access_key:
                        session_kwargs.update({
                            "aws_access_key_id": access_key_id,
                            "aws_secret_access_key": secret_access_key,
                        })
                        logger.info("Bedrock embeddings using explicit credentials")
                    elif profile:
                        session_kwargs["profile_name"] = profile
                        logger.info(f"Bedrock embeddings using profile: {profile}")
                    else:
                        logger.info("Bedrock embeddings using default credential chain")
                    
                    # Initialize Bedrock client
                    try:
                        session = boto3.Session(**session_kwargs)
                        sts_client = session.client("sts", region_name=region)
                        identity = sts_client.get_caller_identity()
                        logger.info(f"Bedrock embeddings AWS identity verified - Account: {identity['Account']}, ARN: {identity['Arn']}")
                        
                        self._bedrock_client = session.client("bedrock-runtime", region_name=region)
                        logger.info(f"Bedrock embeddings initialized successfully - Model: {model_id}, Region: {region}, Dimension: {dimension}")
                    except Exception as e:
                        error_msg = (
                            f"Failed to initialize Bedrock embeddings client.\n"
                            f"Model: {model_id}\n"
                            f"Region: {region}\n"
                            f"Profile: {profile or 'None'}\n"
                            f"Deployment Env: {deployment_env}\n"
                            f"Error: {e}"
                        )
                        logger.error(error_msg)
                        raise RuntimeError(error_msg) from e
                
                def _embed_with_bedrock(self, text: str) -> list[float]:
                    """Call Bedrock Titan embedding API"""
                    try:
                        # Prepare request body for Titan Embeddings V2
                        request_body = {
                            "inputText": text,
                            "dimensions": self.dimension,
                            "normalize": True,
                        }
                        
                        # Call Bedrock API
                        response = self._bedrock_client.invoke_model(
                            modelId=self.model_id,
                            body=json.dumps(request_body),
                            contentType="application/json",
                            accept="application/json",
                        )
                        
                        response_body = json.loads(response["body"].read())
                        embedding = response_body.get("embedding")
                        
                        if not embedding:
                            raise ValueError(f"No embedding in Bedrock response: {response_body}")
                        
                        return embedding
                    except Exception as e:
                        error_msg = (
                            f"Bedrock embedding API call failed.\n"
                            f"Model: {self.model_id}\n"
                            f"Region: {self.region}\n"
                            f"Text length: {len(text)}\n"
                            f"Error: {e}"
                        )
                        logger.error(error_msg)
                        raise RuntimeError(error_msg) from e
                
                def embed_documents(self, texts: list[str]) -> list[list[float]]:
                    """Embed multiple documents"""
                    embeddings = []
                    for i, text in enumerate(texts):
                        try:
                            embedding = self._embed_with_bedrock(text)
                            embeddings.append(embedding)
                        except Exception as e:
                            logger.error(f"Failed to embed document {i+1}/{len(texts)}: {e}")
                            raise
                    
                    logger.info(f"Successfully embedded {len(embeddings)} documents using Bedrock Titan")
                    return embeddings
                
                def embed_query(self, text: str) -> list[float]:
                    """Embed a single query"""
                    embedding = self._embed_with_bedrock(text)
                    logger.info(f"Successfully embedded query (length: {len(text)}) using Bedrock Titan")
                    return embedding
            
            # Create Bedrock Titan embeddings instance
            embeddings = BedrockTitanEmbeddings(
                model_id=embedding_config["model"],
                region=embedding_config["region"],
                profile=embedding_config.get("profile"),
                access_key_id=embedding_config.get("access_key_id"),
                secret_access_key=embedding_config.get("secret_access_key"),
                deployment_env=embedding_config.get("deployment_env", "local"),
                dimension=embedding_config.get("dimension", 1024)
            )
            
            logger.info(f"Bedrock embeddings created - Model: {embedding_config['model']}, Region: {embedding_config['region']}")
            return embeddings
            
        except Exception as e:
            logger.error(f"Bedrock embeddings initialization failed: {e}")
            raise
    
    @classmethod
    def _create_dify_embeddings(cls, embedding_config: Dict[str, Any]) -> Embeddings:
        """Create Dify.ai embeddings instance"""
        try:
            from langchain_openai import OpenAIEmbeddings
            
            # Dify.ai uses OpenAI-compatible API for embeddings
            kwargs = {
                "model": embedding_config["model"],
                "openai_api_key": embedding_config["api_key"],
                "openai_api_base": embedding_config["base_url"],
            }
            
            # Add custom headers for Dify if user is provided
            if embedding_config.get("user"):
                kwargs["default_headers"] = {"User": embedding_config["user"]}
            
            embeddings = OpenAIEmbeddings(**kwargs)
            logger.info(f"Dify.ai embeddings initialized successfully - Model: {embedding_config['model']}, Base URL: {embedding_config['base_url']}")
            return embeddings
            
        except Exception as e:
            logger.error(f"Dify.ai embeddings initialization failed: {e}")
            raise
    
    @classmethod
    def _verify_embeddings_connection(cls, embeddings: Embeddings, provider: str) -> bool:
        """Verify embeddings connection"""
        try:
            # Send simple test text
            test_text = "Hello world"
            result = embeddings.embed_query(test_text)
            
            if result and len(result) > 0:
                logger.info(f"{provider} embeddings connection verification successful - Dimension: {len(result)}")
                return True
            else:
                logger.error(f"{provider} embeddings connection verification failed: empty result")
                return False
            
        except Exception as e:
            logger.error(f"{provider} embeddings connection verification failed: {e}")
            # For ollama provider using local model, don't treat verification failure as critical
            if provider == "ollama":
                logger.warning(f"ollama embeddings connection verification failed: {e}, but continuing...")
                return False  # Return False but don't raise exception
            return False
    
    @classmethod
    def test_embeddings_connection(cls) -> Dict[str, Any]:
        """Test embeddings connection"""
        try:
            embeddings = cls.get_embeddings()
            embedding_config = config.get_embedding_config()
            
            # Send test text
            test_text = "Hello, this is a test embedding."
            result = embeddings.embed_query(test_text)
            
            return {
                "success": True,
                "provider": embedding_config.get("provider"),
                "model": embedding_config.get("model"),
                "dimension": len(result) if result else 0,
                "sample_embedding": result[:5] if result and len(result) >= 5 else result  # First 5 dimensions
            }
            
        except Exception as e:
            embedding_config = config.get_embedding_config()
            return {
                "success": False,
                "provider": embedding_config.get("provider"),
                "error": str(e)
            }
    
    @classmethod
    def get_embeddings_status(cls) -> Dict[str, Any]:
        """Get current embeddings status"""
        try:
            embedding_config = config.get_embedding_config()
            embeddings = cls.get_embeddings()
            
            status = {
                "provider": embedding_config.get("provider"),
                "model": embedding_config.get("model"),
                "available": embeddings is not None,
                "config": {
                    "dimension": embedding_config.get("dimension"),
                    "cache_dir": str(embedding_config.get("cache_dir", "N/A"))
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
    def reset_embeddings(cls) -> bool:
        """Reset embeddings instance (force recreate on next call)"""
        try:
            cls._instance = None
            cls._current_config = None
            logger.info("Embeddings instance reset successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reset embeddings instance: {e}")
            return False

# Convenience functions for global access
def get_embeddings(force_local: bool = False) -> Embeddings:
    """Get global embeddings instance"""
    return EmbeddingFactory.get_embeddings(force_local)

def get_embeddings_status() -> Dict[str, Any]:
    """Get global embeddings status"""
    return EmbeddingFactory.get_embeddings_status()

def reset_embeddings() -> bool:
    """Reset global embeddings instance"""
    return EmbeddingFactory.reset_embeddings()

def test_embeddings_connection() -> Dict[str, Any]:
    """Test global embeddings connection"""
    return EmbeddingFactory.test_embeddings_connection() 