from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, HttpUrl
from enum import Enum


class MCPTransport(str, Enum):
    STDIO = "stdio"
    WEBSOCKET = "websocket"
    HTTP = "http"
    SSE = "sse"


class MCPToolInputProperty(BaseModel):
    type: str
    description: Optional[str] = None
    enum: Optional[List[str]] = None
    default: Optional[Any] = None
    required: bool = False


class MCPTool(BaseModel):
    name: str
    title: Optional[str] = None
    description: str
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Optional[Dict[str, Any]] = None
    annotations: Optional[Dict[str, Any]] = None
    is_destructive: bool = False
    requires_auth: bool = False
    category: Optional[str] = None


class MCPResource(BaseModel):
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None
    annotations: Optional[Dict[str, Any]] = None
    size: Optional[int] = None
    last_modified: Optional[datetime] = None


class MCPPrompt(BaseModel):
    name: str
    title: Optional[str] = None
    description: Optional[str] = None
    arguments: List[Dict[str, Any]] = Field(default_factory=list)
    annotations: Optional[Dict[str, Any]] = None
    category: Optional[str] = None


class MCPServerCapabilities(BaseModel):
    tools: bool = False
    resources: bool = False
    prompts: bool = False
    logging: bool = False
    experimental: Dict[str, Any] = Field(default_factory=dict)


class MCPServerMetadata(BaseModel):
    protocol_version: Optional[str] = None
    supported_transports: List[MCPTransport] = Field(default_factory=list)
    authentication_methods: List[str] = Field(default_factory=list)
    security_annotations: Dict[str, Any] = Field(default_factory=dict)
    capabilities: MCPServerCapabilities = Field(default_factory=MCPServerCapabilities)
    runtime_requirements: Dict[str, Any] = Field(default_factory=dict)


class MCPServerHealth(BaseModel):
    status: str = "unknown"  # unknown, healthy, unhealthy, unreachable
    last_checked: Optional[datetime] = None
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    uptime_percentage: Optional[float] = None


class MCPServer(BaseModel):
    # Basic identification
    id: str
    name: str
    description: Optional[str] = None
    url: Optional[HttpUrl] = None
    docker_image: Optional[str] = None
    
    # Repository metadata
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    source: str
    namespace: Optional[str] = None
    
    # MCP-specific metadata
    metadata: MCPServerMetadata = Field(default_factory=MCPServerMetadata)
    
    # MCP protocol data
    tools: List[MCPTool] = Field(default_factory=list)
    resources: List[MCPResource] = Field(default_factory=list)
    prompts: List[MCPPrompt] = Field(default_factory=list)
    
    # Runtime and health data
    health: MCPServerHealth = Field(default_factory=MCPServerHealth)
    last_introspected: Optional[datetime] = None
    introspection_errors: List[str] = Field(default_factory=list)
    
    # Docker-specific metadata
    docker_labels: Dict[str, str] = Field(default_factory=dict)
    docker_pull_count: Optional[int] = None
    docker_star_count: Optional[int] = None
    
    # Analytics and usage
    popularity_score: Optional[float] = None
    trust_score: Optional[float] = None
    categories: List[str] = Field(default_factory=list)


class RegistryResponse(BaseModel):
    servers: List[MCPServer]
    metadata: Optional[dict] = None


class DockerHubRepository(BaseModel):
    name: str
    namespace: str
    description: Optional[str] = None
    star_count: int = 0
    pull_count: int = 0
    last_updated: Optional[datetime] = None
    
    def to_mcp_server(self) -> MCPServer:
        return MCPServer(
            id=f"{self.namespace}/{self.name}",
            name=self.name,
            description=self.description,
            docker_image=f"{self.namespace}/{self.name}",
            namespace=self.namespace,
            source="docker_hub",
            created_at=self.last_updated,
            updated_at=self.last_updated,
            docker_pull_count=self.pull_count,
            docker_star_count=self.star_count
        )


class DockerHubResponse(BaseModel):
    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[DockerHubRepository]