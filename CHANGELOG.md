# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-06-24

### Added
- **Core Scraping Infrastructure**
  - Multi-registry support for MCP Community Registry and Docker Hub
  - Intelligent deduplication and data aggregation
  - Comprehensive data models with Pydantic validation
  
- **CLI Interface**
  - `list-servers` command with JSON and table output formats
  - `search` command for finding servers by name/description
  - `stats` command for registry statistics
  - Environment variable support for Docker Hub authentication
  
- **Web Dashboard**
  - FastAPI-based REST API with OpenAPI documentation
  - Interactive web interface for browsing servers
  - Real-time search and filtering capabilities
  - JSON API endpoints for programmatic access
  
- **Registry Clients**
  - Docker Hub API v2 integration with authentication support
  - MCP Community Registry client with pagination
  - Error handling and rate limiting considerations
  
- **Documentation**
  - Comprehensive README with installation and usage instructions
  - API documentation and examples
  - Troubleshooting guide for common issues
  - Configuration examples and environment setup

### Tested
- **Successful Scraping Results (June 24, 2025)**
  - 122 Docker MCP servers retrieved from Docker Hub
  - Categories: Databases, APIs, Development Tools, AI/ML Services
  - Popular servers: GitHub, PostgreSQL, Slack, Stripe, Kubernetes
  - Recent additions: Pulumi, CircleCI, Razorpay
  
- **All Components Verified**
  - CLI tools with multiple output formats
  - Web dashboard and REST API functionality
  - Data aggregation and deduplication logic
  - Error handling for registry connectivity issues

### Known Issues
- MCP Community Registry temporarily unavailable due to DNS resolution failure
- Requires `PYTHONPATH=.` for CLI execution (by design for development)

### Technical Details
- Python 3.9+ required
- Dependencies: FastAPI, httpx, Click, Pydantic
- Architecture: Modular design with separate registry clients
- Data formats: JSON output with comprehensive metadata
- Web server: Uvicorn ASGI server with async support