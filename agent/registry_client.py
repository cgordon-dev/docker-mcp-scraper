import httpx
from typing import List, Optional
from .models import MCPServer, RegistryResponse


class MCPRegistryClient:
    def __init__(self, base_url: str = "https://registry.modelcontextprotocol.org"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=30.0)
    
    def list_servers(self, limit: int = 100, cursor: Optional[str] = None) -> RegistryResponse:
        url = f"{self.base_url}/v0/servers"
        params = {"limit": min(limit, 100)}
        
        if cursor:
            params["cursor"] = cursor
        
        response = self.client.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        servers = []
        for server_data in data.get("servers", []):
            server = MCPServer(
                id=server_data["id"],
                name=server_data["name"],
                description=server_data.get("description"),
                url=server_data.get("url"),
                created_at=server_data.get("created_at"),
                updated_at=server_data.get("updated_at"),
                source="mcp_registry"
            )
            servers.append(server)
        
        return RegistryResponse(
            servers=servers,
            metadata=data.get("metadata", {})
        )
    
    def get_all_servers(self) -> List[MCPServer]:
        all_servers = []
        cursor = None
        
        while True:
            response = self.list_servers(cursor=cursor)
            all_servers.extend(response.servers)
            
            metadata = response.metadata or {}
            cursor = metadata.get("next_cursor")
            
            if not cursor:
                break
        
        return all_servers
    
    def get_server(self, server_id: str) -> Optional[MCPServer]:
        url = f"{self.base_url}/v0/servers/{server_id}"
        
        try:
            response = self.client.get(url)
            response.raise_for_status()
            
            data = response.json()
            return MCPServer(
                id=data["id"],
                name=data["name"],
                description=data.get("description"),
                url=data.get("url"),
                created_at=data.get("created_at"),
                updated_at=data.get("updated_at"),
                source="mcp_registry"
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def close(self):
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()