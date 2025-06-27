#!/usr/bin/env python3

import json
import os
import asyncio
from typing import Optional
from datetime import datetime
import click
from dotenv import load_dotenv

from agent.aggregator import MCPServerAggregator

load_dotenv()


@click.group()
def cli():
    """Docker MCP Server Registry Scraper CLI"""
    pass


@cli.command()
@click.option('--output', '-o', type=click.Path(), help='Output file path (JSON format)')
@click.option('--dockerhub-username', envvar='DOCKERHUB_USERNAME', help='Docker Hub username')
@click.option('--dockerhub-password', envvar='DOCKERHUB_PASSWORD', help='Docker Hub password')
@click.option('--github-token', envvar='GITHUB_TOKEN', help='GitHub personal access token for higher rate limits')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
@click.option('--introspect/--no-introspect', default=False, help='Perform full MCP introspection to discover tools, resources, and prompts')
@click.option('--max-concurrent', default=5, help='Maximum concurrent introspections')
@click.option('--include-github/--no-github', default=True, help='Include GitHub repository search')
@click.option('--github-query', default='', help='Specific GitHub search query')
def list_servers(output: Optional[str], dockerhub_username: Optional[str], 
                dockerhub_password: Optional[str], github_token: Optional[str], output_format: str, 
                introspect: bool, max_concurrent: int, include_github: bool, github_query: str):
    """Fetch and list all available Docker MCP servers"""
    
    async def _list_servers():
        with MCPServerAggregator(github_token=github_token) as aggregator:
            dockerhub_auth = None
            if dockerhub_username and dockerhub_password:
                dockerhub_auth = (dockerhub_username, dockerhub_password)
            
            if introspect:
                click.echo("Fetching MCP servers with full introspection (this may take a while)...")
                servers = await aggregator.fetch_all_servers_with_introspection(
                    dockerhub_auth, 
                    introspect=True,
                    max_concurrent_introspection=max_concurrent,
                    include_github=include_github,
                    github_query=github_query
                )
            else:
                click.echo("Fetching MCP servers from all registries...")
                servers = aggregator.fetch_all_servers(dockerhub_auth, include_github, github_query)
            
            if output_format == 'json':
                server_data = [server.model_dump() for server in servers]
                
                if output:
                    with open(output, 'w') as f:
                        json.dump(server_data, f, indent=2, default=str)
                    click.echo(f"Results saved to {output}")
                else:
                    click.echo(json.dumps(server_data, indent=2, default=str))
            
            else:  # table format
                if not servers:
                    click.echo("No servers found.")
                    return
                
                click.echo(f"\nFound {len(servers)} MCP servers:")
                click.echo("-" * 80)
                
                for server in servers:
                    click.echo(f"Name: {server.name}")
                    click.echo(f"Source: {server.source}")
                    if server.docker_image:
                        click.echo(f"Docker Image: {server.docker_image}")
                    if server.description:
                        click.echo(f"Description: {server.description}")
                    if server.url:
                        click.echo(f"URL: {server.url}")
                    
                    # Show introspection results if available
                    if introspect:
                        click.echo(f"Health: {server.health.status}")
                        if server.tools:
                            click.echo(f"Tools: {len(server.tools)} ({', '.join([t.name for t in server.tools[:3]])}{'...' if len(server.tools) > 3 else ''})")
                        if server.resources:
                            click.echo(f"Resources: {len(server.resources)}")
                        if server.prompts:
                            click.echo(f"Prompts: {len(server.prompts)}")
                        if server.metadata.protocol_version:
                            click.echo(f"MCP Version: {server.metadata.protocol_version}")
                    
                    click.echo("-" * 80)
    
    asyncio.run(_list_servers())


