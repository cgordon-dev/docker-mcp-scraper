import httpx
from typing import List, Optional
from .models import MCPServer, RegistryResponse
from .github_registry_client import GitHubRegistryClient
from .logger import logger, log_api_call, RegistryError


class MCPRegistryClient:
    def __init__(self, base_url: str = "https://registry.modelcontextprotocol.org", github_token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.github_token = github_token
        self.client = httpx.Client(
            timeout=30.0,
            headers={"User-Agent": "MCP-Scraper/1.0"}
        )
        
        # Initialize GitHub registry client as primary source
        self.github_client = GitHubRegistryClient(github_token)
        
        logger.info(
            "MCP Registry client initialized", 
            base_url=self.base_url,
            using_github_primary=True,
            has_github_token=bool(github_token)
        )
    
    @log_api_call("mcp_registry", "/v0/servers")
    def list_servers(self, limit: int = 100, cursor: Optional[str] = None) -> RegistryResponse:
        url = f"{self.base_url}/v0/servers"
        params = {"limit": min(limit, 100)}
        
        if cursor:
            params["cursor"] = cursor
        
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            servers = []
            failed_servers = []
            
            for server_data in data.get("servers", []):
                try:
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
                except Exception as e:
                    failed_servers.append(server_data.get("id", "unknown"))
                    logger.warning(
                        "Failed to parse server data from MCP registry",
                        error=e,
                        server_id=server_data.get("id", "unknown")
                    )
            
            if failed_servers:
                logger.warning(
                    f"Failed to parse {len(failed_servers)} servers from MCP registry",
                    failed_servers=failed_servers
                )
            
            logger.info(
                f"Successfully fetched {len(servers)} servers from MCP registry",
                total_servers=len(servers),
                failed_servers=len(failed_servers)
            )
            
            return RegistryResponse(
                servers=servers,
                metadata=data.get("metadata", {})
            )
            
        except httpx.RequestError as e:
            raise RegistryError(
                f"Failed to connect to MCP registry: {str(e)}",
                registry="mcp_registry"
            )
        except httpx.HTTPStatusError as e:
            raise RegistryError(
                f"MCP registry returned error: {e.response.status_code} {e.response.reason_phrase}",
                registry="mcp_registry",
                status_code=e.response.status_code
            )
        except Exception as e:
            raise RegistryError(
                f"Unexpected error fetching from MCP registry: {str(e)}",
                registry="mcp_registry"
            )
    
    def get_all_servers(self) -> List[MCPServer]:
        """Fetch all servers from MCP registry with GitHub as primary source."""
        logger.info("Starting to fetch all servers from MCP registry (GitHub + HTTP fallback)")
        
        # Try GitHub registry first (primary source)
        try:
            logger.info("Fetching servers from GitHub registry")
            import asyncio
            
            # Handle case where we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                # We're in an existing event loop, need to use different approach
                logger.warning("Already in event loop, skipping GitHub registry for now")
                github_servers = []
            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                github_servers = asyncio.run(self.github_client.get_all_servers())
            
            if github_servers:
                logger.info(
                    f"Successfully fetched servers from GitHub registry",
                    total_servers=len(github_servers),
                    total_tools=sum(len(s.tools) for s in github_servers)
                )
                return github_servers
            else:
                logger.warning("GitHub registry returned no servers, trying HTTP fallback")
        
        except Exception as e:
            logger.warning(
                "Failed to fetch from GitHub registry, trying HTTP fallback",
                error=e
            )
        
        # Fallback to HTTP registry
        try:
            return self._get_all_servers_http()
        except Exception as e:
            logger.error("All registry sources failed", error=e)
            raise RegistryError(
                "Failed to fetch from both GitHub and HTTP registry sources",
                "all_registries"
            )
    
    def _get_all_servers_http(self) -> List[MCPServer]:
        """Fetch all servers from HTTP MCP registry with pagination (fallback)."""
        all_servers = []
        cursor = None
        page = 1
        
        logger.info("Starting to fetch all servers from HTTP MCP registry")
        
        try:
            while True:
                logger.debug(f"Fetching page {page} from HTTP MCP registry", cursor=cursor)
                
                response = self.list_servers(cursor=cursor)
                all_servers.extend(response.servers)
                
                metadata = response.metadata or {}
                cursor = metadata.get("next_cursor")
                
                logger.debug(
                    f"Page {page} completed",
                    servers_on_page=len(response.servers),
                    total_servers=len(all_servers),
                    has_next_page=bool(cursor)
                )
                
                if not cursor:
                    break
                
                page += 1
            
            logger.info(
                f"Successfully fetched all servers from HTTP MCP registry",
                total_servers=len(all_servers),
                total_pages=page
            )
            
            return all_servers
            
        except Exception as e:
            logger.error(
                "Failed to fetch all servers from HTTP MCP registry",
                error=e,
                servers_fetched=len(all_servers),
                last_page=page
            )
            raise
    
    @log_api_call("mcp_registry", "/v0/servers/{id}")
    def get_server(self, server_id: str) -> Optional[MCPServer]:
        """Fetch a specific server from MCP registry."""
        url = f"{self.base_url}/v0/servers/{server_id}"
        
        try:
            response = self.client.get(url)
            response.raise_for_status()
            
            data = response.json()
            server = MCPServer(
                id=data["id"],
                name=data["name"],
                description=data.get("description"),
                url=data.get("url"),
                created_at=data.get("created_at"),
                updated_at=data.get("updated_at"),
                source="mcp_registry"
            )
            
            logger.debug(f"Successfully fetched server from MCP registry", server_id=server_id)
            return server
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"Server not found in MCP registry", server_id=server_id)
                return None
            
            logger.error(
                f"Failed to fetch server from MCP registry",
                server_id=server_id,
                status_code=e.response.status_code,
                error=e
            )
            raise RegistryError(
                f"Failed to fetch server {server_id}: {e.response.status_code} {e.response.reason_phrase}",
                registry="mcp_registry",
                status_code=e.response.status_code
            )
        except Exception as e:
            logger.error(
                f"Unexpected error fetching server from MCP registry",
                server_id=server_id,
                error=e
            )
            raise
    
    def close(self):
        """Close the HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
        if hasattr(self, 'github_client'):
            self.github_client.close()
        logger.debug("MCP Registry client closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()