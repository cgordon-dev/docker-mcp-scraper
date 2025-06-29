# Production MCP Server Registry Scraper

A comprehensive, production-ready tool for discovering and analyzing MCP (Model Context Protocol) servers from multiple sources including GitHub repositories, Docker Hub, and the MCP Community Registry. Features advanced **source code analysis** for automatic tool extraction from Python and TypeScript MCP servers.

## 🚀 Features

### Multi-Source Discovery
- **GitHub Registry**: Official MCP servers from `modelcontextprotocol/servers` repository
- **Docker Hub**: Official MCP namespace and community images  
- **MCP Community Registry**: Official Anthropic registry (HTTP fallback)
- **Database Storage**: Persistent caching with SQLite/PostgreSQL support

### Advanced Tool Extraction
- **Python AST Analysis**: Extracts tools from Python source code using Abstract Syntax Tree parsing
- **TypeScript Code Analysis**: Discovers tools from TypeScript/JavaScript using pattern matching
- **Source Code Introspection**: Automatically analyzes server repositories for tool definitions
- **36+ Tools Discovered**: Successfully extracted from 7 official MCP servers

### Production-Ready Capabilities
- **Full MCP Introspection**: Automatic discovery of tools, resources, and prompts
- **Container Orchestration**: Safe, isolated server analysis
- **Comprehensive Logging**: Structured logging with error tracking
- **Database Persistence**: Historical data and fast search capabilities
- **Advanced Search**: Search by tools, programming language, GitHub topics, categories

### GitHub Integration
- **Official Server Repository**: Primary source from `modelcontextprotocol/servers`
- **Smart Detection**: Analyzes package.json, pyproject.toml, Dockerfiles, and README files
- **Language Support**: TypeScript, Python, JavaScript, Go, Rust, and more
- **Trust Scoring**: GitHub metrics-based reliability assessment
- **Topic Discovery**: GitHub topics and tags integration

## Installation

1. Clone the repository:
```bash
git clone https://github.com/cgordon-dev/docker-mcp-scraper.git
cd docker-mcp-scraper
```

2. Install dependencies (Python 3.9+ required):
```bash
pip install -r requirements.txt
```

3. Configure environment (recommended for GitHub access):
```bash
cp .env.example .env
# Edit .env with your credentials:
# GITHUB_TOKEN=your_github_token_here (required for GitHub registry)
# DOCKERHUB_USERNAME=your_username (optional, for higher rate limits)
# DOCKERHUB_PASSWORD=your_password (optional, for higher rate limits)
```

**Note**: GitHub token is required for accessing the official MCP server repository and performing tool extraction.

## 📖 Usage

### Basic Server Discovery

List all MCP servers (GitHub registry as primary source):
```bash
python scripts/cli.py list-servers
```

Include full introspection (discovers tools, resources, prompts):
```bash
python scripts/cli.py list-servers --introspect
```

Get servers with tool extraction from source code:
```bash
python scripts/cli.py list-servers --include-github
```

### GitHub Registry Commands

Discover official MCP servers from `modelcontextprotocol/servers`:
```bash
python scripts/cli.py github discover
```

Find servers by programming language:
```bash
python scripts/cli.py github by-language python
python scripts/cli.py github by-language typescript
```

Find servers by GitHub topic:
```bash
python scripts/cli.py github by-topic ai
python scripts/cli.py github by-topic automation
```

GitHub statistics and tool extraction results:
```bash
python scripts/cli.py github stats
```

### Advanced Search

Search by tool name:
```bash
python scripts/cli.py find-tool "github"
python scripts/cli.py search "database" --search-type tool
```

Search by category:
```bash
python scripts/cli.py search "ai" --search-type category
```

Health checking:
```bash
python scripts/cli.py health-check --output health-report.json
```

### Database Commands

Database statistics:
```bash
python scripts/cli.py db stats
```

Search cached servers:
```bash
python scripts/cli.py db search --has-tools --health-status healthy
```

Clear database:
```bash
python scripts/cli.py db clear
```

Search for specific servers:
```bash
python scripts/cli.py search "database"
```

View statistics:
```bash
python scripts/cli.py stats
```

### Web Dashboard

Start the web server:
```bash
uvicorn web.main:app --host 0.0.0.0 --port 8000
```

Then visit:
- Dashboard: http://localhost:8000/dashboard
- API Documentation: http://localhost:8000/docs
- API Root: http://localhost:8000/api/servers

