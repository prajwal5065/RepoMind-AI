import ast
from typing import Optional
from models.response_models import ParsedFile, ParsedFunction, ParsedClass, ParsedImport, ParsedRoute
from utils.logger import get_logger

logger = get_logger(__name__)

class ASTVisitor(ast.NodeVisitor):
    def __init__(self):
        self.functions = []
        self.classes = []
        self.imports = []
        self.routes = []

    def _get_decorator_name(self, decorator: ast.expr) -> Optional[str]:
        if isinstance(decorator, ast.Call):
            return self._get_decorator_name(decorator.func)
        elif isinstance(decorator, ast.Attribute):
            base = self._get_decorator_name(decorator.value)
            return f"{base}.{decorator.attr}" if base else decorator.attr
        elif isinstance(decorator, ast.Name):
            return decorator.id
        return None

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(ParsedImport(module=alias.name, names=[alias.name]))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module if node.module else ""
        names = [alias.name for alias in node.names]
        self.imports.append(ParsedImport(module=module, names=names))
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        methods = []
        for body_item in node.body:
            if isinstance(body_item, ast.FunctionDef) or isinstance(body_item, ast.AsyncFunctionDef):
                methods.append(body_item.name)
        
        self.classes.append(ParsedClass(
            name=node.name,
            line_number=node.lineno,
            line_end=getattr(node, 'end_lineno', node.lineno),
            methods=methods
        ))
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node):
        self._handle_function(node)

    def _handle_function(self, node):
        is_route = False
        for decorator in node.decorator_list:
            dec_name = self._get_decorator_name(decorator)
            if dec_name:
                # Basic heuristic for common routing decorators: @app.get, @router.post etc.
                dec_lower = dec_name.lower()
                if any(method in dec_lower for method in ['.get', '.post', '.put', '.delete', '.patch']) \
                   or dec_lower.startswith('app.') or dec_lower.startswith('router.'):
                    self.routes.append(ParsedRoute(
                        decorator=dec_name,
                        function_name=node.name,
                        line_number=node.lineno,
                        line_end=getattr(node, 'end_lineno', node.lineno)
                    ))
                    is_route = True
        
        # We append the function regardless of whether it's a route, 
        # so we have a complete list of functions.
        self.functions.append(ParsedFunction(
            name=node.name,
            line_number=node.lineno,
            line_end=getattr(node, 'end_lineno', node.lineno)
        ))
        
        self.generic_visit(node)


def parse_python_file(file_path: str) -> Optional[ParsedFile]:
    """Parses a Python file and returns a ParsedFile object with AST details."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
            
        tree = ast.parse(source, filename=file_path)
        visitor = ASTVisitor()
        visitor.visit(tree)
        
        return ParsedFile(
            file_path=file_path,
            functions=visitor.functions,
            classes=visitor.classes,
            imports=visitor.imports,
            routes=visitor.routes
        )
    except SyntaxError as e:
        logger.warning(f"Syntax error in {file_path}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to parse {file_path}: {e}")
        return None