@cli.command()
@click.argument('query')
@click.option('--dockerhub-username', envvar='DOCKERHUB_USERNAME', help='Docker Hub username')
@click.option('--dockerhub-password', envvar='DOCKERHUB_PASSWORD', help='Docker Hub password')
@click.option('--search-type', type=click.Choice(['all', 'tool', 'category']), default='all', help='Search type')
@click.option('--introspect/--no-introspect', default=False, help='Include introspection data in search')
def search(query: str, dockerhub_username: Optional[str], dockerhub_password: Optional[str], search_type: str, introspect: bool):
    """Search for MCP servers by name, description, tools, or categories"""
    
    async def _search():
        with MCPServerAggregator(github_token=github_token) as aggregator:
            dockerhub_auth = None
            if dockerhub_username and dockerhub_password:
                dockerhub_auth = (dockerhub_username, dockerhub_password)
            
            click.echo(f"Searching for '{query}'...")
            
            if introspect:
                all_servers = await aggregator.fetch_all_servers_with_introspection(dockerhub_auth)
            else:
                all_servers = aggregator.fetch_all_servers(dockerhub_auth)
            
            if search_type == 'tool':
                results = aggregator.search_by_tool(all_servers, query)
            elif search_type == 'category':
                results = aggregator.search_by_category(all_servers, query)
            else:
                results = aggregator.search_servers(all_servers, query)
            
            if not results:
                click.echo("No servers found matching your query.")
                return
            
            click.echo(f"\nFound {len(results)} matching servers:")
            click.echo("-" * 80)
            
            for server in results:
                click.echo(f"Name: {server.name}")
                click.echo(f"Source: {server.source}")
                if server.docker_image:
                    click.echo(f"Docker Image: {server.docker_image}")
                if server.description:
                    click.echo(f"Description: {server.description}")
                
                # Show matching tools if searched by tool
                if search_type == 'tool' and server.tools:
                    matching_tools = [t.name for t in server.tools if query.lower() in t.name.lower()]
                    if matching_tools:
                        click.echo(f"Matching Tools: {', '.join(matching_tools)}")
                
                click.echo("-" * 80)
    
    asyncio.run(_search())


@cli.command()
@click.option('--dockerhub-username', envvar='DOCKERHUB_USERNAME', help='Docker Hub username')
@click.option('--dockerhub-password', envvar='DOCKERHUB_PASSWORD', help='Docker Hub password')
@click.option('--introspect/--no-introspect', default=False, help='Include introspection statistics')
def stats(dockerhub_username: Optional[str], dockerhub_password: Optional[str], introspect: bool):
    """Show comprehensive statistics about available MCP servers"""
    
    async def _stats():
        with MCPServerAggregator(github_token=github_token) as aggregator:
            dockerhub_auth = None
            if dockerhub_username and dockerhub_password:
                dockerhub_auth = (dockerhub_username, dockerhub_password)
            
            if introspect:
                click.echo("Fetching MCP servers with full introspection for comprehensive statistics...")
                servers = await aggregator.fetch_all_servers_with_introspection(dockerhub_auth)
            else:
                click.echo("Fetching MCP servers statistics...")
                servers = aggregator.fetch_all_servers(dockerhub_auth)
            
            by_source = aggregator.get_servers_by_source(servers)
            
            click.echo(f"\nTotal MCP Servers: {len(servers)}")
            click.echo("\nBy Source:")
            for source, source_servers in by_source.items():
                click.echo(f"  {source}: {len(source_servers)}")
            
            docker_images = [s for s in servers if s.docker_image]
            click.echo(f"\nServers with Docker Images: {len(docker_images)}")
            
            with_descriptions = [s for s in servers if s.description]
            click.echo(f"Servers with Descriptions: {len(with_descriptions)}")
            
            if introspect:
                # Enhanced statistics with introspection data
                health_summary = aggregator.get_server_health_summary(servers)
                click.echo("\nHealth Status:")
                for status, count in health_summary.items():
                    click.echo(f"  {status}: {count}")
                
                servers_with_tools = aggregator.get_servers_with_tools(servers)
                servers_with_resources = aggregator.get_servers_with_resources(servers)
                servers_with_prompts = aggregator.get_servers_with_prompts(servers)
                
                click.echo(f"\nServers with Tools: {len(servers_with_tools)}")
                click.echo(f"Servers with Resources: {len(servers_with_resources)}")
                click.echo(f"Servers with Prompts: {len(servers_with_prompts)}")
                
                # Tool statistics
                tool_stats = aggregator.get_tool_statistics(servers)
                total_tools = sum(len(s.tools) for s in servers)
                unique_tools = len(tool_stats)
                
                click.echo(f"\nTotal Tools: {total_tools}")
                click.echo(f"Unique Tool Names: {unique_tools}")
                
                if tool_stats:
                    click.echo("\nMost Common Tools:")
                    sorted_tools = sorted(tool_stats.items(), key=lambda x: x[1], reverse=True)[:10]
                    for tool_name, count in sorted_tools:
                        click.echo(f"  {tool_name}: {count} servers")
                
                # Protocol version statistics
                protocol_versions = {}
                for server in servers:
                    version = server.metadata.protocol_version or "unknown"
                    protocol_versions[version] = protocol_versions.get(version, 0) + 1
                
                if len(protocol_versions) > 1:
                    click.echo("\nMCP Protocol Versions:")
                    for version, count in sorted(protocol_versions.items()):
                        click.echo(f"  {version}: {count}")
    
    asyncio.run(_stats())


