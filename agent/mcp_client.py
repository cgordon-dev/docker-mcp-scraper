import asyncio
import json
import subprocess
import docker
import websockets
import httpx
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from contextlib import asynccontextmanager
from .models import MCPServer, MCPTool, MCPResource, MCPPrompt, MCPServerHealth, MCPTransport
from .logger import logger, log_execution_time, MCPProtocolError, DockerError


class MCPClient:
    """Client for communicating with MCP servers via various transports."""
    
    def __init__(self):
        self.docker_client = docker.from_env()
        self.http_client = httpx.AsyncClient(timeout=30.0)
    
    async def introspect_server(self, server: MCPServer) -> MCPServer:
        """Introspect an MCP server to discover its capabilities."""
        logger.info(f"Starting introspection of MCP server", server_name=server.name)
        
        # Update server health status
        server.health.status = "introspecting"
        server.health.last_checked = datetime.now()
        
        try:
            # Try different transport methods in order of preference
            transport_results = {}
            
            # 1. Try Docker stdio transport (most common)
            if server.docker_image:
                try:
                    tools, resources, prompts = await self._introspect_docker_stdio(server)
                    transport_results["docker_stdio"] = {
                        "tools": tools,
                        "resources": resources,
                        "prompts": prompts
                    }
                    logger.info(
                        f"Successfully introspected server via Docker stdio",
                        server_name=server.name,
                        tools_count=len(tools),
                        resources_count=len(resources),
                        prompts_count=len(prompts)
                    )
                except Exception as e:
                    logger.warning(
                        f"Docker stdio introspection failed for server",
                        server_name=server.name,
                        error=e
                    )
                    server.introspection_errors.append(f"Docker stdio: {str(e)}")
            
            # 2. Try HTTP transport if URL is available
            if server.url:
                try:
                    tools, resources, prompts = await self._introspect_http(server)
                    transport_results["http"] = {
                        "tools": tools,
                        "resources": resources,
                        "prompts": prompts
                    }
                    logger.info(
                        f"Successfully introspected server via HTTP",
                        server_name=server.name,
                        tools_count=len(tools),
                        resources_count=len(resources),
                        prompts_count=len(prompts)
                    )
                except Exception as e:
                    logger.warning(
                        f"HTTP introspection failed for server",
                        server_name=server.name,
                        error=e
                    )
                    server.introspection_errors.append(f"HTTP: {str(e)}")
            
            # 3. Try WebSocket transport
            if server.metadata.supported_transports and MCPTransport.WEBSOCKET in server.metadata.supported_transports:
                try:
                    tools, resources, prompts = await self._introspect_websocket(server)
                    transport_results["websocket"] = {
                        "tools": tools,
                        "resources": resources,
                        "prompts": prompts
                    }
                    logger.info(
                        f"Successfully introspected server via WebSocket",
                        server_name=server.name,
                        tools_count=len(tools),
                        resources_count=len(resources),
                        prompts_count=len(prompts)
                    )
                except Exception as e:
                    logger.warning(
                        f"WebSocket introspection failed for server",
                        server_name=server.name,
                        error=e
                    )
                    server.introspection_errors.append(f"WebSocket: {str(e)}")
            
            # Use the best available results
            if transport_results:
                # Prefer Docker stdio, then HTTP, then WebSocket
                best_result = None
                for transport in ["docker_stdio", "http", "websocket"]:
                    if transport in transport_results:
                        best_result = transport_results[transport]
                        break
                
                if best_result:
                    server.tools = best_result["tools"]
                    server.resources = best_result["resources"]
                    server.prompts = best_result["prompts"]
                    server.health.status = "healthy"
                    server.last_introspected = datetime.now()
                    
                    # Update capabilities based on discovered features
                    server.metadata.capabilities.tools = len(server.tools) > 0
                    server.metadata.capabilities.resources = len(server.resources) > 0
                    server.metadata.capabilities.prompts = len(server.prompts) > 0
                    
                    logger.info(
                        f"Successfully completed introspection of MCP server",
                        server_name=server.name,
                        total_tools=len(server.tools),
                        total_resources=len(server.resources),
                        total_prompts=len(server.prompts)
                    )
                else:
                    server.health.status = "unhealthy"
                    server.health.error_message = "No successful introspection methods"
            else:
                server.health.status = "unreachable"
                server.health.error_message = "All introspection methods failed"
                logger.error(
                    f"Failed to introspect MCP server via any transport method",
                    server_name=server.name,
                    errors=server.introspection_errors
                )
        
        except Exception as e:
            server.health.status = "unhealthy"
            server.health.error_message = str(e)
            logger.error(
                f"Unexpected error during MCP server introspection",
                server_name=server.name,
                error=e
            )
        
        return server
    
    @log_execution_time 
    async def _introspect_docker_stdio(self, server: MCPServer) -> tuple[List[MCPTool], List[MCPResource], List[MCPPrompt]]:
        """Introspect MCP server via Docker stdio transport."""
        if not server.docker_image:
            raise DockerError("No Docker image specified", "", "introspect")
        
        container = None
        try:
            logger.debug(f"Starting Docker container for introspection", image=server.docker_image)
            
            # Run container with MCP stdio protocol
            container = self.docker_client.containers.run(
                server.docker_image,
                detach=True,
                tty=True,
                stdin_open=True,
                remove=True,
                network_mode="none",  # Isolate from network for security
                mem_limit="512m",     # Limit memory usage
                cpu_period=100000,    # Limit CPU usage
                cpu_quota=50000,      # 50% CPU
                security_opt=["no-new-privileges:true"],  # Security hardening
                read_only=True,       # Read-only filesystem
                tmpfs={"/tmp": "rw,noexec,nosuid,size=100m"}  # Temporary filesystem
            )
            
            # Wait for container to be ready
            await asyncio.sleep(2)
            
            # Initialize MCP protocol
            init_message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {"listChanged": True},
                        "sampling": {}
                    },
                    "clientInfo": {
                        "name": "mcp-scraper",
                        "version": "1.0.0"
                    }
                }
            }
            
            # Send initialization message
            container.exec_run(
                f"echo '{json.dumps(init_message)}' | python -m mcp",
                stdin=True,
                tty=False
            )
            
            # Query capabilities
            tools = await self._query_tools_stdio(container)
            resources = await self._query_resources_stdio(container)
            prompts = await self._query_prompts_stdio(container)
            
            return tools, resources, prompts
            
        except docker.errors.DockerException as e:
            raise DockerError(f"Docker error: {str(e)}", server.docker_image, "introspect")
        except Exception as e:
            raise MCPProtocolError(f"MCP protocol error: {str(e)}", server.name)
        finally:
            if container:
                try:
                    container.stop(timeout=5)
                    container.remove()
                except Exception as e:
                    logger.warning(f"Failed to clean up container", error=e)
    
    async def _query_tools_stdio(self, container) -> List[MCPTool]:
        """Query tools via stdio MCP protocol."""
        tools_message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        
        try:
            exec_result = container.exec_run(
                f"echo '{json.dumps(tools_message)}' | python -m mcp",
                stdin=True
            )
            
            if exec_result.exit_code == 0:
                response = json.loads(exec_result.output.decode())
                tools = []
                
                for tool_data in response.get("result", {}).get("tools", []):
                    tool = MCPTool(
                        name=tool_data["name"],
                        description=tool_data.get("description", ""),
                        input_schema=tool_data.get("inputSchema", {}),
                        annotations=tool_data.get("annotations", {})
                    )
                    tools.append(tool)
                
                return tools
        except Exception as e:
            logger.debug(f"Failed to query tools via stdio", error=e)
        
        return []
    
    async def _query_resources_stdio(self, container) -> List[MCPResource]:
        """Query resources via stdio MCP protocol."""
        resources_message = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/list"
        }
        
        try:
            exec_result = container.exec_run(
                f"echo '{json.dumps(resources_message)}' | python -m mcp",
                stdin=True
            )
            
            if exec_result.exit_code == 0:
                response = json.loads(exec_result.output.decode())
                resources = []
                
                for resource_data in response.get("result", {}).get("resources", []):
                    resource = MCPResource(
                        uri=resource_data["uri"],
                        name=resource_data.get("name", ""),
                        description=resource_data.get("description", ""),
                        mime_type=resource_data.get("mimeType"),
                        annotations=resource_data.get("annotations", {})
                    )
                    resources.append(resource)
                
                return resources
        except Exception as e:
            logger.debug(f"Failed to query resources via stdio", error=e)
        
        return []
    
    async def _query_prompts_stdio(self, container) -> List[MCPPrompt]:
        """Query prompts via stdio MCP protocol."""
        prompts_message = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "prompts/list"
        }
        
        try:
            exec_result = container.exec_run(
                f"echo '{json.dumps(prompts_message)}' | python -m mcp",
                stdin=True
            )
            
            if exec_result.exit_code == 0:
                response = json.loads(exec_result.output.decode())
                prompts = []
                
                for prompt_data in response.get("result", {}).get("prompts", []):
                    prompt = MCPPrompt(
                        name=prompt_data["name"],
                        description=prompt_data.get("description", ""),
                        arguments=prompt_data.get("arguments", []),
                        annotations=prompt_data.get("annotations", {})
                    )
                    prompts.append(prompt)
                
                return prompts
        except Exception as e:
            logger.debug(f"Failed to query prompts via stdio", error=e)
        
        return []
    
    async def _introspect_http(self, server: MCPServer) -> tuple[List[MCPTool], List[MCPResource], List[MCPPrompt]]:
        """Introspect MCP server via HTTP transport."""
        if not server.url:
            raise MCPProtocolError("No URL specified for HTTP transport", server.name)
        
        base_url = str(server.url).rstrip("/")
        
        try:
            # Query tools
            tools_response = await self.http_client.post(
                f"{base_url}/mcp/tools/list",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
            )
            tools = self._parse_tools_response(tools_response.json())
            
            # Query resources
            resources_response = await self.http_client.post(
                f"{base_url}/mcp/resources/list",
                json={"jsonrpc": "2.0", "id": 2, "method": "resources/list"}
            )
            resources = self._parse_resources_response(resources_response.json())
            
            # Query prompts
            prompts_response = await self.http_client.post(
                f"{base_url}/mcp/prompts/list",
                json={"jsonrpc": "2.0", "id": 3, "method": "prompts/list"}
            )
            prompts = self._parse_prompts_response(prompts_response.json())
            
            return tools, resources, prompts
            
        except httpx.RequestError as e:
            raise MCPProtocolError(f"HTTP request failed: {str(e)}", server.name)
        except Exception as e:
            raise MCPProtocolError(f"HTTP introspection failed: {str(e)}", server.name)
    
    async def _introspect_websocket(self, server: MCPServer) -> tuple[List[MCPTool], List[MCPResource], List[MCPPrompt]]:
        """Introspect MCP server via WebSocket transport."""
        # This would require WebSocket URL construction logic
        # For now, returning empty results as WebSocket introspection
        # would need server-specific WebSocket endpoint information
        logger.debug(f"WebSocket introspection not yet implemented", server_name=server.name)
        return [], [], []
    
    def _parse_tools_response(self, response: Dict[str, Any]) -> List[MCPTool]:
        """Parse tools from MCP response."""
        tools = []
        for tool_data in response.get("result", {}).get("tools", []):
            tool = MCPTool(
                name=tool_data["name"],
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("inputSchema", {}),
                annotations=tool_data.get("annotations", {})
            )
            tools.append(tool)
        return tools
    
    def _parse_resources_response(self, response: Dict[str, Any]) -> List[MCPResource]:
        """Parse resources from MCP response."""
        resources = []
        for resource_data in response.get("result", {}).get("resources", []):
            resource = MCPResource(
                uri=resource_data["uri"],
                name=resource_data.get("name", ""),
                description=resource_data.get("description", ""),
                mime_type=resource_data.get("mimeType"),
                annotations=resource_data.get("annotations", {})
            )
            resources.append(resource)
        return resources
    
    def _parse_prompts_response(self, response: Dict[str, Any]) -> List[MCPPrompt]:
        """Parse prompts from MCP response."""
        prompts = []
        for prompt_data in response.get("result", {}).get("prompts", []):
            prompt = MCPPrompt(
                name=prompt_data["name"],
                description=prompt_data.get("description", ""),
                arguments=prompt_data.get("arguments", []),
                annotations=prompt_data.get("annotations", {})
            )
            prompts.append(prompt)
        return prompts
    
    async def batch_introspect(self, servers: List[MCPServer], max_concurrent: int = 5) -> List[MCPServer]:
        """Introspect multiple servers concurrently."""
        logger.info(f"Starting batch introspection of {len(servers)} MCP servers", max_concurrent=max_concurrent)
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def introspect_with_semaphore(server: MCPServer) -> MCPServer:
            async with semaphore:
                return await self.introspect_server(server)
        
        # Create tasks for all servers
        tasks = [introspect_with_semaphore(server) for server in servers]
        
        # Execute with progress tracking
        completed_servers = []
        for i, task in enumerate(asyncio.as_completed(tasks), 1):
            try:
                server = await task
                completed_servers.append(server)
                logger.info(
                    f"Completed introspection {i}/{len(servers)}",
                    server_name=server.name,
                    status=server.health.status
                )
            except Exception as e:
                logger.error(f"Failed to introspect server {i}/{len(servers)}", error=e)
        
        logger.info(
            f"Completed batch introspection",
            total_servers=len(servers),
            successful=len([s for s in completed_servers if s.health.status == "healthy"]),
            failed=len([s for s in completed_servers if s.health.status != "healthy"])
        )
        
        return completed_servers
    
    async def close(self):
        """Close the MCP client and clean up resources."""
        await self.http_client.aclose()
        self.docker_client.close()
        logger.debug("MCP client closed")


# Async context manager for MCP client
@asynccontextmanager
async def mcp_client():
    client = MCPClient()
    try:
        yield client
    finally:
        await client.close()