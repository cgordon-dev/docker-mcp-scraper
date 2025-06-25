from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class MCPServer(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    url: Optional[str] = None
    docker_image: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    source: str
    namespace: Optional[str] = None


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
            updated_at=self.last_updated
        )


class DockerHubResponse(BaseModel):
    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[DockerHubRepository]