# New commands for production features

@cli.command()
@click.argument('tool_name')
@click.option('--dockerhub-username', envvar='DOCKERHUB_USERNAME', help='Docker Hub username')
@click.option('--dockerhub-password', envvar='DOCKERHUB_PASSWORD', help='Docker Hub password')
def find_tool(tool_name: str, dockerhub_username: Optional[str], dockerhub_password: Optional[str]):
    """Find MCP servers that provide a specific tool"""
    
    async def _find_tool():
        with MCPServerAggregator(github_token=github_token) as aggregator:
            dockerhub_auth = None
            if dockerhub_username and dockerhub_password:
                dockerhub_auth = (dockerhub_username, dockerhub_password)
            
            click.echo(f"Finding servers that provide tool '{tool_name}'...")
            servers = await aggregator.fetch_all_servers_with_introspection(dockerhub_auth)
            results = aggregator.search_by_tool(servers, tool_name)
            
            if not results:
                click.echo(f"No servers found that provide tool '{tool_name}'.")
                return
            
            click.echo(f"\nFound {len(results)} servers with tool '{tool_name}':")
            click.echo("-" * 80)
            
            for server in results:
                click.echo(f"Name: {server.name}")
                click.echo(f"Docker Image: {server.docker_image}")
                
                # Show matching tools with descriptions
                matching_tools = [t for t in server.tools if tool_name.lower() in t.name.lower()]
                for tool in matching_tools:
                    click.echo(f"  Tool: {tool.name}")
                    if tool.description:
                        click.echo(f"    Description: {tool.description}")
                    if tool.input_schema:
                        click.echo(f"    Input Schema: {json.dumps(tool.input_schema, indent=4)}")
                
                click.echo("-" * 80)
    
    asyncio.run(_find_tool())


