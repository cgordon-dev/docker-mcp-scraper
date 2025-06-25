#!/usr/bin/env python3

import json
import os
from typing import Optional
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
@click.option('--format', 'output_format', type=click.Choice(['json', 'table']), default='table', help='Output format')
def list_servers(output: Optional[str], dockerhub_username: Optional[str], 
                dockerhub_password: Optional[str], output_format: str):
    """Fetch and list all available Docker MCP servers"""
    
    with MCPServerAggregator() as aggregator:
        dockerhub_auth = None
        if dockerhub_username and dockerhub_password:
            dockerhub_auth = (dockerhub_username, dockerhub_password)
        
        click.echo("Fetching MCP servers from all registries...")
        servers = aggregator.fetch_all_servers(dockerhub_auth)
        
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
                click.echo("-" * 80)


@cli.command()
@click.argument('query')
@click.option('--dockerhub-username', envvar='DOCKERHUB_USERNAME', help='Docker Hub username')
@click.option('--dockerhub-password', envvar='DOCKERHUB_PASSWORD', help='Docker Hub password')
def search(query: str, dockerhub_username: Optional[str], dockerhub_password: Optional[str]):
    """Search for MCP servers by name or description"""
    
    with MCPServerAggregator() as aggregator:
        dockerhub_auth = None
        if dockerhub_username and dockerhub_password:
            dockerhub_auth = (dockerhub_username, dockerhub_password)
        
        click.echo(f"Searching for '{query}'...")
        all_servers = aggregator.fetch_all_servers(dockerhub_auth)
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
            click.echo("-" * 80)


@cli.command()
@click.option('--dockerhub-username', envvar='DOCKERHUB_USERNAME', help='Docker Hub username')
@click.option('--dockerhub-password', envvar='DOCKERHUB_PASSWORD', help='Docker Hub password')
def stats(dockerhub_username: Optional[str], dockerhub_password: Optional[str]):
    """Show statistics about available MCP servers"""
    
    with MCPServerAggregator() as aggregator:
        dockerhub_auth = None
        if dockerhub_username and dockerhub_password:
            dockerhub_auth = (dockerhub_username, dockerhub_password)
        
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


if __name__ == '__main__':
    cli()