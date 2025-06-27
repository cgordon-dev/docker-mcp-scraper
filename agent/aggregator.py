import asyncio
from datetime import datetime
from typing import List, Dict, Set, Optional, Any
from .models import MCPServer
from .registry_client import MCPRegistryClient
from .dockerhub_client import DockerHubClient
from .github_client import GitHubMCPClient
from .mcp_client import MCPClient, mcp_client
from .database import MCPDatabase, database
from .logger import logger


class MCPServerAggregator:
    def __init__(self, use_database: bool = True, database_url: Optional[str] = None, github_token: Optional[str] = None):
        self.registry_client = MCPRegistryClient(github_token=github_token)
        self.dockerhub_client = DockerHubClient()
        self.github_client = GitHubMCPClient(github_token)
        self.mcp_client = None
        self.use_database = use_database
        
        if self.use_database:
            if database_url:
                self.database = MCPDatabase(database_url)
            else:
                self.database = database
        else:
            self.database = None
    
    def fetch_all_servers(self, dockerhub_auth: tuple = None, include_github: bool = True, github_query: str = "") -> List[MCPServer]:
        """Fetch servers from all sources with basic metadata."""
        all_servers = []
        
        logger.info("Starting to fetch servers from all sources", include_github=include_github)
        
        # Fetch from MCP Community Registry
        try:
            logger.info("Fetching servers from MCP Community Registry")
            registry_servers = self.registry_client.get_all_servers()
            all_servers.extend(registry_servers)
            logger.info(f"Fetched {len(registry_servers)} servers from MCP Community Registry")
        except Exception as e:
            logger.error("Error fetching from MCP Registry", error=e)
        
        # Fetch from Docker Hub MCP namespace
        try:
            logger.info("Fetching servers from Docker Hub")
            if dockerhub_auth:
                username, password = dockerhub_auth
                self.dockerhub_client.authenticate(username, password)
            
            dockerhub_servers = self.dockerhub_client.get_mcp_servers()
            all_servers.extend(dockerhub_servers)
            logger.info(f"Fetched {len(dockerhub_servers)} servers from Docker Hub")
        except Exception as e:
            logger.error("Error fetching from Docker Hub", error=e)
        
        # Fetch from GitHub
        if include_github:
            try:
                logger.info("Fetching servers from GitHub")
                github_servers = self.github_client.get_mcp_servers(query=github_query)
                all_servers.extend(github_servers)
                logger.info(f"Fetched {len(github_servers)} servers from GitHub")
            except Exception as e:
                logger.error("Error fetching from GitHub", error=e)
        
        deduplicated_servers = self.deduplicate_servers(all_servers)
        logger.info(
            f"Completed fetching servers from all sources",
            total_fetched=len(all_servers),
            after_deduplication=len(deduplicated_servers)
        )
        
        return deduplicated_servers
    
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
        
        # Basic metadata
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
        
        # MCP-specific data (higher value)
        if server.tools:
            score += 5 + len(server.tools)
        if server.resources:
            score += 3 + len(server.resources)
        if server.prompts:
            score += 3 + len(server.prompts)
        if server.metadata.protocol_version:
            score += 2
        if server.docker_labels:
            score += 2
        
        # Health and introspection data
        if server.health.status == "healthy":
            score += 3
        if server.last_introspected:
            score += 2
        
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
        """Enhanced search servers by name, description, tools, or categories."""
        query_lower = query.lower()
        results = []
        
        for server in servers:
            # Search in name and description
            if (query_lower in server.name.lower() or 
                (server.description and query_lower in server.description.lower())):
                results.append(server)
                continue
            
            # Search in tool names and descriptions
            for tool in server.tools:
                if (query_lower in tool.name.lower() or 
                    query_lower in tool.description.lower()):
                    results.append(server)
                    break
            
            # Search in categories
            if any(query_lower in cat.lower() for cat in server.categories):
                results.append(server)
                continue
            
            # Search in Docker labels
            for label_key, label_value in server.docker_labels.items():
                if query_lower in label_key.lower() or query_lower in label_value.lower():
                    results.append(server)
                    break
        
        return results
    
    async def fetch_all_servers_with_introspection(
        self, 
        dockerhub_auth: tuple = None, 
        introspect: bool = True,
        max_concurrent_introspection: int = 5,
        use_cache: bool = True,
        include_github: bool = True,
        github_query: str = ""
    ) -> List[MCPServer]:
        """Fetch servers and perform full introspection to discover capabilities."""
        
        # Check if we can use cached data from database
        if use_cache and self.database:
            cached_servers = self.database.get_all_servers()
            if cached_servers:
                logger.info(f"Found {len(cached_servers)} servers in database cache")
                
                # Check if we need to refresh based on last introspection time
                needs_refresh = any(
                    not server.last_introspected or 
                    (datetime.now() - server.last_introspected).days > 1  # Refresh daily
                    for server in cached_servers
                )
                
                if not needs_refresh:
                    logger.info("Using cached server data from database")
                    return cached_servers
                else:
                    logger.info("Cached data is stale, refreshing...")
        
        # First, get basic server information
        servers = self.fetch_all_servers(dockerhub_auth, include_github, github_query)
        
        if not introspect:
            # Save basic server info to database
            if self.database:
                self.database.save_servers(servers)
            return servers
        
        logger.info(f"Starting introspection of {len(servers)} servers")
        
        # Perform batch introspection
        async with mcp_client() as client:
            introspected_servers = await client.batch_introspect(
                servers, 
                max_concurrent=max_concurrent_introspection
            )
        
        # Re-deduplicate after introspection (scores may have changed)
        final_servers = self.deduplicate_servers(introspected_servers)
        
        # Save to database
        if self.database:
            logger.info("Saving introspection results to database")
            self.database.save_servers(final_servers)
        
        # Log introspection results
        healthy_servers = [s for s in final_servers if s.health.status == "healthy"]
        total_tools = sum(len(s.tools) for s in final_servers)
        total_resources = sum(len(s.resources) for s in final_servers)
        total_prompts = sum(len(s.prompts) for s in final_servers)
        
        logger.info(
            f"Completed server introspection",
            total_servers=len(final_servers),
            healthy_servers=len(healthy_servers),
            total_tools=total_tools,
            total_resources=total_resources,
            total_prompts=total_prompts
        )
        
        return final_servers
    
    def get_servers_with_tools(self, servers: List[MCPServer]) -> List[MCPServer]:
        """Filter servers that have tools available."""
        return [server for server in servers if server.tools]
    
    def get_servers_with_resources(self, servers: List[MCPServer]) -> List[MCPServer]:
        """Filter servers that have resources available."""
        return [server for server in servers if server.resources]
    
    def get_servers_with_prompts(self, servers: List[MCPServer]) -> List[MCPServer]:
        """Filter servers that have prompts available."""
        return [server for server in servers if server.prompts]
    
    def get_tool_statistics(self, servers: List[MCPServer]) -> Dict[str, int]:
        """Get statistics about tools across all servers."""
        tool_names = {}
        for server in servers:
            for tool in server.tools:
                tool_names[tool.name] = tool_names.get(tool.name, 0) + 1
        return tool_names
    
    def get_server_health_summary(self, servers: List[MCPServer]) -> Dict[str, int]:
        """Get health status summary across all servers."""
        health_counts = {}
        for server in servers:
            status = server.health.status
            health_counts[status] = health_counts.get(status, 0) + 1
        return health_counts
    
    def search_by_tool(self, servers: List[MCPServer], tool_name: str) -> List[MCPServer]:
        """Search for servers that provide a specific tool."""
        results = []
        tool_name_lower = tool_name.lower()
        
        for server in servers:
            for tool in server.tools:
                if tool_name_lower in tool.name.lower():
                    results.append(server)
                    break
        
        return results
    
    def search_by_category(self, servers: List[MCPServer], category: str) -> List[MCPServer]:
        """Search for servers by category."""
        results = []
        category_lower = category.lower()
        
        for server in servers:
            # Check server categories
            if any(category_lower in cat.lower() for cat in server.categories):
                results.append(server)
                continue
            
            # Check tool categories
            for tool in server.tools:
                if tool.category and category_lower in tool.category.lower():
                    results.append(server)
                    break
        
        return results
    
    def get_cached_servers(self) -> List[MCPServer]:
        """Get servers from database cache."""
        if not self.database:
            return []
        return self.database.get_all_servers()
    
    def search_cached_servers(self, **kwargs) -> List[MCPServer]:
        """Search servers in database cache."""
        if not self.database:
            return []
        return self.database.search_servers(**kwargs)
    
    def get_database_statistics(self) -> Dict[str, Any]:
        """Get statistics from database."""
        if not self.database:
            return {}
        return self.database.get_statistics()
    
    def get_github_servers(self, servers: List[MCPServer]) -> List[MCPServer]:
        """Filter servers that come from GitHub."""
        return [server for server in servers if server.source == "github"]
    
    def search_by_language(self, servers: List[MCPServer], language: str) -> List[MCPServer]:
        """Search for servers by programming language (primarily for GitHub repos)."""
        results = []
        language_lower = language.lower()
        
        for server in servers:
            # Check categories which include programming languages
            if any(language_lower in cat.lower() for cat in server.categories):
                results.append(server)
        
        return results
    
    def search_by_github_topics(self, servers: List[MCPServer], topic: str) -> List[MCPServer]:
        """Search for servers by GitHub topics/tags."""
        results = []
        topic_lower = topic.lower()
        
        for server in servers:
            if server.source == "github" and any(topic_lower in tag.lower() for tag in server.tags):
                results.append(server)
        
        return results
    
    def get_github_statistics(self, servers: List[MCPServer]) -> Dict[str, Any]:
        """Get GitHub-specific statistics."""
        github_servers = self.get_github_servers(servers)
        
        if not github_servers:
            return {}
        
        # Language distribution
        languages = {}
        for server in github_servers:
            for category in server.categories:
                if category in ['javascript', 'typescript', 'python', 'go', 'rust', 'java', 'c++', 'c#']:
                    languages[category] = languages.get(category, 0) + 1
        
        # Topic distribution
        topics = {}
        for server in github_servers:
            for topic in server.tags:
                topics[topic] = topics.get(topic, 0) + 1
        
        # Trust score distribution
        high_trust = len([s for s in github_servers if s.trust_score and s.trust_score > 0.7])
        medium_trust = len([s for s in github_servers if s.trust_score and 0.3 < s.trust_score <= 0.7])
        low_trust = len([s for s in github_servers if s.trust_score and s.trust_score <= 0.3])
        
        return {
            "total_github_servers": len(github_servers),
            "by_language": dict(sorted(languages.items(), key=lambda x: x[1], reverse=True)[:10]),
            "by_topic": dict(sorted(topics.items(), key=lambda x: x[1], reverse=True)[:10]),
            "trust_distribution": {
                "high_trust": high_trust,
                "medium_trust": medium_trust,
                "low_trust": low_trust
            }
        }
    
    def close(self):
        """Close all clients."""
        self.registry_client.close()
        self.dockerhub_client.close()
        self.github_client.close()
        if self.database:
            self.database.close()
        if self.mcp_client:
            # Note: This is sync, but mcp_client should be used with async context manager
            pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()