@cli.command()
@click.option('--dockerhub-username', envvar='DOCKERHUB_USERNAME', help='Docker Hub username')
@click.option('--dockerhub-password', envvar='DOCKERHUB_PASSWORD', help='Docker Hub password')
@click.option('--output', '-o', type=click.Path(), help='Output file path for detailed report')
def health_check(dockerhub_username: Optional[str], dockerhub_password: Optional[str], output: Optional[str]):
    """Perform health checks on all MCP servers"""
    
    async def _health_check():
        with MCPServerAggregator(github_token=github_token) as aggregator:
            dockerhub_auth = None
            if dockerhub_username and dockerhub_password:
                dockerhub_auth = (dockerhub_username, dockerhub_password)
            
            click.echo("Performing health checks on all MCP servers...")
            servers = await aggregator.fetch_all_servers_with_introspection(dockerhub_auth)
            
            health_summary = aggregator.get_server_health_summary(servers)
            
            click.echo(f"\nHealth Check Results:")
            click.echo(f"Total Servers: {len(servers)}")
            for status, count in health_summary.items():
                click.echo(f"{status.title()}: {count}")
            
            # Show failed servers
            failed_servers = [s for s in servers if s.health.status in ['unhealthy', 'unreachable']]
            if failed_servers:
                click.echo(f"\nFailed Servers ({len(failed_servers)}):")
                click.echo("-" * 80)
                for server in failed_servers:
                    click.echo(f"Name: {server.name}")
                    click.echo(f"Status: {server.health.status}")
                    if server.health.error_message:
                        click.echo(f"Error: {server.health.error_message}")
                    if server.introspection_errors:
                        click.echo(f"Introspection Errors: {', '.join(server.introspection_errors)}")
                    click.echo("-" * 40)
            
            # Save detailed report if requested
            if output:
                health_report = {
                    "timestamp": click.DateTime().convert(click.get_current_context(), None, None),
                    "summary": health_summary,
                    "servers": [{
                        "name": s.name,
                        "status": s.health.status,
                        "error_message": s.health.error_message,
                        "introspection_errors": s.introspection_errors,
                        "tools_count": len(s.tools),
                        "resources_count": len(s.resources),
                        "prompts_count": len(s.prompts)
                    } for s in servers]
                }
                
                with open(output, 'w') as f:
                    json.dump(health_report, f, indent=2, default=str)
                click.echo(f"\nDetailed health report saved to {output}")
    
    asyncio.run(_health_check())


# Database management commands
@cli.group()
def db():
    """Database management commands"""
    pass


@db.command()
def init():
    """Initialize the database"""
    from agent.database import database
    click.echo("Database already initialized on import. Tables created if needed.")
    click.echo("Database ready.")


@db.command()
def stats():
    """Show database statistics"""
    from agent.database import database
    stats = database.get_statistics()
    
    click.echo("\nDatabase Statistics:")
    click.echo("-" * 40)
    click.echo(f"Total Servers: {stats.get('total_servers', 0)}")
    
    by_source = stats.get('by_source', {})
    if by_source:
        click.echo("\nBy Source:")
        for source, count in by_source.items():
            click.echo(f"  {source}: {count}")
    
    by_health = stats.get('by_health_status', {})
    if by_health:
        click.echo("\nBy Health Status:")
        for status, count in by_health.items():
            click.echo(f"  {status}: {count}")
    
    click.echo(f"\nCapabilities:")
    click.echo(f"  Servers with Tools: {stats.get('servers_with_tools', 0)}")
    click.echo(f"  Servers with Resources: {stats.get('servers_with_resources', 0)}")
    click.echo(f"  Servers with Prompts: {stats.get('servers_with_prompts', 0)}")