### REST API

Get all servers:
```bash
curl http://localhost:8000/api/servers
```

Search servers:
```bash
curl "http://localhost:8000/api/servers?search=database&limit=10"
```

Filter by source:
```bash
curl "http://localhost:8000/api/servers?source=docker_hub"
```

Get statistics:
```bash
curl http://localhost:8000/api/stats
```

## Configuration

The tool can be configured via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub personal access token (required) | None |
| `DOCKERHUB_USERNAME` | Docker Hub username | None |
| `DOCKERHUB_PASSWORD` | Docker Hub password | None |
| `MCP_REGISTRY_URL` | MCP Registry base URL | https://registry.modelcontextprotocol.org |
| `DOCKERHUB_BASE_URL` | Docker Hub base URL | https://hub.docker.com |
| `DEFAULT_PAGE_SIZE` | Default API page size | 100 |
| `MAX_PAGE_SIZE` | Maximum API page size | 1000 |
| `WEB_HOST` | Web server host | 0.0.0.0 |
| `WEB_PORT` | Web server port | 8000 |
| `DEBUG` | Enable debug mode | false |

## Data Sources

### GitHub Registry (Primary)
- **Repository**: https://github.com/modelcontextprotocol/servers
- **API**: GitHub API v3 with content analysis
- **Authentication**: GitHub token required
- **Tool Extraction**: Python AST and TypeScript pattern matching

### MCP Community Registry (Fallback)
- **URL**: https://registry.modelcontextprotocol.org
- **API**: `/v0/servers` endpoint with pagination
- **Authentication**: None required

### Docker Hub MCP Namespace  
- **URL**: https://hub.docker.com/u/mcp
- **API**: Docker Hub API v2
- **Authentication**: Optional (for higher rate limits)

## Architecture

```
docker-mcp-scraper/
├── agent/                      # Core scraping logic
│   ├── models.py              # Data models (MCPServer, MCPTool, etc.)
│   ├── registry_client.py     # MCP Registry client (GitHub primary)
│   ├── github_registry_client.py # GitHub repository analysis
│   ├── source_analyzer.py     # Python AST & TypeScript tool extraction
│   ├── dockerhub_client.py    # Docker Hub client
│   ├── aggregator.py          # Multi-source data aggregation
│   ├── database.py            # SQLite/PostgreSQL persistence
│   └── logger.py              # Structured logging
├── config/                     # Configuration
│   └── settings.py            # Settings management
├── scripts/                    # CLI tools
│   └── cli.py                 # Click-based CLI with GitHub commands
├── web/                        # Web interface
│   └── main.py                # FastAPI application
└── requirements.txt            # Python dependencies
```

## Recent Scraping Results

**Latest Run (June 27, 2025):**
- ✅ **7 Official MCP servers** from `modelcontextprotocol/servers` repository
- 🛠️ **36+ Tools extracted** from source code analysis
- 🐍 **Python servers**: filesystem, git, postgres, sqlite, brave-search
- 📝 **TypeScript servers**: everything, fetch
- 🔍 **Tool categories**: File operations, Git, Database, Web search, HTTP requests
- 📈 **Source code analysis**: 100% success rate for tool extraction

### Sample Results
```bash
$ python scripts/cli.py stats
Total MCP Servers: 7
By Source:
  github_registry: 7
Servers with Tools: 7
Total Tools Discovered: 36+
```

### Example Server with Tools
```json
{
  "name": "filesystem",
  "description": "MCP Server for filesystem operations",
  "source": "github_registry",
  "tools": [
    {
      "name": "read_file",
      "description": "Read a file from the filesystem",
      "category": "file_operations"
    },
    {
      "name": "write_file", 
      "description": "Write content to a file",
      "category": "file_operations"
    }
  ]
}
```

## Troubleshooting

### Common Issues

**DNS Resolution Error (MCP Registry)**
```
Error fetching from MCP Registry: [Errno 8] nodename nor servname provided, or not known
```
*Solution: This is a temporary issue with the MCP Community Registry. The scraper will continue with Docker Hub data.*

**Module Import Error**
```
ModuleNotFoundError: No module named 'agent'
```
*Solution: Run with PYTHONPATH: `PYTHONPATH=. python scripts/cli.py`*

**Permission Denied (pip install)**
```
ERROR: Could not install packages due to an EnvironmentError
```
*Solution: Use `pip install --user -r requirements.txt` or create a virtual environment*

## License

MIT License
