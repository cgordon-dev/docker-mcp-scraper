import httpx
import json
import base64
import asyncio
from typing import List, Optional, Dict, Any

try:
    import toml
except ImportError:
    # Fallback TOML parser implementation
    def simple_toml_loads(content: str) -> Dict[str, Any]:
        """Simple TOML parser for basic pyproject.toml files."""
        result = {}
        current_section = result
        section_stack = [result]
        
        for line in content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Section headers
            if line.startswith('[') and line.endswith(']'):
                section_name = line[1:-1]
                if '.' in section_name:
                    # Nested section like [project.dependencies]
                    parts = section_name.split('.')
                    current_section = result
                    for part in parts:
                        if part not in current_section:
                            current_section[part] = {}
                        current_section = current_section[part]
                else:
                    if section_name not in result:
                        result[section_name] = {}
                    current_section = result[section_name]
                continue
            
            # Key-value pairs
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                # Handle arrays
                if value.startswith('[') and value.endswith(']'):
                    # Simple array parsing
                    array_content = value[1:-1].strip()
                    if array_content:
                        items = [item.strip().strip('"').strip("'") for item in array_content.split(',')]
                        value = [item for item in items if item]
                    else:
                        value = []
                
                current_section[key] = value
        
        return result
    
    # Create a mock toml module
    class MockToml:
        def loads(self, content: str) -> Dict[str, Any]:
            return simple_toml_loads(content)
    
    toml = MockToml()
from datetime import datetime
from urllib.parse import quote
from .models import MCPServer, MCPServerMetadata, MCPTool, MCPResource, MCPPrompt
from .source_analyzer import SourceCodeAnalyzer
from .logger import logger, log_api_call, RegistryError


