# Production MCP Server Registry Scraper

A comprehensive, production-ready tool for discovering and analyzing MCP (Model Context Protocol) servers from multiple sources including Docker Hub, GitHub repositories, and the MCP Community Registry.

## 🚀 Features

### Multi-Source Discovery
- **Docker Hub**: Official MCP namespace and community images
- **GitHub**: Repository-based MCP servers with intelligent detection
- **MCP Community Registry**: Official Anthropic registry
- **Database Storage**: Persistent caching with SQLite/PostgreSQL support

### Production-Ready Capabilities
- **Full MCP Introspection**: Automatic discovery of tools, resources, and prompts
- **Container Orchestration**: Safe, isolated server analysis
- **Comprehensive Logging**: Structured logging with error tracking
- **Database Persistence**: Historical data and fast search capabilities
- **Advanced Search**: Search by tools, programming language, GitHub topics, categories

### GitHub Integration
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

3. Configure environment (optional):
```bash
cp .env.example .env
# Edit .env with your credentials for higher rate limits:
# DOCKERHUB_USERNAME=your_username
# DOCKERHUB_PASSWORD=your_password  
# GITHUB_TOKEN=your_github_token
```

## 📖 Usage

### Basic Server Discovery

List all MCP servers from all sources:
```bash
python scripts/cli.py list-servers
```

Include full introspection (discovers tools, resources, prompts):
```bash
python scripts/cli.py list-servers --introspect
```

Search with GitHub integration:
```bash
python scripts/cli.py list-servers --include-github --github-query "typescript mcp"
```

### GitHub-Specific Commands

Discover MCP servers on GitHub:
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

GitHub statistics:
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
