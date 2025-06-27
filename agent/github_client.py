import httpx
import json
import base64
import re
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from urllib.parse import quote
from .models import MCPServer, MCPServerMetadata, MCPTool, MCPResource, MCPPrompt, MCPTransport
from .logger import logger, log_api_call, RegistryError


class GitHubRepository:
    """Represents a GitHub repository with MCP server potential."""
    
    def __init__(self, data: Dict[str, Any]):
        self.name = data["name"]
        self.full_name = data["full_name"]
        self.description = data.get("description", "")
        self.html_url = data["html_url"]
        self.clone_url = data["clone_url"]
        self.ssh_url = data["ssh_url"]
        self.language = data.get("language")
        self.stargazers_count = data.get("stargazers_count", 0)
        self.forks_count = data.get("forks_count", 0)
        self.created_at = self._parse_datetime(data.get("created_at"))
        self.updated_at = self._parse_datetime(data.get("updated_at"))
        self.pushed_at = self._parse_datetime(data.get("pushed_at"))
        self.size = data.get("size", 0)
        self.default_branch = data.get("default_branch", "main")
        self.topics = data.get("topics", [])
        self.owner = data.get("owner", {})
        self.license = data.get("license", {})
        
        # MCP-specific attributes (populated during analysis)
        self.is_mcp_server = False
        self.mcp_confidence_score = 0.0
        self.mcp_indicators: List[str] = []
        self.package_info: Dict[str, Any] = {}
        self.dockerfile_info: Dict[str, Any] = {}
        
    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse GitHub datetime string."""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    
    def to_mcp_server(self) -> MCPServer:
        """Convert GitHub repository to MCP server model."""
        server_id = f"github/{self.full_name}"
        
        # Build categories from topics and language
        categories = list(self.topics)
        if self.language:
            categories.append(self.language.lower())
        
        # Calculate trust score based on GitHub metrics
        trust_score = min(1.0, (
            (self.stargazers_count * 0.1) + 
            (self.forks_count * 0.2) + 
            (50 if self.license else 0) +
            (self.mcp_confidence_score * 500)
        ) / 1000)
        
        return MCPServer(
            id=server_id,
            name=self.name,
            description=self.description,
            url=self.html_url,
            tags=self.topics,
            created_at=self.created_at,
            updated_at=self.updated_at,
            source="github",
            namespace=self.owner.get("login", ""),
            categories=categories,
            trust_score=trust_score,
            popularity_score=min(1.0, self.stargazers_count / 1000),
            docker_labels=self.dockerfile_info.get("labels", {}),
            docker_image=self.dockerfile_info.get("image_name")
        )


class GitHubMCPClient:
    """Client for discovering and analyzing MCP servers on GitHub."""
    
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token
        self.base_url = "https://api.github.com"
        
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "MCP-Scraper/1.0"
        }
        
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        self.client = httpx.Client(
            timeout=30.0,
            headers=headers
        )
        
        # MCP detection patterns
        self.mcp_indicators = {
            # Package.json indicators
            "package_json": [
                r'"@modelcontextprotocol/',
                r'"mcp-',
                r'"model-context-protocol"',
                r'"ModelContextProtocol"',
                r'"mcp":\s*{',
                r'"mcp-server"',
                r'"@anthropic-ai/sdk"'
            ],
            # Python indicators  
            "python": [
                r'from mcp import',
                r'import mcp',
                r'mcp-server',
                r'model-context-protocol',
                r'anthropic.*mcp',
                r'class.*MCPServer',
                r'@mcp\.tool',
                r'mcp\.Server'
            ],
            # Repository description/README indicators
            "description": [
                r'mcp.server',
                r'model.context.protocol',
                r'anthropic.*mcp',
                r'claude.*mcp',
                r'mcp.*tool',
                r'mcp.*resource',
                r'mcp.*prompt'
            ],
            # Dockerfile indicators
            "dockerfile": [
                r'FROM.*mcp',
                r'LABEL.*mcp',
                r'CMD.*mcp',
                r'ENTRYPOINT.*mcp'
            ]
        }
        
        logger.info("GitHub MCP client initialized", has_token=bool(self.github_token))
    
    @log_api_call("github", "/search/repositories")
    def search_mcp_repositories(
        self, 
        query: str = "", 
        per_page: int = 100, 
        max_pages: int = 10
    ) -> List[GitHubRepository]:
        """Search GitHub for repositories that might be MCP servers."""
        
        # Build comprehensive search queries for MCP servers
        search_queries = [
            "mcp server",
            "model context protocol", 
            "anthropic mcp",
            "claude mcp",
            '"@modelcontextprotocol"',
            "mcp-server language:typescript",
            "mcp-server language:python",
            "mcp-server language:javascript", 
            "anthropic-ai/mcp topic:mcp",
            "filename:mcp.json",
            "filename:mcp-server",
            '"from mcp import"',
            '"import mcp"'
        ]
        
        if query:
            search_queries = [f"{query} mcp"]
        
        all_repositories = []
        seen_repos: Set[str] = set()
        
        for search_query in search_queries:
            logger.info(f"Searching GitHub repositories", query=search_query)
            
            try:
                repos = self._search_repositories_paginated(
                    search_query, per_page, max_pages
                )
                
                # Deduplicate repositories
                for repo in repos:
                    if repo.full_name not in seen_repos:
                        all_repositories.append(repo)
                        seen_repos.add(repo.full_name)
                
                logger.info(
                    f"Found repositories for query",
                    query=search_query,
                    count=len(repos),
                    total_unique=len(all_repositories)
                )
                
            except Exception as e:
                logger.error(f"Failed to search repositories", query=search_query, error=e)
                continue
        
        logger.info(
            f"Completed GitHub repository search",
            total_repositories=len(all_repositories),
            search_queries=len(search_queries)
        )
        
        return all_repositories
    
    def _search_repositories_paginated(
        self, 
        query: str, 
        per_page: int, 
        max_pages: int
    ) -> List[GitHubRepository]:
        """Search repositories with pagination."""
        repositories = []
        page = 1
        
        while page <= max_pages:
            url = f"{self.base_url}/search/repositories"
            params = {
                "q": query,
                "sort": "stars",
                "order": "desc", 
                "per_page": min(per_page, 100),
                "page": page
            }
            
            try:
                response = self.client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                items = data.get("items", [])
                
                if not items:
                    break
                
                for item in items:
                    try:
                        repo = GitHubRepository(item)
                        repositories.append(repo)
                    except Exception as e:
                        logger.warning(
                            "Failed to parse repository data",
                            repo_name=item.get("full_name", "unknown"),
                            error=e
                        )
                
                # Check if we've reached the last page
                total_count = data.get("total_count", 0)
                if len(repositories) >= total_count or len(items) < per_page:
                    break
                
                page += 1
                
            except httpx.RequestError as e:
                raise RegistryError(f"GitHub API request failed: {str(e)}", "github")
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    logger.warning("GitHub API rate limit exceeded")
                    break
                raise RegistryError(
                    f"GitHub API error: {e.response.status_code}",
                    "github",
                    e.response.status_code
                )
        
        return repositories
    
    @log_api_call("github", "/repos/{owner}/{repo}/contents/{path}")
    def get_file_content(self, repo: GitHubRepository, file_path: str) -> Optional[str]:
        """Get the content of a file from a GitHub repository."""
        url = f"{self.base_url}/repos/{repo.full_name}/contents/{quote(file_path)}"
        
        try:
            response = self.client.get(url)
            
            if response.status_code == 404:
                return None
                
            response.raise_for_status()
            data = response.json()
            
            # Decode base64 content
            if data.get("encoding") == "base64":
                content = base64.b64decode(data["content"]).decode("utf-8")
                return content
            
        except Exception as e:
            logger.debug(
                f"Failed to get file content",
                repo=repo.full_name,
                file_path=file_path,
                error=e
            )
        
        return None
    
    def analyze_repository_for_mcp(self, repo: GitHubRepository) -> GitHubRepository:
        """Analyze a repository to determine if it's an MCP server."""
        logger.debug(f"Analyzing repository for MCP indicators", repo=repo.full_name)
        
        confidence_score = 0.0
        indicators = []
        
        # 1. Check repository name and description
        repo_text = f"{repo.name} {repo.description}".lower()
        for pattern in self.mcp_indicators["description"]:
            if re.search(pattern, repo_text, re.IGNORECASE):
                confidence_score += 0.3
                indicators.append(f"repo_description: {pattern}")
        
        # 2. Check topics
        mcp_topics = [t for t in repo.topics if "mcp" in t.lower()]
        if mcp_topics:
            confidence_score += 0.4
            indicators.append(f"topics: {mcp_topics}")
        
        # 3. Analyze package.json (for Node.js/TypeScript projects)
        if repo.language in ["JavaScript", "TypeScript"] or any(
            "js" in t or "ts" in t or "node" in t for t in repo.topics
        ):
            package_json = self.get_file_content(repo, "package.json")
            if package_json:
                repo.package_info = self._analyze_package_json(package_json)
                if repo.package_info.get("is_mcp"):
                    confidence_score += 0.6
                    indicators.extend(repo.package_info.get("indicators", []))
        
        # 4. Analyze Python files (for Python projects)
        if repo.language == "Python" or any("python" in t for t in repo.topics):
            python_indicators = self._analyze_python_files(repo)
            if python_indicators:
                confidence_score += 0.5
                indicators.extend(python_indicators)
        
        # 5. Check for Dockerfile
        dockerfile_content = self.get_file_content(repo, "Dockerfile")
        if dockerfile_content:
            repo.dockerfile_info = self._analyze_dockerfile(dockerfile_content)
            if repo.dockerfile_info.get("is_mcp"):
                confidence_score += 0.4
                indicators.extend(repo.dockerfile_info.get("indicators", []))
        
        # 6. Check README files
        readme_indicators = self._analyze_readme_files(repo)
        if readme_indicators:
            confidence_score += 0.3
            indicators.extend(readme_indicators)
        
        # Update repository with analysis results
        repo.mcp_confidence_score = min(1.0, confidence_score)
        repo.mcp_indicators = indicators
        repo.is_mcp_server = confidence_score >= 0.5  # Threshold for MCP detection
        
        logger.debug(
            f"Repository MCP analysis complete",
            repo=repo.full_name,
            is_mcp=repo.is_mcp_server,
            confidence=repo.mcp_confidence_score,
            indicators_count=len(indicators)
        )
        
        return repo
    
    def _analyze_package_json(self, content: str) -> Dict[str, Any]:
        """Analyze package.json for MCP indicators."""
        try:
            data = json.loads(content)
            indicators = []
            is_mcp = False
            
            # Check dependencies
            all_deps = {}
            all_deps.update(data.get("dependencies", {}))
            all_deps.update(data.get("devDependencies", {}))
            all_deps.update(data.get("peerDependencies", {}))
            
            for dep_name in all_deps:
                if any(pattern in dep_name.lower() for pattern in ["mcp", "model-context-protocol", "@anthropic-ai"]):
                    indicators.append(f"dependency: {dep_name}")
                    is_mcp = True
            
            # Check scripts
            scripts = data.get("scripts", {})
            for script_name, script_cmd in scripts.items():
                if any(pattern in script_cmd.lower() for pattern in ["mcp", "model-context-protocol"]):
                    indicators.append(f"script: {script_name}")
                    is_mcp = True
            
            # Check keywords
            keywords = data.get("keywords", [])
            for keyword in keywords:
                if "mcp" in keyword.lower():
                    indicators.append(f"keyword: {keyword}")
                    is_mcp = True
            
            # Check name and description
            name = data.get("name", "")
            description = data.get("description", "")
            if "mcp" in name.lower() or "mcp" in description.lower():
                indicators.append("package_name_or_description")
                is_mcp = True
            
            return {
                "is_mcp": is_mcp,
                "indicators": indicators,
                "data": data
            }
            
        except json.JSONDecodeError:
            return {"is_mcp": False, "indicators": [], "data": {}}
    
    def _analyze_python_files(self, repo: GitHubRepository) -> List[str]:
        """Analyze Python files for MCP indicators."""
        indicators = []
        
        # Check common Python files
        python_files = [
            "main.py", "app.py", "server.py", "mcp_server.py",
            "pyproject.toml", "setup.py", "requirements.txt"
        ]
        
        for file_path in python_files:
            content = self.get_file_content(repo, file_path)
            if content:
                for pattern in self.mcp_indicators["python"]:
                    if re.search(pattern, content, re.IGNORECASE):
                        indicators.append(f"{file_path}: {pattern}")
        
        return indicators
    
    def _analyze_dockerfile(self, content: str) -> Dict[str, Any]:
        """Analyze Dockerfile for MCP indicators."""
        indicators = []
        is_mcp = False
        labels = {}
        image_name = None
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            
            # Check for MCP patterns
            for pattern in self.mcp_indicators["dockerfile"]:
                if re.search(pattern, line, re.IGNORECASE):
                    indicators.append(f"dockerfile: {pattern}")
                    is_mcp = True
            
            # Extract labels
            if line.upper().startswith('LABEL '):
                label_part = line[6:].strip()
                if '=' in label_part:
                    key, value = label_part.split('=', 1)
                    labels[key.strip().strip('"')] = value.strip().strip('"')
            
            # Extract base image info
            if line.upper().startswith('FROM '):
                image_name = line[5:].strip()
        
        return {
            "is_mcp": is_mcp,
            "indicators": indicators,
            "labels": labels,
            "image_name": image_name
        }
    
    def _analyze_readme_files(self, repo: GitHubRepository) -> List[str]:
        """Analyze README files for MCP indicators."""
        indicators = []
        
        readme_files = ["README.md", "README.rst", "README.txt", "readme.md"]
        
        for readme_file in readme_files:
            content = self.get_file_content(repo, readme_file)
            if content:
                content_lower = content.lower()
                for pattern in self.mcp_indicators["description"]:
                    if re.search(pattern, content_lower):
                        indicators.append(f"readme: {pattern}")
                break  # Only check the first README found
        
        return indicators
    
    def get_mcp_servers(self, query: str = "", max_repositories: int = 1000) -> List[MCPServer]:
        """Get all MCP servers from GitHub with full analysis."""
        logger.info(f"Starting GitHub MCP server discovery", query=query, max_repos=max_repositories)
        
        # Search for potential MCP repositories
        repositories = self.search_mcp_repositories(query, max_pages=max_repositories // 100)
        
        # Analyze each repository for MCP indicators
        mcp_servers = []
        analyzed_count = 0
        
        for repo in repositories:
            try:
                analyzed_repo = self.analyze_repository_for_mcp(repo)
                
                if analyzed_repo.is_mcp_server:
                    mcp_server = analyzed_repo.to_mcp_server()
                    mcp_servers.append(mcp_server)
                
                analyzed_count += 1
                
                if analyzed_count % 50 == 0:
                    logger.info(
                        f"Repository analysis progress",
                        analyzed=analyzed_count,
                        total=len(repositories),
                        mcp_servers_found=len(mcp_servers)
                    )
                
            except Exception as e:
                logger.error(
                    f"Failed to analyze repository",
                    repo=repo.full_name,
                    error=e
                )
                continue
        
        logger.info(
            f"GitHub MCP server discovery complete",
            total_repositories_analyzed=analyzed_count,
            mcp_servers_found=len(mcp_servers)
        )
        
        return mcp_servers
    
    def close(self):
        """Close the HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
            logger.debug("GitHub client closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()