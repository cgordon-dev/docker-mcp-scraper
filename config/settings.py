import os
from dotenv import load_dotenv

load_dotenv()

# MCP Registry Settings
MCP_REGISTRY_URL = os.getenv("MCP_REGISTRY_URL", "https://registry.modelcontextprotocol.org")

# Docker Hub Settings
DOCKERHUB_USERNAME = os.getenv("DOCKERHUB_USERNAME")
DOCKERHUB_PASSWORD = os.getenv("DOCKERHUB_PASSWORD")
DOCKERHUB_BASE_URL = os.getenv("DOCKERHUB_BASE_URL", "https://hub.docker.com")

# API Settings
DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", "100"))
MAX_PAGE_SIZE = int(os.getenv("MAX_PAGE_SIZE", "1000"))

# Web Settings
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8000"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"