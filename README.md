# Docker MCP Server Registry Scraper

A comprehensive tool for discovering and aggregating Docker MCP (Model Context Protocol) servers from multiple registries.

## Features

- **Multi-Registry Support**: Fetches from MCP Community Registry and Docker Hub MCP namespace
- **Deduplication**: Intelligently merges duplicate servers from different sources
- **CLI Interface**: Command-line tools for listing, searching, and analyzing servers
- **Web Dashboard**: Simple web interface for browsing available servers
- **REST API**: JSON API for programmatic access to server data

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

3. Configure environment (optional):
```bash
cp .env.example .env
# Edit .env with your Docker Hub credentials for higher rate limits
```

## Usage

### CLI Commands

List all available MCP servers:
```bash
python scripts/cli.py list-servers
```

List servers in JSON format:
```bash
python scripts/cli.py list-servers --format json
```

Save results to file:
```bash
python scripts/cli.py list-servers --output servers.json
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

### MCP Community Registry
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
├── agent/                 # Core scraping logic
│   ├── models.py         # Data models
│   ├── registry_client.py # MCP Registry client
│   ├── dockerhub_client.py # Docker Hub client
│   └── aggregator.py     # Data aggregation logic
├── config/               # Configuration
│   └── settings.py       # Settings management
├── scripts/              # CLI tools
│   └── cli.py           # Click-based CLI
├── web/                  # Web interface
│   └── main.py          # FastAPI application
└── requirements.txt      # Python dependencies
```

## Recent Scraping Results

**Latest Run (June 24, 2025):**
- ✅ **122 Docker MCP servers** successfully scraped from Docker Hub
- 🗄️ Categories: Databases, APIs, Development Tools, AI/ML Services  
- 🔥 Popular servers: GitHub, PostgreSQL, Slack, Stripe, Kubernetes
- 📈 Recent additions: Pulumi, CircleCI, Razorpay
- ⚠️ MCP Community Registry temporarily unavailable (DNS issue)

### Sample Results
```bash
$ python scripts/cli.py stats
Total MCP Servers: 122
By Source:
  docker_hub: 122
Servers with Docker Images: 122
Servers with Descriptions: 120
```

### Example Server Data
```json
{
  "name": "github",
  "description": "Tools for interacting with the GitHub API...",
  "docker_image": "mcp/github",
  "source": "docker_hub"
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
