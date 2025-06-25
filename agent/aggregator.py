from typing import List, Dict, Set
from .models import MCPServer
from .registry_client import MCPRegistryClient
from .dockerhub_client import DockerHubClient


class MCPServerAggregator:
    def __init__(self):
        self.registry_client = MCPRegistryClient()
        self.dockerhub_client = DockerHubClient()
    
    def fetch_all_servers(self, dockerhub_auth: tuple = None) -> List[MCPServer]:
        all_servers = []
        
        # Fetch from MCP Community Registry
        try:
            registry_servers = self.registry_client.get_all_servers()
            all_servers.extend(registry_servers)
        except Exception as e:
            print(f"Error fetching from MCP Registry: {e}")
        
        # Fetch from Docker Hub MCP namespace
        try:
            if dockerhub_auth:
                username, password = dockerhub_auth
                self.dockerhub_client.authenticate(username, password)
            
            dockerhub_servers = self.dockerhub_client.get_mcp_servers()
            all_servers.extend(dockerhub_servers)
        except Exception as e:
            print(f"Error fetching from Docker Hub: {e}")
        
        return self.deduplicate_servers(all_servers)
    
    def deduplicate_servers(self, servers: List[MCPServer]) -> List[MCPServer]:
        seen_ids: Set[str] = set()
        seen_names: Dict[str, MCPServer] = {}
        deduplicated = []
        
        for server in servers:
            # First, check for exact ID matches
            if server.id in seen_ids:
                continue
            
            # Then check for name matches (case-insensitive)
            name_key = server.name.lower()
            
            if name_key in seen_names:
                existing = seen_names[name_key]
                # Prefer servers with more complete information
                if self._is_more_complete(server, existing):
                    # Replace the existing server
                    deduplicated = [s for s in deduplicated if s.id != existing.id]
                    deduplicated.append(server)
                    seen_names[name_key] = server
                    seen_ids.add(server.id)
                # Skip the current server if existing is more complete
                continue
            
            # Add new server
            deduplicated.append(server)
            seen_ids.add(server.id)
            seen_names[name_key] = server
        
        return deduplicated
    
    def _is_more_complete(self, server1: MCPServer, server2: MCPServer) -> bool:
        """Compare two servers and return True if server1 has more complete information"""
        score1 = self._completeness_score(server1)
        score2 = self._completeness_score(server2)
        return score1 > score2
    
    def _completeness_score(self, server: MCPServer) -> int:
        """Calculate a completeness score for a server based on available fields"""
        score = 0
        
        if server.description:
            score += 2
        if server.url:
            score += 2
        if server.docker_image:
            score += 3
        if server.tags:
            score += len(server.tags)
        if server.created_at:
            score += 1
        if server.updated_at:
            score += 1
        
        # Prefer Docker Hub sources for Docker images
        if server.source == "docker_hub" and server.docker_image:
            score += 2
        
        return score
    
    def get_servers_by_source(self, servers: List[MCPServer]) -> Dict[str, List[MCPServer]]:
        """Group servers by their source"""
        by_source = {}
        for server in servers:
            if server.source not in by_source:
                by_source[server.source] = []
            by_source[server.source].append(server)
        return by_source
    
    def search_servers(self, servers: List[MCPServer], query: str) -> List[MCPServer]:
        """Search servers by name or description"""
        query_lower = query.lower()
        results = []
        
        for server in servers:
            if (query_lower in server.name.lower() or 
                (server.description and query_lower in server.description.lower())):
                results.append(server)
        
        return results
    
    def close(self):
        self.registry_client.close()
        self.dockerhub_client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()