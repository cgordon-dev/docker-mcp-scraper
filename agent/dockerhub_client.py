import httpx
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from .models import DockerHubRepository, DockerHubResponse, MCPServer, MCPServerMetadata, MCPTransport
from .logger import logger, log_api_call, DockerError, RegistryError


class DockerHubClient:
    def __init__(self, base_url: str = "https://hub.docker.com"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            timeout=30.0,
            headers={"User-Agent": "MCP-Scraper/1.0"}
        )
        self.token: Optional[str] = None
        logger.info("Docker Hub client initialized", base_url=self.base_url)
    
    @log_api_call("docker_hub", "/v2/users/login/")
    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate with Docker Hub for higher rate limits."""
        auth_url = f"{self.base_url}/v2/users/login/"
        auth_data = {"username": username, "password": password}
        
        try:
            response = self.client.post(auth_url, json=auth_data)
            response.raise_for_status()
            
            self.token = response.json().get("token")
            success = self.token is not None
            
            if success:
                logger.info("Successfully authenticated with Docker Hub", username=username)
            else:
                logger.warning("Docker Hub authentication returned no token", username=username)
            
            return success
            
        except httpx.HTTPError as e:
            logger.error(
                "Failed to authenticate with Docker Hub",
                username=username,
                error=e
            )
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"JWT {self.token}"
        return headers
    
    @log_api_call("docker_hub", "/v2/repositories/{namespace}/")
    def list_repositories(self, namespace: str, page_size: int = 100, page: int = 1) -> DockerHubResponse:
        """List repositories in a Docker Hub namespace."""
        url = f"{self.base_url}/v2/repositories/{namespace}/"
        params = {
            "page_size": min(page_size, 100),
            "page": page
        }
        
        try:
            response = self.client.get(url, params=params, headers=self._get_headers())
            response.raise_for_status()
            
            data = response.json()
            
            repositories = []
            failed_repos = []
            
            for repo_data in data.get("results", []):
                try:
                    last_updated = None
                    if repo_data.get("last_updated"):
                        try:
                            last_updated = datetime.fromisoformat(
                                repo_data["last_updated"].replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError) as e:
                            logger.debug(
                                "Failed to parse last_updated timestamp",
                                timestamp=repo_data.get("last_updated"),
                                error=e
                            )
                    
                    repo = DockerHubRepository(
                        name=repo_data["name"],
                        namespace=repo_data["namespace"],
                        description=repo_data.get("description", ""),
                        star_count=repo_data.get("star_count", 0),
                        pull_count=repo_data.get("pull_count", 0),
                        last_updated=last_updated
                    )
                    repositories.append(repo)
                    
                except Exception as e:
                    repo_name = repo_data.get("name", "unknown")
                    failed_repos.append(repo_name)
                    logger.warning(
                        "Failed to parse repository data from Docker Hub",
                        namespace=namespace,
                        repository=repo_name,
                        error=e
                    )
            
            if failed_repos:
                logger.warning(
                    f"Failed to parse {len(failed_repos)} repositories from Docker Hub",
                    namespace=namespace,
                    failed_repos=failed_repos
                )
            
            logger.debug(
                f"Successfully fetched repositories from Docker Hub",
                namespace=namespace,
                page=page,
                repositories_count=len(repositories),
                failed_count=len(failed_repos)
            )
            
            return DockerHubResponse(
                count=data.get("count", 0),
                next=data.get("next"),
                previous=data.get("previous"),
                results=repositories
            )
            
        except httpx.RequestError as e:
            raise RegistryError(
                f"Failed to connect to Docker Hub: {str(e)}",
                registry="docker_hub"
            )
        except httpx.HTTPStatusError as e:
            raise RegistryError(
                f"Docker Hub returned error: {e.response.status_code} {e.response.reason_phrase}",
                registry="docker_hub",
                status_code=e.response.status_code
            )
        except Exception as e:
            raise RegistryError(
                f"Unexpected error fetching from Docker Hub: {str(e)}",
                registry="docker_hub"
            )
    
    def get_all_repositories(self, namespace: str) -> List[DockerHubRepository]:
        """Fetch all repositories from a Docker Hub namespace with pagination."""
        all_repositories = []
        page = 1
        
        logger.info(f"Starting to fetch all repositories from Docker Hub namespace", namespace=namespace)
        
        try:
            while True:
                logger.debug(f"Fetching page {page} from Docker Hub", namespace=namespace, page=page)
                
                response = self.list_repositories(namespace, page=page)
                all_repositories.extend(response.results)
                
                logger.debug(
                    f"Page {page} completed",
                    namespace=namespace,
                    repos_on_page=len(response.results),
                    total_repos=len(all_repositories),
                    has_next_page=bool(response.next)
                )
                
                if not response.next:
                    break
                
                page += 1
            
            logger.info(
                f"Successfully fetched all repositories from Docker Hub namespace",
                namespace=namespace,
                total_repositories=len(all_repositories),
                total_pages=page
            )
            
            return all_repositories
            
        except Exception as e:
            logger.error(
                "Failed to fetch all repositories from Docker Hub",
                namespace=namespace,
                error=e,
                repositories_fetched=len(all_repositories),
                last_page=page
            )
            raise
    
    def get_mcp_servers(self) -> List[MCPServer]:
        """Fetch all MCP servers from Docker Hub with enhanced metadata."""
        logger.info("Starting to fetch MCP servers from Docker Hub")
        
        try:
            repositories = self.get_all_repositories("mcp")
            servers = []
            manifest_failures = []
            
            for repo in repositories:
                try:
                    server = repo.to_mcp_server()
                    
                    # Enhance with Docker manifest data
                    logger.debug(f"Fetching manifest for MCP server", server_name=repo.name)
                    manifest_data = self.get_image_manifest(repo.namespace, repo.name)
                    
                    if manifest_data:
                        server.docker_labels = manifest_data.get("labels", {})
                        server.metadata = self._extract_mcp_metadata_from_labels(manifest_data.get("labels", {}))
                        logger.debug(
                            f"Successfully enhanced MCP server with manifest data",
                            server_name=repo.name,
                            labels_count=len(server.docker_labels)
                        )
                    else:
                        manifest_failures.append(repo.name)
                        logger.debug(f"No manifest data available for MCP server", server_name=repo.name)
                    
                    servers.append(server)
                    
                except Exception as e:
                    logger.error(
                        f"Failed to process MCP server",
                        server_name=repo.name,
                        error=e
                    )
                    # Still add the basic server without enhanced metadata
                    servers.append(repo.to_mcp_server())
            
            if manifest_failures:
                logger.warning(
                    f"Failed to fetch manifest data for {len(manifest_failures)} MCP servers",
                    failed_servers=manifest_failures
                )
            
            logger.info(
                f"Successfully fetched MCP servers from Docker Hub",
                total_servers=len(servers),
                manifest_failures=len(manifest_failures)
            )
            
            return servers
            
        except Exception as e:
            logger.error("Failed to fetch MCP servers from Docker Hub", error=e)
            raise
    
    def get_repository_tags(self, namespace: str, repository: str) -> List[str]:
        url = f"{self.base_url}/v2/repositories/{namespace}/{repository}/tags/"
        
        try:
            response = self.client.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            data = response.json()
            return [tag["name"] for tag in data.get("results", [])]
        except httpx.HTTPError:
            return []
    
    def get_image_manifest(self, namespace: str, repository: str, tag: str = "latest") -> Optional[Dict[str, Any]]:
        """Extract Docker image manifest data including labels."""
        # First try to get the manifest v2 schema
        manifest_url = f"https://registry-1.docker.io/v2/{namespace}/{repository}/manifests/{tag}"
        
        try:
            # Get Docker registry token
            token = self._get_registry_token(namespace, repository)
            if not token:
                return None
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.docker.distribution.manifest.v2+json,application/vnd.docker.distribution.manifest.v1+json"
            }
            
            response = self.client.get(manifest_url, headers=headers)
            response.raise_for_status()
            
            manifest = response.json()
            
            # Extract config digest for v2 manifests
            if "config" in manifest:
                config_digest = manifest["config"]["digest"]
                return self._get_image_config(namespace, repository, config_digest, token)
            
            # For v1 manifests, try to extract from history
            elif "history" in manifest:
                return self._extract_labels_from_v1_manifest(manifest)
                
        except Exception as e:
            # Fallback: try to get basic info from Docker Hub API
            return self._get_dockerfile_info(namespace, repository)
        
        return None
    
    def _get_registry_token(self, namespace: str, repository: str) -> Optional[str]:
        """Get Docker registry authentication token."""
        auth_url = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{namespace}/{repository}:pull"
        
        try:
            response = self.client.get(auth_url)
            response.raise_for_status()
            return response.json().get("token")
        except Exception:
            return None
    
    def _get_image_config(self, namespace: str, repository: str, config_digest: str, token: str) -> Optional[Dict[str, Any]]:
        """Get image configuration containing labels."""
        config_url = f"https://registry-1.docker.io/v2/{namespace}/{repository}/blobs/{config_digest}"
        
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.docker.distribution.manifest.v2+json"
            }
            
            response = self.client.get(config_url, headers=headers)
            response.raise_for_status()
            
            config = response.json()
            return {
                "labels": config.get("config", {}).get("Labels") or {},
                "env": config.get("config", {}).get("Env") or [],
                "cmd": config.get("config", {}).get("Cmd") or [],
                "entrypoint": config.get("config", {}).get("Entrypoint") or []
            }
        except Exception:
            return None
    
    def _extract_labels_from_v1_manifest(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Extract labels from v1 manifest history."""
        labels = {}
        
        for history_item in manifest.get("history", []):
            v1_compat = history_item.get("v1Compatibility")
            if v1_compat:
                try:
                    compat_data = json.loads(v1_compat)
                    config_labels = compat_data.get("config", {}).get("Labels")
                    if config_labels:
                        labels.update(config_labels)
                except (json.JSONDecodeError, KeyError):
                    continue
        
        return {"labels": labels}
    
    def _get_dockerfile_info(self, namespace: str, repository: str) -> Optional[Dict[str, Any]]:
        """Fallback: get basic info from Docker Hub API."""
        url = f"{self.base_url}/v2/repositories/{namespace}/{repository}/dockerfile/"
        
        try:
            response = self.client.get(url, headers=self._get_headers())
            if response.status_code == 200:
                dockerfile_data = response.json()
                # Try to extract LABEL instructions from Dockerfile
                dockerfile_content = dockerfile_data.get("contents", "")
                labels = self._parse_dockerfile_labels(dockerfile_content)
                return {"labels": labels}
        except Exception:
            pass
        
        return None
    
    def _parse_dockerfile_labels(self, dockerfile_content: str) -> Dict[str, str]:
        """Parse LABEL instructions from Dockerfile content."""
        labels = {}
        
        for line in dockerfile_content.split('\n'):
            line = line.strip()
            if line.upper().startswith('LABEL '):
                # Simple label parsing - could be enhanced
                label_part = line[6:].strip()  # Remove 'LABEL '
                
                # Handle key=value format
                if '=' in label_part:
                    key, value = label_part.split('=', 1)
                    # Remove quotes
                    key = key.strip().strip('"\'')
                    value = value.strip().strip('"\'')
                    labels[key] = value
        
        return labels
    
    def _extract_mcp_metadata_from_labels(self, labels: Dict[str, str]) -> MCPServerMetadata:
        """Extract MCP metadata from Docker labels."""
        metadata = MCPServerMetadata()
        
        # Standard MCP labels
        if "mcp.version" in labels:
            metadata.protocol_version = labels["mcp.version"]
        
        if "mcp.transports" in labels:
            transports_str = labels["mcp.transports"]
            try:
                transport_list = transports_str.split(",")
                metadata.supported_transports = [
                    MCPTransport(t.strip()) for t in transport_list 
                    if t.strip() in ["stdio", "websocket", "http", "sse"]
                ]
            except ValueError:
                pass
        
        if "mcp.capabilities.tools" in labels:
            metadata.capabilities.tools = labels["mcp.capabilities.tools"].lower() == "true"
        
        if "mcp.capabilities.resources" in labels:
            metadata.capabilities.resources = labels["mcp.capabilities.resources"].lower() == "true"
        
        if "mcp.capabilities.prompts" in labels:
            metadata.capabilities.prompts = labels["mcp.capabilities.prompts"].lower() == "true"
        
        if "mcp.auth" in labels:
            auth_methods = labels["mcp.auth"].split(",")
            metadata.authentication_methods = [method.strip() for method in auth_methods]
        
        # Runtime requirements
        runtime_reqs = {}
        for key, value in labels.items():
            if key.startswith("mcp.runtime."):
                req_key = key[12:]  # Remove 'mcp.runtime.' prefix
                runtime_reqs[req_key] = value
        
        if runtime_reqs:
            metadata.runtime_requirements = runtime_reqs
        
        return metadata
    
    def close(self):
        """Close the HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
            logger.debug("Docker Hub client closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()