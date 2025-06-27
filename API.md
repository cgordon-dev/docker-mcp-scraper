# API Documentation

This document provides comprehensive documentation for the MCP Server Registry Scraper API and CLI interface.

## CLI Commands

### Core Commands

#### `list-servers`
List all MCP servers from all configured sources.

```bash
python scripts/cli.py list-servers [OPTIONS]
```

**Options:**
- `--output [json|table]`: Output format (default: json)
- `--include-github`: Include GitHub repository servers
- `--introspect`: Perform full server introspection for tools/resources
- `--github-query TEXT`: Search query for GitHub servers

**Examples:**
```bash
# Basic server listing
python scripts/cli.py list-servers

# Include GitHub servers with tool extraction
python scripts/cli.py list-servers --include-github

# Full introspection with container analysis
python scripts/cli.py list-servers --introspect

# Table format output
python scripts/cli.py list-servers --output table
```

#### `search`
Search servers by name, description, tools, or categories.

```bash
python scripts/cli.py search QUERY [OPTIONS]
```

**Options:**
- `--search-type [name|tool|category]`: Type of search (default: name)
- `--output [json|table]`: Output format

**Examples:**
```bash
# Search by server name
python scripts/cli.py search "database"

# Search by tool name
python scripts/cli.py search "git" --search-type tool

# Search by category
python scripts/cli.py search "ai" --search-type category
```

#### `stats`
Display comprehensive statistics about discovered servers.

```bash
python scripts/cli.py stats
```

**Output includes:**
- Total servers by source
- Tool distribution
- Health status summary
- Category breakdown

### GitHub Commands

#### `github discover`
Discover MCP servers from the official GitHub repository.

```bash
python scripts/cli.py github discover [OPTIONS]
```

**Options:**
- `--output [json|table]`: Output format

#### `github by-language`
Find servers by programming language.

```bash
python scripts/cli.py github by-language LANGUAGE [OPTIONS]
```

**Supported Languages:**
- python
- typescript
- javascript
- go
- rust
- java

**Examples:**
```bash
python scripts/cli.py github by-language python
python scripts/cli.py github by-language typescript
```

#### `github by-topic`
Find servers by GitHub topic/tag.

```bash
python scripts/cli.py github by-topic TOPIC [OPTIONS]
```

**Examples:**
```bash
python scripts/cli.py github by-topic ai
python scripts/cli.py github by-topic automation
```

#### `github stats`
Display GitHub-specific statistics including tool extraction results.

```bash
python scripts/cli.py github stats
```

### Database Commands

#### `db stats`
Display database statistics and cache information.

```bash
python scripts/cli.py db stats
```

#### `db search`
Search cached server data in the database.

```bash
python scripts/cli.py db search [OPTIONS]
```

**Options:**
- `--has-tools`: Filter servers that have tools
- `--health-status [healthy|unhealthy|unknown]`: Filter by health status
- `--source TEXT`: Filter by data source

#### `db clear`
Clear all cached data from the database.

```bash
python scripts/cli.py db clear
```

### Utility Commands

#### `find-tool`
Find servers that provide a specific tool.

```bash
python scripts/cli.py find-tool TOOL_NAME [OPTIONS]
```

#### `health-check`
Perform health checks on all servers.

```bash
python scripts/cli.py health-check [OPTIONS]
```

**Options:**
- `--output FILE`: Save results to JSON file

## REST API Endpoints

The web server provides a comprehensive REST API for programmatic access.

### Base URL
```
http://localhost:8000/api
```

### Servers Endpoints

#### Get All Servers
```http
GET /api/servers
```

**Query Parameters:**
- `search` (optional): Search query
- `source` (optional): Filter by source (github_registry, docker_hub, mcp_registry)
- `has_tools` (optional): Filter servers with tools (true/false)
- `limit` (optional): Number of results (default: 100)
- `offset` (optional): Pagination offset

**Example:**
```bash
curl "http://localhost:8000/api/servers?search=database&limit=10"
```

#### Get Server by ID
```http
GET /api/servers/{server_id}
```

