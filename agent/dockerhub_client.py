import httpx
from typing import List, Optional, Dict, Any
from datetime import datetime
from .models import DockerHubRepository, DockerHubResponse, MCPServer


class DockerHubClient:
    def __init__(self, base_url: str = "https://hub.docker.com"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=30.0)
        self.token: Optional[str] = None
    
    def authenticate(self, username: str, password: str) -> bool:
        auth_url = f"{self.base_url}/v2/users/login/"
        auth_data = {"username": username, "password": password}
        
        try:
            response = self.client.post(auth_url, json=auth_data)
            response.raise_for_status()
            
            self.token = response.json().get("token")
            return self.token is not None
        except httpx.HTTPError:
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"JWT {self.token}"
        return headers
    
    def list_repositories(self, namespace: str, page_size: int = 100, page: int = 1) -> DockerHubResponse:
        url = f"{self.base_url}/v2/repositories/{namespace}/"
        params = {
            "page_size": min(page_size, 100),
            "page": page
        }
        
        response = self.client.get(url, params=params, headers=self._get_headers())
        response.raise_for_status()
        
        data = response.json()
        
        repositories = []
        for repo_data in data.get("results", []):
            last_updated = None
            if repo_data.get("last_updated"):
                try:
                    last_updated = datetime.fromisoformat(
                        repo_data["last_updated"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass
            
            repo = DockerHubRepository(
                name=repo_data["name"],
                namespace=repo_data["namespace"],
                description=repo_data.get("description", ""),
                star_count=repo_data.get("star_count", 0),
                pull_count=repo_data.get("pull_count", 0),
                last_updated=last_updated
            )
            repositories.append(repo)
        
        return DockerHubResponse(
            count=data.get("count", 0),
            next=data.get("next"),
            previous=data.get("previous"),
            results=repositories
        )
    
    def get_all_repositories(self, namespace: str) -> List[DockerHubRepository]:
        all_repositories = []
        page = 1
        
        while True:
            response = self.list_repositories(namespace, page=page)
            all_repositories.extend(response.results)
            
            if not response.next:
                break
            
            page += 1
        
        return all_repositories
    
    def get_mcp_servers(self) -> List[MCPServer]:
        repositories = self.get_all_repositories("mcp")
        return [repo.to_mcp_server() for repo in repositories]
    
    def get_repository_tags(self, namespace: str, repository: str) -> List[str]:
        url = f"{self.base_url}/v2/repositories/{namespace}/{repository}/tags/"
        
        try:
            response = self.client.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            data = response.json()
            return [tag["name"] for tag in data.get("results", [])]
        except httpx.HTTPError:
            return []
    
    def close(self):
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()