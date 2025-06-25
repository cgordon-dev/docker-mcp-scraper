from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

from agent.aggregator import MCPServerAggregator
from agent.models import MCPServer

app = FastAPI(title="Docker MCP Server Registry", version="1.0.0")

# Global aggregator instance (in production, consider using dependency injection)
aggregator = MCPServerAggregator()

@app.get("/")
async def root():
    return {"message": "Docker MCP Server Registry API", "docs": "/docs"}

@app.get("/api/servers", response_model=List[MCPServer])
async def get_servers(
    source: Optional[str] = Query(None, description="Filter by source (mcp_registry, docker_hub)"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    limit: Optional[int] = Query(100, ge=1, le=1000, description="Maximum number of results")
):
    """Get all MCP servers from all registries"""
    try:
        # Get Docker Hub credentials from environment
        dockerhub_username = os.getenv("DOCKERHUB_USERNAME")
        dockerhub_password = os.getenv("DOCKERHUB_PASSWORD")
        
        dockerhub_auth = None
        if dockerhub_username and dockerhub_password:
            dockerhub_auth = (dockerhub_username, dockerhub_password)
        
        servers = aggregator.fetch_all_servers(dockerhub_auth)
        
        # Apply source filter
        if source:
            servers = [s for s in servers if s.source == source]
        
        # Apply search filter
        if search:
            servers = aggregator.search_servers(servers, search)
        
        # Apply limit
        servers = servers[:limit]
        
        return servers
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching servers: {str(e)}")

@app.get("/api/servers/{server_id}", response_model=MCPServer)
async def get_server(server_id: str):
    """Get a specific MCP server by ID"""
    try:
        # Try MCP Registry first
        server = aggregator.registry_client.get_server(server_id)
        if server:
            return server
        
        raise HTTPException(status_code=404, detail="Server not found")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching server: {str(e)}")

@app.get("/api/stats")
async def get_stats():
    """Get statistics about available MCP servers"""
    try:
        dockerhub_username = os.getenv("DOCKERHUB_USERNAME")
        dockerhub_password = os.getenv("DOCKERHUB_PASSWORD")
        
        dockerhub_auth = None
        if dockerhub_username and dockerhub_password:
            dockerhub_auth = (dockerhub_username, dockerhub_password)
        
        servers = aggregator.fetch_all_servers(dockerhub_auth)
        by_source = aggregator.get_servers_by_source(servers)
        
        stats = {
            "total_servers": len(servers),
            "by_source": {source: len(source_servers) for source, source_servers in by_source.items()},
            "with_docker_image": len([s for s in servers if s.docker_image]),
            "with_description": len([s for s in servers if s.description]),
            "with_url": len([s for s in servers if s.url])
        }
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating stats: {str(e)}")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Simple HTML dashboard for browsing MCP servers"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Docker MCP Server Registry</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .server { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .server h3 { margin-top: 0; color: #333; }
            .source { background: #f8f9fa; padding: 2px 8px; border-radius: 3px; font-size: 0.8em; }
            .docker-image { color: #007bff; font-family: monospace; }
            .description { color: #666; margin: 10px 0; }
            .search { width: 300px; padding: 8px; margin: 10px 0; }
            .stats { background: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
            .loading { text-align: center; padding: 20px; }
        </style>
    </head>
    <body>
        <h1>Docker MCP Server Registry</h1>
        
        <div id="stats" class="stats">
            <div class="loading">Loading statistics...</div>
        </div>
        
        <input type="text" id="search" class="search" placeholder="Search servers by name or description...">
        
        <div id="servers">
            <div class="loading">Loading servers...</div>
        </div>

        <script>
        let allServers = [];
        
        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                document.getElementById('stats').innerHTML = `
                    <h3>Registry Statistics</h3>
                    <p><strong>Total Servers:</strong> ${stats.total_servers}</p>
                    <p><strong>By Source:</strong> ${Object.entries(stats.by_source).map(([k,v]) => `${k}: ${v}`).join(', ')}</p>
                    <p><strong>With Docker Images:</strong> ${stats.with_docker_image}</p>
                    <p><strong>With Descriptions:</strong> ${stats.with_description}</p>
                `;
            } catch (error) {
                document.getElementById('stats').innerHTML = '<p>Error loading statistics</p>';
            }
        }
        
        async function loadServers() {
            try {
                const response = await fetch('/api/servers');
                allServers = await response.json();
                displayServers(allServers);
            } catch (error) {
                document.getElementById('servers').innerHTML = '<p>Error loading servers</p>';
            }
        }
        
        function displayServers(servers) {
            const container = document.getElementById('servers');
            if (servers.length === 0) {
                container.innerHTML = '<p>No servers found</p>';
                return;
            }
            
            container.innerHTML = servers.map(server => `
                <div class="server">
                    <h3>${server.name} <span class="source">${server.source}</span></h3>
                    ${server.docker_image ? `<p class="docker-image">${server.docker_image}</p>` : ''}
                    ${server.description ? `<p class="description">${server.description}</p>` : ''}
                    ${server.url ? `<p><a href="${server.url}" target="_blank">More Info</a></p>` : ''}
                </div>
            `).join('');
        }
        
        function searchServers(query) {
            if (!query.trim()) {
                displayServers(allServers);
                return;
            }
            
            const filtered = allServers.filter(server => 
                server.name.toLowerCase().includes(query.toLowerCase()) ||
                (server.description && server.description.toLowerCase().includes(query.toLowerCase()))
            );
            displayServers(filtered);
        }
        
        document.getElementById('search').addEventListener('input', (e) => {
            searchServers(e.target.value);
        });
        
        // Load data on page load
        loadStats();
        loadServers();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    aggregator.close()