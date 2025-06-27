import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Float, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

from .models import MCPServer, MCPTool, MCPResource, MCPPrompt, MCPServerHealth, MCPServerMetadata
from .logger import logger

Base = declarative_base()


class DBMCPServer(Base):
    """Database model for MCP servers."""
    __tablename__ = "mcp_servers"
    
    # Primary identification
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text)
    url = Column(String)
    docker_image = Column(String, index=True)
    
    # Repository metadata
    tags = Column(SQLiteJSON)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    source = Column(String, nullable=False, index=True)
    namespace = Column(String, index=True)
    
    # MCP-specific metadata
    metadata_json = Column(SQLiteJSON)
    
    # MCP protocol data (stored as JSON)
    tools_json = Column(SQLiteJSON)
    resources_json = Column(SQLiteJSON)
    prompts_json = Column(SQLiteJSON)
    
    # Runtime and health data
    health_status = Column(String, default="unknown", index=True)
    health_last_checked = Column(DateTime)
    health_response_time_ms = Column(Float)
    health_error_message = Column(Text)
    health_uptime_percentage = Column(Float)
    
    last_introspected = Column(DateTime)
    introspection_errors = Column(SQLiteJSON)
    
    # Docker-specific metadata
    docker_labels = Column(SQLiteJSON)
    docker_pull_count = Column(Integer)
    docker_star_count = Column(Integer)
    
    # Analytics and usage
    popularity_score = Column(Float)
    trust_score = Column(Float)
    categories = Column(SQLiteJSON)
    
    # Database timestamps
    db_created_at = Column(DateTime, default=datetime.utcnow)
    db_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_mcp_server(self) -> MCPServer:
        """Convert database model to Pydantic model."""
        
        # Parse tools
        tools = []
        if self.tools_json:
            for tool_data in self.tools_json:
                tools.append(MCPTool(**tool_data))
        
        # Parse resources
        resources = []
        if self.resources_json:
            for resource_data in self.resources_json:
                resources.append(MCPResource(**resource_data))
        
        # Parse prompts
        prompts = []
        if self.prompts_json:
            for prompt_data in self.prompts_json:
                prompts.append(MCPPrompt(**prompt_data))
        
        # Parse metadata
        metadata = MCPServerMetadata()
        if self.metadata_json:
            metadata = MCPServerMetadata(**self.metadata_json)
        
        # Parse health
        health = MCPServerHealth(
            status=self.health_status,
            last_checked=self.health_last_checked,
            response_time_ms=self.health_response_time_ms,
            error_message=self.health_error_message,
            uptime_percentage=self.health_uptime_percentage
        )
        
        return MCPServer(
            id=self.id,
            name=self.name,
            description=self.description,
            url=self.url,
            docker_image=self.docker_image,
            tags=self.tags or [],
            created_at=self.created_at,
            updated_at=self.updated_at,
            source=self.source,
            namespace=self.namespace,
            metadata=metadata,
            tools=tools,
            resources=resources,
            prompts=prompts,
            health=health,
            last_introspected=self.last_introspected,
            introspection_errors=self.introspection_errors or [],
            docker_labels=self.docker_labels or {},
            docker_pull_count=self.docker_pull_count,
            docker_star_count=self.docker_star_count,
            popularity_score=self.popularity_score,
            trust_score=self.trust_score,
            categories=self.categories or []
        )
    
    @classmethod
    def from_mcp_server(cls, server: MCPServer) -> "DBMCPServer":
        """Create database model from Pydantic model."""
        
        # Serialize tools
        tools_json = [tool.model_dump() for tool in server.tools] if server.tools else None
        
        # Serialize resources
        resources_json = [resource.model_dump() for resource in server.resources] if server.resources else None
        
        # Serialize prompts
        prompts_json = [prompt.model_dump() for prompt in server.prompts] if server.prompts else None
        
        # Serialize metadata
        metadata_json = server.metadata.model_dump() if server.metadata else None
        
        return cls(
            id=server.id,
            name=server.name,
            description=server.description,
            url=str(server.url) if server.url else None,
            docker_image=server.docker_image,
            tags=server.tags,
            created_at=server.created_at,
            updated_at=server.updated_at,
            source=server.source,
            namespace=server.namespace,
            metadata_json=metadata_json,
            tools_json=tools_json,
            resources_json=resources_json,
            prompts_json=prompts_json,
            health_status=server.health.status,
            health_last_checked=server.health.last_checked,
            health_response_time_ms=server.health.response_time_ms,
            health_error_message=server.health.error_message,
            health_uptime_percentage=server.health.uptime_percentage,
            last_introspected=server.last_introspected,
            introspection_errors=server.introspection_errors,
            docker_labels=server.docker_labels,
            docker_pull_count=server.docker_pull_count,
            docker_star_count=server.docker_star_count,
            popularity_score=server.popularity_score,
            trust_score=server.trust_score,
            categories=server.categories
        )