class GitHubRegistryClient:
    """Client for fetching official MCP servers from GitHub repository and extracting tools."""
    
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token
        self.base_url = "https://api.github.com"
        self.repo_owner = "modelcontextprotocol"
        self.repo_name = "servers"
        
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
        
        self.source_analyzer = SourceCodeAnalyzer()
        
        logger.info(
            "GitHub registry client initialized",
            has_token=bool(self.github_token),
            repo=f"{self.repo_owner}/{self.repo_name}"
        )
    
    @log_api_call("github_registry", "/repos/{owner}/{repo}/contents/src")
    async def get_all_servers(self) -> List[MCPServer]:
        """Fetch all official MCP servers from GitHub repository."""
        logger.info("Starting to fetch all servers from GitHub MCP registry")
        
        try:
            # Get the src directory contents
            src_contents = await self._get_directory_contents("src")
            
            servers = []
            for item in src_contents:
                if item.get("type") == "dir":
                    server_name = item["name"]
                    logger.debug(f"Processing server directory", server_name=server_name)
                    
                    try:
                        server = await self._analyze_server_directory(server_name)
                        if server:
                            servers.append(server)
                            logger.info(
                                f"Successfully analyzed server",
                                server_name=server_name,
                                tools_count=len(server.tools),
                                resources_count=len(server.resources),
                                prompts_count=len(server.prompts)
                            )
                    except Exception as e:
                        logger.error(
                            f"Failed to analyze server directory",
                            server_name=server_name,
                            error=e
                        )
                        continue
            
            logger.info(
                f"Completed GitHub MCP registry fetch",
                total_servers=len(servers),
                total_tools=sum(len(s.tools) for s in servers)
            )
            
            return servers
            
        except Exception as e:
            logger.error("Failed to fetch servers from GitHub MCP registry", error=e)
            raise RegistryError(
                f"Failed to fetch from GitHub registry: {str(e)}",
                "github_registry"
            )
    
    async def _get_directory_contents(self, path: str) -> List[Dict[str, Any]]:
        """Get contents of a directory in the GitHub repository."""
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{quote(path)}"
        
        try:
            response = self.client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"Directory not found", path=path)
                return []
            raise RegistryError(
                f"GitHub API error: {e.response.status_code}",
                "github_registry",
                e.response.status_code
            )
        except httpx.RequestError as e:
            raise RegistryError(f"GitHub API request failed: {str(e)}", "github_registry")
    
    async def _get_file_content(self, path: str) -> Optional[str]:
        """Get the content of a file from the GitHub repository."""
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/contents/{quote(path)}"
        
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
                path=path,
                error=e
            )
        
        return None
    
    async def _analyze_server_directory(self, server_name: str) -> Optional[MCPServer]:
        """Analyze a server directory to extract complete server information."""
        base_path = f"src/{server_name}"
        
        # Get directory contents
        dir_contents = await self._get_directory_contents(base_path)
        if not dir_contents:
            return None
        
        # Initialize server metadata
        server_id = f"github/{self.repo_owner}/{self.repo_name}/{server_name}"
        server_url = f"https://github.com/{self.repo_owner}/{self.repo_name}/tree/main/src/{server_name}"
        
        # Extract basic metadata
        metadata = await self._extract_server_metadata(base_path, dir_contents)
        
        # Create base server object
        server = MCPServer(
            id=server_id,
            name=metadata.get("name", server_name),
            description=metadata.get("description", ""),
            url=server_url,
            created_at=metadata.get("created_at"),
            updated_at=metadata.get("updated_at"),
            source="github_registry",
            namespace=f"{self.repo_owner}/{self.repo_name}",
            categories=metadata.get("categories", []),
            docker_image=metadata.get("docker_image"),
            docker_labels=metadata.get("docker_labels", {}),
            metadata=MCPServerMetadata(
                protocol_version=metadata.get("protocol_version"),
                capabilities=metadata.get("capabilities", {})
            )
        )
        
        # Extract tools, resources, and prompts from source code
        await self._extract_server_capabilities(server, base_path, dir_contents)
        
        return server
    
    async def _extract_server_metadata(self, base_path: str, dir_contents: List[Dict]) -> Dict[str, Any]:
        """Extract metadata from package.json, pyproject.toml, and README files."""
        metadata = {}
        
        # Check for Python project (pyproject.toml)
        pyproject_content = await self._get_file_content(f"{base_path}/pyproject.toml")
        if pyproject_content:
            try:
                pyproject_data = toml.loads(pyproject_content)
                project = pyproject_data.get("project", {})
                
                metadata.update({
                    "name": project.get("name", ""),
                    "description": project.get("description", ""),
                    "version": project.get("version", ""),
                    "categories": ["python"],
                    "dependencies": list(project.get("dependencies", [])),
                    "protocol_version": self._extract_mcp_version(project.get("dependencies", []))
                })
                
                # Extract authors
                authors = project.get("authors", [])
                if authors:
                    metadata["author"] = authors[0].get("name", "")
                
            except Exception as e:
                logger.debug(f"Failed to parse pyproject.toml", path=base_path, error=e)
        
        # Check for TypeScript/JavaScript project (package.json)
        package_content = await self._get_file_content(f"{base_path}/package.json")
        if package_content:
            try:
                package_data = json.loads(package_content)
                
                metadata.update({
                    "name": package_data.get("name", ""),
                    "description": package_data.get("description", ""),
                    "version": package_data.get("version", ""),
                    "categories": ["typescript", "javascript"],
                    "dependencies": list(package_data.get("dependencies", {}).keys()),
                    "protocol_version": self._extract_mcp_version_from_deps(package_data.get("dependencies", {}))
                })
                
                if package_data.get("author"):
                    metadata["author"] = package_data["author"]
                
            except Exception as e:
                logger.debug(f"Failed to parse package.json", path=base_path, error=e)
        
        # Check for Dockerfile
        dockerfile_content = await self._get_file_content(f"{base_path}/Dockerfile")
        if dockerfile_content:
            docker_info = self._analyze_dockerfile(dockerfile_content)
            metadata.update(docker_info)
        
        # Extract enhanced description from README
        readme_content = await self._get_file_content(f"{base_path}/README.md")
        if readme_content:
            enhanced_desc = self._extract_readme_description(readme_content)
            if enhanced_desc and len(enhanced_desc) > len(metadata.get("description", "")):
                metadata["description"] = enhanced_desc
        
        return metadata
    
    def _extract_mcp_version(self, dependencies: List[str]) -> Optional[str]:
        """Extract MCP version from Python dependencies."""
        for dep in dependencies:
            if "mcp" in dep.lower():
                # Try to extract version from dependency specification
                if ">=" in dep:
                    return dep.split(">=")[1].strip()
                elif "==" in dep:
                    return dep.split("==")[1].strip()
        return None
    
    def _extract_mcp_version_from_deps(self, dependencies: Dict[str, str]) -> Optional[str]:
        """Extract MCP version from JavaScript/TypeScript dependencies."""
        for name, version in dependencies.items():
            if "mcp" in name.lower() or "modelcontextprotocol" in name.lower():
                return version.lstrip("^~")
        return None
    
    def _analyze_dockerfile(self, dockerfile_content: str) -> Dict[str, Any]:
        """Analyze Dockerfile content for Docker-related metadata."""
        info = {"docker_labels": {}}
        
        lines = dockerfile_content.split('\n')
        for line in lines:
            line = line.strip()
            
            # Extract labels
            if line.upper().startswith('LABEL '):
                label_part = line[6:].strip()
                if '=' in label_part:
                    key, value = label_part.split('=', 1)
                    info["docker_labels"][key.strip().strip('"')] = value.strip().strip('"')
            
            # Extract base image for Docker image name inference
            if line.upper().startswith('FROM '):
                base_image = line[5:].strip()
                # Generate docker image name based on server name
                server_name = base_image.split('/')[-1] if '/' in base_image else base_image
                info["docker_image"] = f"mcp/{server_name}"
        
        return info
    
    def _extract_readme_description(self, readme_content: str) -> str:
        """Extract enhanced description from README content."""
        lines = readme_content.split('\n')
        
        # Look for the first substantial paragraph after title
        description_lines = []
        found_title = False
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('#'):
                found_title = True
                continue
            
            if found_title and line and not line.startswith('##'):
                if not line.startswith('[') and not line.startswith('!'):  # Skip links and images
                    description_lines.append(line)
                    if len(' '.join(description_lines)) > 200:  # Reasonable description length
                        break
        
        description = ' '.join(description_lines).strip()
        
        # Clean up common README artifacts
        description = description.replace('**', '').replace('`', '')
        
        return description[:500]  # Limit to reasonable length
    
    async def _extract_server_capabilities(self, server: MCPServer, base_path: str, dir_contents: List[Dict]) -> None:
        """Extract tools, resources, and prompts from server source code."""
        tools = []
        resources = []
        prompts = []
        
        # Find source files to analyze
        source_files = await self._find_source_files(base_path, dir_contents)
        
        for file_path, file_type in source_files:
            try:
                content = await self._get_file_content(file_path)
                if not content:
                    continue
                
                logger.debug(f"Analyzing source file", file_path=file_path, file_type=file_type)
                
                if file_type == "python":
                    file_tools = await self.source_analyzer.extract_tools_from_python(content, file_path)
                    tools.extend(file_tools)
                elif file_type == "typescript":
                    file_tools = await self.source_analyzer.extract_tools_from_typescript(content, file_path)
                    tools.extend(file_tools)
                
            except Exception as e:
                logger.warning(f"Failed to analyze source file", file_path=file_path, error=e)
        
        # Deduplicate tools by name
        unique_tools = {}
        for tool in tools:
            if tool.name not in unique_tools:
                unique_tools[tool.name] = tool
            else:
                # Keep the tool with more complete information
                existing = unique_tools[tool.name]
                if (len(tool.description) > len(existing.description) or 
                    len(tool.input_schema) > len(existing.input_schema)):
                    unique_tools[tool.name] = tool
        
        server.tools = list(unique_tools.values())
        server.resources = resources  # TODO: Implement resource extraction
        server.prompts = prompts     # TODO: Implement prompt extraction
        
        logger.debug(
            f"Extracted capabilities from server",
            server_name=server.name,
            tools_count=len(server.tools),
            source_files_analyzed=len(source_files)
        )
    
    async def _find_source_files(self, base_path: str, dir_contents: List[Dict]) -> List[tuple[str, str]]:
        """Find source files to analyze for tool extraction."""
        source_files = []
        
        # Look for main source files in common locations
        common_paths = [
            # Python patterns
            f"{base_path}/src",
            f"{base_path}",
            # TypeScript patterns  
            f"{base_path}/src",
            f"{base_path}",
        ]
        
        for path in common_paths:
            try:
                contents = await self._get_directory_contents(path)
                for item in contents:
                    if item.get("type") == "file":
                        file_name = item["name"]
                        file_path = f"{path}/{file_name}"
                        
                        # Identify file type
                        if file_name.endswith(('.py',)):
                            source_files.append((file_path, "python"))
                        elif file_name.endswith(('.ts', '.js')):
                            source_files.append((file_path, "typescript"))
                    elif item.get("type") == "dir":
                        # Recursively check subdirectories
                        subdir_path = f"{path}/{item['name']}"
                        subdir_files = await self._find_source_files_recursive(subdir_path, depth=1)
                        source_files.extend(subdir_files)
            except Exception:
                continue
        
        return source_files
    
    async def _find_source_files_recursive(self, path: str, depth: int = 0, max_depth: int = 2) -> List[tuple[str, str]]:
        """Recursively find source files with depth limit."""
        if depth > max_depth:
            return []
        
        source_files = []
        
        try:
            contents = await self._get_directory_contents(path)
            for item in contents:
                if item.get("type") == "file":
                    file_name = item["name"]
                    file_path = f"{path}/{file_name}"
                    
                    if file_name.endswith(('.py',)):
                        source_files.append((file_path, "python"))
                    elif file_name.endswith(('.ts', '.js')):
                        source_files.append((file_path, "typescript"))
                elif item.get("type") == "dir" and depth < max_depth:
                    subdir_path = f"{path}/{item['name']}"
                    subdir_files = await self._find_source_files_recursive(subdir_path, depth + 1, max_depth)
                    source_files.extend(subdir_files)
        except Exception:
            pass
        
        return source_files
    
    def close(self):
        """Close the HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
            logger.debug("GitHub registry client closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()