@db.command()
@click.option('--query', help='Search query')
@click.option('--source', help='Filter by source')
@click.option('--health-status', help='Filter by health status')
@click.option('--has-tools/--no-tools', default=None, help='Filter by tool availability')
@click.option('--has-resources/--no-resources', default=None, help='Filter by resource availability')
@click.option('--has-prompts/--no-prompts', default=None, help='Filter by prompt availability')
@click.option('--limit', type=int, help='Limit number of results')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table')
def search(query, source, health_status, has_tools, has_resources, has_prompts, limit, output_format):
    """Search servers in database"""
    from agent.database import database
    
    servers = database.search_servers(
        query=query,
        source=source,
        health_status=health_status,
        has_tools=has_tools,
        has_resources=has_resources,
        has_prompts=has_prompts,
        limit=limit
    )
    
    if not servers:
        click.echo("No servers found matching criteria.")
        return
    
    if output_format == 'json':
        server_data = [server.model_dump() for server in servers]
        click.echo(json.dumps(server_data, indent=2, default=str))
    else:
        click.echo(f"\nFound {len(servers)} servers:")
        click.echo("-" * 80)
        for server in servers:
            click.echo(f"Name: {server.name}")
            click.echo(f"Source: {server.source}")
            click.echo(f"Health: {server.health.status}")
            if server.tools:
                click.echo(f"Tools: {len(server.tools)}")
            if server.resources:
                click.echo(f"Resources: {len(server.resources)}")
            if server.prompts:
                click.echo(f"Prompts: {len(server.prompts)}")
            click.echo("-" * 80)


@db.command()
@click.confirmation_option(help='Are you sure you want to clear all servers?')
def clear():
    """Clear all servers from database"""
    from agent.database import database
    count = database.clear_all_servers()
    click.echo(f"Cleared {count} servers from database.")


@db.command()
@click.argument('server_id')
def delete(server_id: str):
    """Delete a specific server from database"""
    from agent.database import database
    if database.delete_server(server_id):
        click.echo(f"Deleted server: {server_id}")
    else:
        click.echo(f"Server not found: {server_id}")


# GitHub-specific commands
@cli.group()
def github():
    """GitHub MCP server commands"""
    pass


@github.command()
@click.option('--github-token', envvar='GITHUB_TOKEN', help='GitHub personal access token')
@click.option('--query', default='', help='GitHub search query')
@click.option('--max-repos', default=500, help='Maximum repositories to analyze')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table')
def discover(github_token: Optional[str], query: str, max_repos: int, output_format: str):
    """Discover MCP servers from GitHub repositories"""
    from agent.github_client import GitHubMCPClient
    
    with GitHubMCPClient(github_token) as client:
        click.echo(f"Discovering MCP servers on GitHub (analyzing up to {max_repos} repositories)...")
        servers = client.get_mcp_servers(query, max_repos)
        
        if not servers:
            click.echo("No MCP servers found on GitHub.")
            return
        
        if output_format == 'json':
            server_data = [server.model_dump() for server in servers]
            click.echo(json.dumps(server_data, indent=2, default=str))
        else:
            click.echo(f"\nFound {len(servers)} MCP servers on GitHub:")
            click.echo("-" * 80)
            
            for server in servers:
                click.echo(f"Name: {server.name}")
                click.echo(f"Repository: {server.url}")
                click.echo(f"Description: {server.description or 'No description'}")
                click.echo(f"Language: {', '.join(server.categories[:3]) if server.categories else 'Unknown'}")
                click.echo(f"Stars: {server.popularity_score * 1000:.0f}" if server.popularity_score else "Stars: N/A")
                click.echo(f"Trust Score: {server.trust_score:.2f}" if server.trust_score else "Trust Score: N/A")
                if server.tags:
                    click.echo(f"Topics: {', '.join(server.tags[:5])}")
                click.echo("-" * 80)


@github.command() 
@click.argument('language')
@click.option('--github-token', envvar='GITHUB_TOKEN', help='GitHub personal access token')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table')
def by_language(language: str, github_token: Optional[str], output_format: str):
    """Find GitHub MCP servers by programming language"""
    
    async def _by_language():
        with MCPServerAggregator(github_token=github_token) as aggregator:
            click.echo(f"Searching for {language} MCP servers on GitHub...")
            
            # Get all servers including GitHub
            servers = aggregator.fetch_all_servers(include_github=True, github_query=f"language:{language}")
            
            # Filter by language
            language_servers = aggregator.search_by_language(servers, language)
            
            if not language_servers:
                click.echo(f"No {language} MCP servers found.")
                return
            
            if output_format == 'json':
                server_data = [server.model_dump() for server in language_servers]
                click.echo(json.dumps(server_data, indent=2, default=str))
            else:
                click.echo(f"\nFound {len(language_servers)} {language} MCP servers:")
                click.echo("-" * 80)
                
                for server in language_servers:
                    click.echo(f"Name: {server.name}")
                    click.echo(f"Source: {server.source}")
                    if server.source == "github":
                        click.echo(f"Repository: {server.url}")
                    elif server.docker_image:
                        click.echo(f"Docker Image: {server.docker_image}")
                    click.echo(f"Description: {server.description or 'No description'}")
                    click.echo("-" * 80)
    
    asyncio.run(_by_language())


