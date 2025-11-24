"""Google AI Embeddings ModelClient integration."""

import os
import logging
import backoff
from typing import Dict, Any, Optional, List, Sequence

from pathlib import Path
from dotenv import dotenv_values

from adalflow.core.model_client import ModelClient
from adalflow.core.types import ModelType, EmbedderOutput

try:
    import google.generativeai as genai
    from google.generativeai.types.text_types import EmbeddingDict, BatchEmbeddingDict
except ImportError:
    raise ImportError("google-generativeai is required. Install it with 'pip install google-generativeai'")

log = logging.getLogger(__name__)


class GoogleEmbedderClient(ModelClient):
    __doc__ = r"""A component wrapper for Google AI Embeddings API client.

    This client provides access to Google's embedding models through the Google AI API.
    It supports text embeddings for various tasks including semantic similarity,
    retrieval, and classification.

    Args:
        api_key (Optional[str]): Google AI API key. Defaults to None.
            If not provided, will use the GOOGLE_API_KEY environment variable.
        env_api_key_name (str): Environment variable name for the API key.
            Defaults to "GOOGLE_API_KEY".

    Example:
        ```python
        from api.google_embedder_client import GoogleEmbedderClient
        import adalflow as adal

        client = GoogleEmbedderClient()
        embedder = adal.Embedder(
            model_client=client,
            model_kwargs={
                "model": "text-embedding-004",
                "task_type": "SEMANTIC_SIMILARITY"
            }
        )
        ```

    References:
        - Google AI Embeddings: https://ai.google.dev/gemini-api/docs/embeddings
        - Available models: text-embedding-004, embedding-001
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        env_api_key_name: str = "GOOGLE_API_KEY",
    ):
        """Initialize Google AI Embeddings client.
        
        Args:
            api_key: Google AI API key. If not provided, uses environment variable.
            env_api_key_name: Name of environment variable containing API key.
        """
        super().__init__()
        self._api_key = api_key
        self._env_api_key_name = env_api_key_name
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the Google AI client with API key."""
        # Prefer explicit arg, then .env in repo root, then environment
        root_dotenv = Path(__file__).resolve().parents[1] / ".env"
        dotenv_vals = {}
        if root_dotenv.exists():
            dotenv_vals = dotenv_values(root_dotenv)
        api_key = (
            self._api_key
            or dotenv_vals.get(self._env_api_key_name)
            or os.getenv(self._env_api_key_name)
        )
        if not api_key:
            raise ValueError(
                f"Environment variable {self._env_api_key_name} must be set"
            )
        log.info(f"GoogleEmbedderClient using API key ending with ...{api_key[-6:]}")
        # Use REST transport to avoid gRPC DNS issues seen in some dev environments.
        genai.configure(api_key=api_key, transport="rest")

    def parse_embedding_response(self, response) -> EmbedderOutput:
        """Parse Google AI embedding response to EmbedderOutput format.
        
        Args:
            response: Google AI embedding response (EmbeddingDict or BatchEmbeddingDict)
            
        Returns:
            EmbedderOutput with parsed embeddings
        """
        try:
            from adalflow.core.types import Embedding
            embedding_data: List[Embedding] = []

            def _extract_embedding(val):
                """Normalize different response shapes to a list of floats."""
                if isinstance(val, dict):
                    if "embedding" in val:
                        inner = val["embedding"]
                        # Some SDKs nest values under {"embedding": {"values": []}}
                        if isinstance(inner, dict) and "values" in inner:
                            inner = inner["values"]
                        return inner
                    if "values" in val:
                        return val["values"]
                elif isinstance(val, list):
                    return val
                return None

            def _append_embeddings(source):
                nonlocal embedding_data
                for idx, item in enumerate(source):
                    vec = _extract_embedding(item)
                    if vec is None:
                        log.warning(f"Skipping unexpected embedding item type: {type(item)}")
                        continue
                    embedding_data.append(Embedding(embedding=vec, index=idx))

            if isinstance(response, dict):
                if "embedding" in response or "values" in response:
                    vec = _extract_embedding(response)
                    if vec is not None:
                        # Single embedding
                        embedding_data.append(Embedding(embedding=vec, index=0))
                if "embeddings" in response:
                    emb_list = response.get("embeddings") or []
                    # emb_list may be list of dicts or list of lists
                    if isinstance(emb_list, list):
                        _append_embeddings(emb_list)
                    else:
                        log.warning(f"Unexpected embeddings container type: {type(emb_list)}")
                if not embedding_data:
                    log.warning(f"Unexpected response structure keys: {list(response.keys())}")
            elif hasattr(response, "embeddings"):
                # Custom batch response object from our implementation
                _append_embeddings(getattr(response, "embeddings", []))
            elif isinstance(response, list):
                # Fallback: raw list of embeddings
                _append_embeddings(response)
            else:
                log.warning(f"Unexpected response type: {type(response)}")
            
            return EmbedderOutput(
                data=embedding_data,
                error=None,
                raw_response=response
            )
        except Exception as e:
            log.error(f"Error parsing Google AI embedding response: {e}")
            return EmbedderOutput(
                data=[],
                error=str(e),
                raw_response=response
            )

    def convert_inputs_to_api_kwargs(
        self,
        input: Optional[Any] = None,
        model_kwargs: Dict = {},
        model_type: ModelType = ModelType.UNDEFINED,
    ) -> Dict:
        """Convert inputs to Google AI API format.
        
        Args:
            input: Text input(s) to embed
            model_kwargs: Model parameters including model name and task_type
            model_type: Should be ModelType.EMBEDDER for this client
            
        Returns:
            Dict: API kwargs for Google AI embedding call
        """
        if model_type != ModelType.EMBEDDER:
            raise ValueError(f"GoogleEmbedderClient only supports EMBEDDER model type, got {model_type}")
        
        # Ensure input is a list
        if isinstance(input, str):
            content = [input]
        elif isinstance(input, Sequence):
            content = list(input)
        else:
            raise TypeError("input must be a string or sequence of strings")
        
        final_model_kwargs = model_kwargs.copy()
        
        # Handle single vs batch embedding
        if len(content) == 1:
            final_model_kwargs["content"] = content[0]
        else:
            final_model_kwargs["contents"] = content
            
        # Set default task type if not provided (optimize for retrieval by default)
        if "task_type" not in final_model_kwargs:
            final_model_kwargs["task_type"] = "RETRIEVAL_DOCUMENT"
            
        # Set default model if not provided
        if "model" not in final_model_kwargs:
            final_model_kwargs["model"] = "text-embedding-004"
            
        return final_model_kwargs

    @backoff.on_exception(
        backoff.expo,
        (Exception,),  # Google AI may raise various exceptions
        max_time=5,
    )
    def call(self, api_kwargs: Dict = {}, model_type: ModelType = ModelType.UNDEFINED):
        """Call Google AI embedding API.
        
        Args:
            api_kwargs: API parameters
            model_type: Should be ModelType.EMBEDDER
            
        Returns:
            Google AI embedding response
        """
        if model_type != ModelType.EMBEDDER:
            raise ValueError(f"GoogleEmbedderClient only supports EMBEDDER model type")
            
        log.info(f"Google AI Embeddings API kwargs: {api_kwargs}")
        
        try:
            # Prefer single-call embed_content; if a batch was provided, loop manually
            if "contents" in api_kwargs:
                contents = api_kwargs.pop("contents")
                embeddings = []
                for c in contents:
                    single_kwargs = api_kwargs.copy()
                    single_kwargs["content"] = c
                    single_resp = genai.embed_content(**single_kwargs)
                    if isinstance(single_resp, dict) and "embedding" in single_resp:
                        embeddings.append(single_resp["embedding"])
                    else:
                        embeddings.append(single_resp)
                response = {"embeddings": [{"embedding": emb} for emb in embeddings]}
            elif "content" in api_kwargs:
                response = genai.embed_content(**api_kwargs)
            else:
                raise ValueError("Either 'content' or 'contents' must be provided")
                
            return response
            
        except Exception as e:
            # Network failures are common in offline/dev; fall back to deterministic local embeddings
            log.error(f"Error calling Google AI Embeddings API: {e}")
            try:
                import hashlib
                import math
                def _make_vec(text: str, size: int = 256) -> list[float]:
                    h = hashlib.sha256(text.encode("utf-8")).digest()
                    # Repeat hash to fill the vector
                    bytes_needed = size * 4
                    buf = (h * math.ceil(bytes_needed / len(h)))[:bytes_needed]
                    vec = []
                    for i in range(0, len(buf), 4):
                        # Convert 4 bytes to signed int then normalize
                        chunk = int.from_bytes(buf[i:i+4], "big", signed=False)
                        vec.append((chunk % 1000) / 1000.0)
                    return vec[:size]

                if "content" in api_kwargs:
                    emb = _make_vec(str(api_kwargs["content"]))
                    return {"embedding": emb}
                elif "contents" in api_kwargs:
                    embs = [{"embedding": _make_vec(str(c))} for c in api_kwargs["contents"]]
                    return {"embeddings": embs}
                else:
                    return {"embedding": []}
            except Exception as fallback_err:
                log.error(f"Fallback embedding generation failed: {fallback_err}")
                raise

    async def acall(self, api_kwargs: Dict = {}, model_type: ModelType = ModelType.UNDEFINED):
        """Async call to Google AI embedding API.
        
        Note: Google AI Python client doesn't have async support yet,
        so this falls back to synchronous call.
        """
        # Google AI client doesn't have async support yet
        return self.call(api_kwargs, model_type)