**Example:**
```bash
curl "http://localhost:8000/api/servers/filesystem"
```

#### Search Servers
```http
GET /api/servers/search
```

**Query Parameters:**
- `q`: Search query (required)
- `type`: Search type (name, tool, category)
- `limit`: Results limit

**Example:**
```bash
curl "http://localhost:8000/api/servers/search?q=git&type=tool"
```

### Statistics Endpoints

#### Get Overall Statistics
```http
GET /api/stats
```

**Response includes:**
- Total servers by source
- Tool distribution
- Health summary
- Category breakdown

#### Get GitHub Statistics
```http
GET /api/stats/github
```

**Response includes:**
- Language distribution
- Topic breakdown
- Trust score distribution
- Tool extraction results

### Tools Endpoints

#### Get All Tools
```http
GET /api/tools
```

**Response format:**
```json
{
  "tools": [
    {
      "name": "read_file",
      "description": "Read a file from the filesystem",
      "category": "file_operations",
      "server_name": "filesystem",
      "server_id": "filesystem"
    }
  ],
  "total": 36
}
```

#### Search Tools
```http
GET /api/tools/search
```

**Query Parameters:**
- `q`: Search query
- `category`: Filter by category
- `server`: Filter by server name

## Data Models

### MCPServer
```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "url": "string",
  "docker_image": "string",
  "source": "github_registry|docker_hub|mcp_registry",
  "tools": [
    {
      "name": "string",
      "description": "string", 
      "category": "string",
      "parameters": {}
    }
  ],
  "resources": [
    {
      "name": "string",
      "description": "string",
      "uri": "string"
    }
  ],
  "prompts": [
    {
      "name": "string",
      "description": "string"
    }
  ],
  "categories": ["string"],
  "tags": ["string"],
  "created_at": "datetime",
  "updated_at": "datetime",
  "last_introspected": "datetime",
  "health": {
    "status": "healthy|unhealthy|unknown",
    "last_check": "datetime",
    "error_message": "string"
  },
  "metadata": {
    "protocol_version": "string",
    "capabilities": {}
  },
  "trust_score": 0.85
}
```

### MCPTool
```json
{
  "name": "string",
  "description": "string",
  "category": "string",
  "parameters": {
    "type": "object",
    "properties": {},
    "required": []
  }
}
```

## Authentication

### GitHub Token
Required for accessing GitHub registry and performing source code analysis.

**Setup:**
1. Create a GitHub personal access token
2. Set the `GITHUB_TOKEN` environment variable
3. Or add to `.env` file: `GITHUB_TOKEN=your_token_here`

**Required Permissions:**
- `public_repo` (for accessing public repositories)
- `read:org` (for organization repositories)

### Docker Hub (Optional)
For higher rate limits when accessing Docker Hub API.

**Setup:**
```bash
export DOCKERHUB_USERNAME=your_username
export DOCKERHUB_PASSWORD=your_password
```

## Error Handling

### Common HTTP Status Codes
- `200 OK`: Successful request
- `400 Bad Request`: Invalid parameters
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### Error Response Format
```json
{
  "error": "Error description",
  "code": "error_code",
  "details": {}
}
```

## Rate Limiting

### GitHub API
- 5000 requests per hour for authenticated requests
- 60 requests per hour for unauthenticated requests

### Docker Hub API
- Higher limits with authentication
- Automatic retry with exponential backoff

## Examples

### Complete Server Discovery Flow
```bash
# 1. Discover all servers with tool extraction
python scripts/cli.py list-servers --include-github

# 2. Search for specific functionality
python scripts/cli.py search "database" --search-type tool

# 3. Get detailed statistics
python scripts/cli.py stats

# 4. Check GitHub-specific results
python scripts/cli.py github stats
```

### API Integration Example
```python
import requests

# Get all servers
response = requests.get("http://localhost:8000/api/servers")
servers = response.json()

# Search for database tools
response = requests.get(
    "http://localhost:8000/api/servers/search",
    params={"q": "database", "type": "tool"}
)
database_servers = response.json()

# Get statistics
response = requests.get("http://localhost:8000/api/stats")
stats = response.json()
```