@github.command()
@click.argument('topic')
@click.option('--github-token', envvar='GITHUB_TOKEN', help='GitHub personal access token')
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table')
def by_topic(topic: str, github_token: Optional[str], output_format: str):
    """Find GitHub MCP servers by topic/tag"""
    
    async def _by_topic():
        with MCPServerAggregator(github_token=github_token) as aggregator:
            click.echo(f"Searching for MCP servers with topic '{topic}' on GitHub...")
            
            # Get all servers including GitHub
            servers = aggregator.fetch_all_servers(include_github=True, github_query=f"topic:{topic}")
            
            # Filter by topic
            topic_servers = aggregator.search_by_github_topics(servers, topic)
            
            if not topic_servers:
                click.echo(f"No MCP servers found with topic '{topic}'.")
                return
            
            if output_format == 'json':
                server_data = [server.model_dump() for server in topic_servers]
                click.echo(json.dumps(server_data, indent=2, default=str))
            else:
                click.echo(f"\nFound {len(topic_servers)} MCP servers with topic '{topic}':")
                click.echo("-" * 80)
                
                for server in topic_servers:
                    click.echo(f"Name: {server.name}")
                    click.echo(f"Repository: {server.url}")
                    click.echo(f"Description: {server.description or 'No description'}")
                    click.echo(f"Topics: {', '.join(server.tags)}")
                    click.echo("-" * 80)
    
    asyncio.run(_by_topic())


@github.command()
@click.option('--github-token', envvar='GITHUB_TOKEN', help='GitHub personal access token')
def stats(github_token: Optional[str]):
    """Show GitHub MCP server statistics"""
    
    async def _github_stats():
        with MCPServerAggregator(github_token=github_token) as aggregator:
            click.echo("Fetching GitHub MCP server statistics...")
            
            # Get all servers including GitHub
            servers = aggregator.fetch_all_servers(include_github=True)
            
            # Get GitHub statistics
            github_stats = aggregator.get_github_statistics(servers)
            
            if not github_stats:
                click.echo("No GitHub MCP servers found.")
                return
            
            click.echo(f"\nGitHub MCP Server Statistics:")
            click.echo("-" * 40)
            click.echo(f"Total GitHub Servers: {github_stats['total_github_servers']}")
            
            by_language = github_stats.get('by_language', {})
            if by_language:
                click.echo("\nBy Programming Language:")
                for language, count in by_language.items():
                    click.echo(f"  {language}: {count}")
            
            by_topic = github_stats.get('by_topic', {})
            if by_topic:
                click.echo("\nTop Topics:")
                for topic, count in list(by_topic.items())[:10]:
                    click.echo(f"  {topic}: {count}")
            
            trust_dist = github_stats.get('trust_distribution', {})
            if trust_dist:
                click.echo("\nTrust Score Distribution:")
                click.echo(f"  High Trust (>0.7): {trust_dist.get('high_trust', 0)}")
                click.echo(f"  Medium Trust (0.3-0.7): {trust_dist.get('medium_trust', 0)}")
                click.echo(f"  Low Trust (<0.3): {trust_dist.get('low_trust', 0)}")
    
    asyncio.run(_github_stats())


if __name__ == '__main__':
    cli()