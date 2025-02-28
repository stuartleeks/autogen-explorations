
import os
from dotenv import load_dotenv
load_dotenv()

def service_type():
    return _get_required_env("SERVICE_TYPE")

def openai_endpoint():
    return _get_required_env("AZURE_OPENAI_ENDPOINT")

def openai_key():
    return _get_required_env("AZURE_OPENAI_KEY")

def openai_model_name():
    return _get_required_env("AZURE_OPENAI_MODEL_NAME")

def openai_deployment_name():
    return _get_required_env("AZURE_OPENAI_DEPLOYMENT_NAME")

def openai_api_version():
    return os.getenv("AZURE_OPENAI_API_VERSION", None)

def ollama_model_id():
    return _get_required_env("OLLAMA_MODEL_ID")

def ollama_host():
    return _get_required_env("OLLAMA_HOST")

def meal_plugin_log_level():
    return os.getenv("MEAL_PLUGIN_LOG_LEVEL", "CRITICAL")

def lights_plugin_log_level():
    return os.getenv("LIGHTS_PLUGIN_LOG_LEVEL", "CRITICAL")

def semantic_kernel_log_level():
    return os.getenv("SEMANTIC_KERNEL_LOG_LEVEL", "CRITICAL")

def agent_log_level():
    return os.getenv("AGENT_LOG_LEVEL", "DEBUG")

def _get_required_env(env_var):
    value = os.getenv(env_var)
    if value is None:
        raise ValueError(
            f"${env_var} is not set in the environment variables.")
    return value