class MCPDatabase:
    """Database manager for MCP servers."""
    
    def __init__(self, database_url: str = "sqlite:///mcp_servers.db"):
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create tables
        Base.metadata.create_all(bind=self.engine)
        logger.info(f"Database initialized", database_url=database_url)
    
    def get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()
    
    def save_server(self, server: MCPServer) -> None:
        """Save or update a server in the database."""
        with self.get_session() as session:
            try:
                # Check if server exists
                existing = session.query(DBMCPServer).filter_by(id=server.id).first()
                
                if existing:
                    # Update existing server
                    db_server = DBMCPServer.from_mcp_server(server)
                    db_server.db_created_at = existing.db_created_at  # Preserve creation time
                    
                    # Update all fields
                    for field, value in db_server.__dict__.items():
                        if not field.startswith('_') and field != 'db_created_at':
                            setattr(existing, field, value)
                    
                    logger.debug(f"Updated server in database", server_id=server.id)
                else:
                    # Create new server
                    db_server = DBMCPServer.from_mcp_server(server)
                    session.add(db_server)
                    logger.debug(f"Added new server to database", server_id=server.id)
                
                session.commit()
                
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to save server to database", server_id=server.id, error=e)
                raise
    
    def save_servers(self, servers: List[MCPServer]) -> None:
        """Save multiple servers in batch."""
        logger.info(f"Saving {len(servers)} servers to database")
        
        success_count = 0
        error_count = 0
        
        for server in servers:
            try:
                self.save_server(server)
                success_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"Failed to save server", server_id=server.id, error=e)
        
        logger.info(
            f"Batch save completed",
            total_servers=len(servers),
            successful=success_count,
            errors=error_count
        )
    
    def get_server(self, server_id: str) -> Optional[MCPServer]:
        """Get a server by ID."""
        with self.get_session() as session:
            db_server = session.query(DBMCPServer).filter_by(id=server_id).first()
            return db_server.to_mcp_server() if db_server else None
    
    def get_all_servers(self) -> List[MCPServer]:
        """Get all servers from database."""
        with self.get_session() as session:
            db_servers = session.query(DBMCPServer).all()
            return [db_server.to_mcp_server() for db_server in db_servers]
    
    def search_servers(
        self, 
        query: Optional[str] = None,
        source: Optional[str] = None,
        health_status: Optional[str] = None,
        has_tools: Optional[bool] = None,
        has_resources: Optional[bool] = None,
        has_prompts: Optional[bool] = None,
        limit: Optional[int] = None
    ) -> List[MCPServer]:
        """Search servers with various filters."""
        
        with self.get_session() as session:
            query_obj = session.query(DBMCPServer)
            
            # Text search
            if query:
                query_obj = query_obj.filter(
                    (DBMCPServer.name.contains(query)) |
                    (DBMCPServer.description.contains(query))
                )
            
            # Source filter
            if source:
                query_obj = query_obj.filter(DBMCPServer.source == source)
            
            # Health status filter
            if health_status:
                query_obj = query_obj.filter(DBMCPServer.health_status == health_status)
            
            # Capability filters
            if has_tools is not None:
                if has_tools:
                    query_obj = query_obj.filter(DBMCPServer.tools_json.isnot(None))
                else:
                    query_obj = query_obj.filter(DBMCPServer.tools_json.is_(None))
            
            if has_resources is not None:
                if has_resources:
                    query_obj = query_obj.filter(DBMCPServer.resources_json.isnot(None))
                else:
                    query_obj = query_obj.filter(DBMCPServer.resources_json.is_(None))
            
            if has_prompts is not None:
                if has_prompts:
                    query_obj = query_obj.filter(DBMCPServer.prompts_json.isnot(None))
                else:
                    query_obj = query_obj.filter(DBMCPServer.prompts_json.is_(None))
            
            # Limit results
            if limit:
                query_obj = query_obj.limit(limit)
            
            db_servers = query_obj.all()
            return [db_server.to_mcp_server() for db_server in db_servers]
    
    def get_servers_by_health_status(self, status: str) -> List[MCPServer]:
        """Get servers by health status."""
        return self.search_servers(health_status=status)
    
    def get_servers_with_tools(self) -> List[MCPServer]:
        """Get servers that have tools."""
        return self.search_servers(has_tools=True)
    
    def get_servers_with_resources(self) -> List[MCPServer]:
        """Get servers that have resources."""
        return self.search_servers(has_resources=True)
    
    def get_servers_with_prompts(self) -> List[MCPServer]:
        """Get servers that have prompts."""
        return self.search_servers(has_prompts=True)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        with self.get_session() as session:
            total_servers = session.query(DBMCPServer).count()
            
            # Source statistics
            source_stats = session.query(
                DBMCPServer.source, 
                session.query(DBMCPServer.id).filter(DBMCPServer.source == DBMCPServer.source).count()
            ).group_by(DBMCPServer.source).all()
            
            # Health statistics
            health_stats = session.query(
                DBMCPServer.health_status,
                session.query(DBMCPServer.id).filter(DBMCPServer.health_status == DBMCPServer.health_status).count()
            ).group_by(DBMCPServer.health_status).all()
            
            # Capability statistics
            servers_with_tools = session.query(DBMCPServer).filter(DBMCPServer.tools_json.isnot(None)).count()
            servers_with_resources = session.query(DBMCPServer).filter(DBMCPServer.resources_json.isnot(None)).count()
            servers_with_prompts = session.query(DBMCPServer).filter(DBMCPServer.prompts_json.isnot(None)).count()
            
            return {
                "total_servers": total_servers,
                "by_source": dict(source_stats),
                "by_health_status": dict(health_stats),
                "servers_with_tools": servers_with_tools,
                "servers_with_resources": servers_with_resources,
                "servers_with_prompts": servers_with_prompts
            }
    
    def delete_server(self, server_id: str) -> bool:
        """Delete a server from database."""
        with self.get_session() as session:
            try:
                db_server = session.query(DBMCPServer).filter_by(id=server_id).first()
                if db_server:
                    session.delete(db_server)
                    session.commit()
                    logger.info(f"Deleted server from database", server_id=server_id)
                    return True
                return False
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to delete server from database", server_id=server_id, error=e)
                raise
    
    def clear_all_servers(self) -> int:
        """Clear all servers from database. Returns count of deleted servers."""
        with self.get_session() as session:
            try:
                count = session.query(DBMCPServer).count()
                session.query(DBMCPServer).delete()
                session.commit()
                logger.info(f"Cleared all servers from database", deleted_count=count)
                return count
            except Exception as e:
                session.rollback()
                logger.error("Failed to clear servers from database", error=e)
                raise
    
    def close(self):
        """Close database connection."""
        self.engine.dispose()
        logger.debug("Database connection closed")


# Global database instance
database = MCPDatabase()