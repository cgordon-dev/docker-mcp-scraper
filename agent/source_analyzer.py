import ast
import json
import re
from typing import List, Dict, Any, Optional, Set
from .models import MCPTool, MCPResource, MCPPrompt
from .logger import logger


class SourceCodeAnalyzer:
    """Analyzes MCP server source code to extract tool, resource, and prompt definitions."""
    
    def __init__(self):
        self.logger = logger
    
    async def extract_tools_from_python(self, source_code: str, file_path: str = "") -> List[MCPTool]:
        """Extract MCP tools from Python source code using AST parsing."""
        tools = []
        
        try:
            tree = ast.parse(source_code)
            
            # Find tool definitions in various patterns
            tools.extend(self._find_tool_list_handlers(tree))
            tools.extend(self._find_tool_constructors(tree))
            tools.extend(self._find_server_decorators(tree))
            
            logger.debug(
                f"Extracted tools from Python source",
                file_path=file_path,
                tools_count=len(tools)
            )
            
        except SyntaxError as e:
            logger.warning(
                f"Failed to parse Python source code",
                file_path=file_path,
                error=str(e)
            )
        except Exception as e:
            logger.error(
                f"Unexpected error analyzing Python source",
                file_path=file_path,
                error=e
            )
        
        return tools
    
    def _find_tool_list_handlers(self, tree: ast.AST) -> List[MCPTool]:
        """Find tools defined in list_tools handlers."""
        tools = []
        
        for node in ast.walk(tree):
            # Look for @server.list_tools() decorated functions
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if self._is_list_tools_decorator(decorator):
                        tools.extend(self._extract_tools_from_function(node))
        
        return tools
    
    def _find_tool_constructors(self, tree: ast.AST) -> List[MCPTool]:
        """Find Tool() constructor calls."""
        tools = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Look for Tool() constructor calls
                if isinstance(node.func, ast.Name) and node.func.id == "Tool":
                    tool = self._extract_tool_from_constructor(node)
                    if tool:
                        tools.append(tool)
                # Look for list of Tool() objects
                elif isinstance(node.func, ast.Attribute) and node.func.attr == "append":
                    if len(node.args) > 0 and isinstance(node.args[0], ast.Call):
                        call = node.args[0]
                        if isinstance(call.func, ast.Name) and call.func.id == "Tool":
                            tool = self._extract_tool_from_constructor(call)
                            if tool:
                                tools.append(tool)
        
        return tools
    
    def _find_server_decorators(self, tree: ast.AST) -> List[MCPTool]:
        """Find tools defined through server decorators."""
        tools = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if self._is_call_tool_decorator(decorator):
                        # Extract tool information from the decorated function
                        tool = self._extract_tool_from_decorated_function(node, decorator)
                        if tool:
                            tools.append(tool)
        
        return tools
    
    def _is_list_tools_decorator(self, decorator: ast.AST) -> bool:
        """Check if decorator is @server.list_tools()."""
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                return (decorator.func.attr == "list_tools" and 
                       isinstance(decorator.func.value, ast.Name) and 
                       decorator.func.value.id == "server")
        return False
    
    def _is_call_tool_decorator(self, decorator: ast.AST) -> bool:
        """Check if decorator is @server.call_tool()."""
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                return (decorator.func.attr == "call_tool" and 
                       isinstance(decorator.func.value, ast.Name) and 
                       decorator.func.value.id == "server")
        return False
    
    def _extract_tools_from_function(self, func_node: ast.FunctionDef) -> List[MCPTool]:
        """Extract tools from a list_tools handler function."""
        tools = []
        
        for node in ast.walk(func_node):
            # Look for return statements with Tool objects
            if isinstance(node, ast.Return) and node.value:
                if isinstance(node.value, ast.List):
                    # Return [Tool(...), Tool(...)]
                    for item in node.value.elts:
                        if isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and item.func.id == "Tool":
                            tool = self._extract_tool_from_constructor(item)
                            if tool:
                                tools.append(tool)
                elif isinstance(node.value, ast.Call):
                    # Return Tool(...)
                    if isinstance(node.value.func, ast.Name) and node.value.func.id == "Tool":
                        tool = self._extract_tool_from_constructor(node.value)
                        if tool:
                            tools.append(tool)
        
        return tools
    
    def _extract_tool_from_constructor(self, call_node: ast.Call) -> Optional[MCPTool]:
        """Extract MCPTool from Tool() constructor call."""
        try:
            # Extract keyword arguments
            kwargs = {}
            for keyword in call_node.keywords:
                if keyword.arg:
                    kwargs[keyword.arg] = self._extract_value(keyword.value)
            
            # Extract positional arguments (if any)
            args = [self._extract_value(arg) for arg in call_node.args]
            
            # Map to MCPTool fields
            name = kwargs.get("name") or (args[0] if len(args) > 0 else None)
            description = kwargs.get("description", "")
            input_schema = kwargs.get("inputSchema", {})
            
            if name:
                return MCPTool(
                    name=str(name),
                    description=str(description),
                    input_schema=input_schema if isinstance(input_schema, dict) else {},
                    annotations=kwargs.get("annotations", {}),
                    is_destructive=kwargs.get("is_destructive", False),
                    requires_auth=kwargs.get("requires_auth", False),
                    category=kwargs.get("category")
                )
        
        except Exception as e:
            logger.debug(f"Failed to extract tool from constructor", error=e)
        
        return None
    
    def _extract_tool_from_decorated_function(self, func_node: ast.FunctionDef, decorator: ast.AST) -> Optional[MCPTool]:
        """Extract tool information from @server.call_tool decorated function."""
        try:
            # Tool name is typically the function name or specified in decorator
            tool_name = func_node.name
            
            # Extract description from docstring
            description = ""
            if (func_node.body and isinstance(func_node.body[0], ast.Expr) and 
                isinstance(func_node.body[0].value, ast.Str)):
                description = func_node.body[0].value.s
            elif (func_node.body and isinstance(func_node.body[0], ast.Expr) and 
                  isinstance(func_node.body[0].value, ast.Constant)):
                description = str(func_node.body[0].value.value)
            
            # Extract input schema from function signature and type hints
            input_schema = self._extract_schema_from_function_signature(func_node)
            
            return MCPTool(
                name=tool_name,
                description=description,
                input_schema=input_schema,
                annotations={},
                is_destructive=False,
                requires_auth=False
            )
        
        except Exception as e:
            logger.debug(f"Failed to extract tool from decorated function", error=e)
        
        return None
    
    def _extract_schema_from_function_signature(self, func_node: ast.FunctionDef) -> Dict[str, Any]:
        """Extract JSON schema from function signature and type hints."""
        schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        try:
            for arg in func_node.args.args:
                if arg.arg in ["self", "request", "server"]:  # Skip common parameters
                    continue
                
                prop_name = arg.arg
                prop_schema = {"type": "string"}  # Default type
                
                # Try to extract type from annotation
                if arg.annotation:
                    prop_schema = self._extract_type_from_annotation(arg.annotation)
                
                schema["properties"][prop_name] = prop_schema
                
                # Check if argument has default value
                defaults_offset = len(func_node.args.args) - len(func_node.args.defaults)
                arg_index = func_node.args.args.index(arg)
                
                if arg_index < defaults_offset:
                    schema["required"].append(prop_name)
        
        except Exception as e:
            logger.debug(f"Failed to extract schema from function signature", error=e)
        
        return schema
    
    def _extract_type_from_annotation(self, annotation: ast.AST) -> Dict[str, Any]:
        """Extract JSON schema type from Python type annotation."""
        try:
            if isinstance(annotation, ast.Name):
                type_name = annotation.id.lower()
                if type_name in ["str", "string"]:
                    return {"type": "string"}
                elif type_name in ["int", "integer"]:
                    return {"type": "integer"}
                elif type_name in ["float", "number"]:
                    return {"type": "number"}
                elif type_name in ["bool", "boolean"]:
                    return {"type": "boolean"}
                elif type_name in ["list", "array"]:
                    return {"type": "array"}
                elif type_name in ["dict", "object"]:
                    return {"type": "object"}
            
            elif isinstance(annotation, ast.Subscript):
                # Handle Optional[Type], List[Type], etc.
                if isinstance(annotation.value, ast.Name):
                    if annotation.value.id == "Optional":
                        base_type = self._extract_type_from_annotation(annotation.slice)
                        base_type["optional"] = True
                        return base_type
                    elif annotation.value.id in ["List", "list"]:
                        item_type = self._extract_type_from_annotation(annotation.slice)
                        return {"type": "array", "items": item_type}
        
        except Exception:
            pass
        
        return {"type": "string"}  # Default fallback
    
    def _extract_value(self, node: ast.AST) -> Any:
        """Extract Python value from AST node."""
        try:
            if isinstance(node, ast.Str):
                return node.s
            elif isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.Num):
                return node.n
            elif isinstance(node, ast.NameConstant):
                return node.value
            elif isinstance(node, ast.List):
                return [self._extract_value(item) for item in node.elts]
            elif isinstance(node, ast.Dict):
                result = {}
                for key, value in zip(node.keys, node.values):
                    key_val = self._extract_value(key)
                    value_val = self._extract_value(value)
                    if key_val is not None:
                        result[key_val] = value_val
                return result
            elif isinstance(node, ast.Call):
                # Handle method calls like schema.model_json_schema()
                if (isinstance(node.func, ast.Attribute) and 
                    node.func.attr == "model_json_schema"):
                    # This is a Pydantic model schema - return placeholder
                    return {"type": "object", "description": "Pydantic model schema"}
            elif isinstance(node, ast.Name):
                # Handle variable references
                return f"${node.id}"  # Placeholder for variable
        
        except Exception:
            pass
        
        return None
    
    async def extract_tools_from_typescript(self, source_code: str, file_path: str = "") -> List[MCPTool]:
        """Extract MCP tools from TypeScript source code using regex patterns."""
        tools = []
        
        try:
            # Extract tool definitions from TypeScript using regex patterns
            tools.extend(self._find_typescript_tool_enum(source_code))
            tools.extend(self._find_typescript_tool_handlers(source_code))
            tools.extend(self._find_typescript_tool_list(source_code))
            
            logger.debug(
                f"Extracted tools from TypeScript source",
                file_path=file_path,
                tools_count=len(tools)
            )
            
        except Exception as e:
            logger.error(
                f"Unexpected error analyzing TypeScript source",
                file_path=file_path,
                error=e
            )
        
        return tools
    
    def _find_typescript_tool_enum(self, source_code: str) -> List[MCPTool]:
        """Find tools defined in TypeScript enum ToolName."""
        tools = []
        
        # Look for enum ToolName pattern
        enum_pattern = r'enum\s+ToolName\s*\{([^}]+)\}'
        enum_match = re.search(enum_pattern, source_code, re.DOTALL)
        
        if enum_match:
            enum_content = enum_match.group(1)
            # Extract tool names from enum
            name_pattern = r'(\w+)\s*=\s*["\']([^"\']+)["\']'
            for match in re.finditer(name_pattern, enum_content):
                tool_name = match.group(2)
                
                # Try to find corresponding tool description
                description = self._find_typescript_tool_description(source_code, tool_name)
                input_schema = self._find_typescript_tool_schema(source_code, tool_name)
                
                tools.append(MCPTool(
                    name=tool_name,
                    description=description,
                    input_schema=input_schema,
                    annotations={},
                    is_destructive=False,
                    requires_auth=False
                ))
        
        return tools
    
    def _find_typescript_tool_handlers(self, source_code: str) -> List[MCPTool]:
        """Find tools defined in call_tool handler switch cases."""
        tools = []
        
        # Look for switch/case patterns in call_tool handlers
        switch_pattern = r'case\s+ToolName\.(\w+):|case\s+["\']([^"\']+)["\']:'
        
        for match in re.finditer(switch_pattern, source_code):
            tool_name = match.group(1) or match.group(2)
            if tool_name:
                description = self._find_typescript_tool_description(source_code, tool_name)
                input_schema = self._find_typescript_tool_schema(source_code, tool_name)
                
                tools.append(MCPTool(
                    name=tool_name,
                    description=description,
                    input_schema=input_schema,
                    annotations={},
                    is_destructive=False,
                    requires_auth=False
                ))
        
        return tools
    
    def _find_typescript_tool_list(self, source_code: str) -> List[MCPTool]:
        """Find tools defined in list_tools return statement."""
        tools = []
        
        # Look for Tool object definitions in list_tools
        tool_pattern = r'\{\s*name:\s*["\']([^"\']+)["\'],\s*description:\s*["\']([^"\']*)["\']'
        
        for match in re.finditer(tool_pattern, source_code):
            tool_name = match.group(1)
            description = match.group(2)
            input_schema = self._find_typescript_tool_schema(source_code, tool_name)
            
            tools.append(MCPTool(
                name=tool_name,
                description=description,
                input_schema=input_schema,
                annotations={},
                is_destructive=False,
                requires_auth=False
            ))
        
        return tools
    
    def _find_typescript_tool_description(self, source_code: str, tool_name: str) -> str:
        """Find description for a TypeScript tool."""
        # Look for description in tool definition
        desc_patterns = [
            rf'name:\s*["\']?{re.escape(tool_name)}["\']?,\s*description:\s*["\']([^"\']*)["\']',
            rf'["\']?{re.escape(tool_name)}["\']?:\s*\{{[^}}]*description:\s*["\']([^"\']*)["\']',
            rf'case\s+["\']?{re.escape(tool_name)}["\']?:.*?//\s*([^\n]*)',
        ]
        
        for pattern in desc_patterns:
            match = re.search(pattern, source_code, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return f"Tool: {tool_name}"
    
    def _find_typescript_tool_schema(self, source_code: str, tool_name: str) -> Dict[str, Any]:
        """Find input schema for a TypeScript tool."""
        # Look for Zod schema definitions
        schema_patterns = [
            rf'const\s+{re.escape(tool_name)}Schema\s*=\s*z\.object\(([^)]+)\)',
            rf'{re.escape(tool_name)}:\s*z\.object\(([^)]+)\)',
            rf'inputSchema:\s*({re.escape(tool_name)}Schema\.jsonSchema\(\))',
        ]
        
        for pattern in schema_patterns:
            match = re.search(pattern, source_code, re.DOTALL | re.IGNORECASE)
            if match:
                # Try to parse the Zod schema definition
                return self._parse_zod_schema(match.group(1))
        
        # Default schema
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def _parse_zod_schema(self, zod_definition: str) -> Dict[str, Any]:
        """Parse Zod schema definition to JSON schema."""
        schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        try:
            # Simple regex-based parsing of Zod object schemas
            # Look for field definitions like: field: z.string()
            field_pattern = r'(\w+):\s*z\.(\w+)\([^)]*\)'
            
            for match in re.finditer(field_pattern, zod_definition):
                field_name = match.group(1)
                zod_type = match.group(2)
                
                # Map Zod types to JSON schema types
                json_type = self._map_zod_type_to_json(zod_type)
                schema["properties"][field_name] = json_type
                
                # Check if field is optional (has .optional())
                if ".optional()" not in match.group(0):
                    schema["required"].append(field_name)
        
        except Exception as e:
            logger.debug(f"Failed to parse Zod schema", error=e)
        
        return schema
    
    def _map_zod_type_to_json(self, zod_type: str) -> Dict[str, str]:
        """Map Zod type to JSON schema type."""
        type_mapping = {
            "string": {"type": "string"},
            "number": {"type": "number"},
            "boolean": {"type": "boolean"},
            "array": {"type": "array"},
            "object": {"type": "object"},
            "enum": {"type": "string"},
            "literal": {"type": "string"},
            "union": {"type": "string"},
        }
        
        return type_mapping.get(zod_type.lower(), {"type": "string"})