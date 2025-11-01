"""
AST-based code parser for analyzing Python files.
"""

import ast
import logging
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
import inspect

logger = logging.getLogger(__name__)


@dataclass
class CodeElement:
    """Represents a code element found in the AST."""
    element_type: str  # function, class, import, variable, etc.
    name: str
    line_number: int
    column_number: int
    end_line_number: Optional[int] = None
    end_column_number: Optional[int] = None
    source_code: Optional[str] = None
    docstring: Optional[str] = None
    decorators: List[str] = None
    arguments: List[str] = None
    parent: Optional[str] = None
    complexity: int = 0
    
    def __post_init__(self):
        if self.decorators is None:
            self.decorators = []
        if self.arguments is None:
            self.arguments = []


@dataclass
class CodeAnalysis:
    """Contains the complete analysis of a code file."""
    file_path: str
    file_hash: str
    total_lines: int
    code_lines: int
    comment_lines: int
    blank_lines: int
    elements: List[CodeElement]
    imports: List[str]
    syntax_errors: List[str]
    complexity_score: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'file_path': self.file_path,
            'file_hash': self.file_hash,
            'total_lines': self.total_lines,
            'code_lines': self.code_lines,
            'comment_lines': self.comment_lines,
            'blank_lines': self.blank_lines,
            'elements': [asdict(elem) for elem in self.elements],
            'imports': self.imports,
            'syntax_errors': self.syntax_errors,
            'complexity_score': self.complexity_score
        }


class CodeParser:
    """AST-based code parser for Python files."""
    
    def __init__(self):
        self.complexity_weights = {
            'if': 1, 'elif': 1, 'else': 0,
            'for': 1, 'while': 1,
            'try': 0, 'except': 1, 'finally': 0,
            'with': 1,
            'and': 1, 'or': 1,
            'lambda': 1,
            'comprehension': 1
        }
    
    def parse_file(self, file_path: str) -> CodeAnalysis:
        """Parse a Python file and return code analysis."""
        try:
            print(f"🔍 Parsing file: {file_path}")
            
            file_path_obj = Path(file_path)
            if not file_path_obj.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Calculate file hash
            file_hash = hashlib.sha256(content.encode()).hexdigest()
            
            # Analyze line counts
            lines = content.split('\n')
            total_lines = len(lines)
            blank_lines = sum(1 for line in lines if not line.strip())
            comment_lines = sum(1 for line in lines if line.strip().startswith('#'))
            code_lines = total_lines - blank_lines - comment_lines
            
            # Parse AST
            try:
                tree = ast.parse(content, filename=file_path)
                syntax_errors = []
            except SyntaxError as e:
                print(f"❌ Syntax error in {file_path}: {e}")
                return CodeAnalysis(
                    file_path=file_path,
                    file_hash=file_hash,
                    total_lines=total_lines,
                    code_lines=code_lines,
                    comment_lines=comment_lines,
                    blank_lines=blank_lines,
                    elements=[],
                    imports=[],
                    syntax_errors=[str(e)],
                    complexity_score=0
                )
            
            # Analyze AST
            analyzer = ASTAnalyzer(content.split('\n'))
            analyzer.visit(tree)
            
            analysis = CodeAnalysis(
                file_path=file_path,
                file_hash=file_hash,
                total_lines=total_lines,
                code_lines=code_lines,
                comment_lines=comment_lines,
                blank_lines=blank_lines,
                elements=analyzer.elements,
                imports=analyzer.imports,
                syntax_errors=[],
                complexity_score=analyzer.total_complexity
            )
            
            print(f"✅ Parsed {file_path}: {len(analysis.elements)} elements, complexity: {analysis.complexity_score}")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to parse file {file_path}: {e}")
            raise
    
    def parse_directory(self, directory_path: str, recursive: bool = True) -> List[CodeAnalysis]:
        """Parse all Python files in a directory."""
        try:
            print(f"📁 Parsing directory: {directory_path}")
            
            directory = Path(directory_path)
            if not directory.exists():
                raise FileNotFoundError(f"Directory not found: {directory_path}")
            
            # Find Python files
            if recursive:
                python_files = list(directory.rglob("*.py"))
            else:
                python_files = list(directory.glob("*.py"))
            
            print(f"📄 Found {len(python_files)} Python files")
            
            analyses = []
            for file_path in python_files:
                try:
                    analysis = self.parse_file(str(file_path))
                    analyses.append(analysis)
                except Exception as e:
                    logger.warning(f"Failed to parse {file_path}: {e}")
                    continue
            
            print(f"✅ Successfully parsed {len(analyses)} files")
            return analyses
            
        except Exception as e:
            logger.error(f"Failed to parse directory {directory_path}: {e}")
            raise


class ASTAnalyzer(ast.NodeVisitor):
    """AST node visitor for extracting code elements."""
    
    def __init__(self, source_lines: List[str]):
        self.source_lines = source_lines
        self.elements: List[CodeElement] = []
        self.imports: List[str] = []
        self.current_class: Optional[str] = None
        self.total_complexity = 0
        
    def _get_source_code(self, node: ast.AST) -> str:
        """Extract source code for a node."""
        try:
            if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
                start_line = node.lineno - 1
                end_line = node.end_lineno
                
                if 0 <= start_line < len(self.source_lines):
                    if end_line and end_line <= len(self.source_lines):
                        lines = self.source_lines[start_line:end_line]
                    else:
                        lines = [self.source_lines[start_line]]
                    
                    return '\n'.join(lines)
            return ""
        except:
            return ""
    
    def _get_docstring(self, node: ast.AST) -> Optional[str]:
        """Extract docstring from a node."""
        try:
            if (hasattr(node, 'body') and 
                node.body and 
                isinstance(node.body[0], ast.Expr) and
                isinstance(node.body[0].value, ast.Constant) and
                isinstance(node.body[0].value.value, str)):
                return node.body[0].value.value
        except:
            pass
        return None
    
    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity for a node."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, ast.ListComp):
                complexity += 1
            elif isinstance(child, ast.DictComp):
                complexity += 1
            elif isinstance(child, ast.SetComp):
                complexity += 1
            elif isinstance(child, ast.GeneratorExp):
                complexity += 1
        
        return complexity
    
    def visit_Import(self, node: ast.Import):
        """Visit import statements."""
        for alias in node.names:
            import_name = alias.asname if alias.asname else alias.name
            self.imports.append(import_name)
            
            element = CodeElement(
                element_type="import",
                name=import_name,
                line_number=node.lineno,
                column_number=node.col_offset,
                source_code=self._get_source_code(node)
            )
            self.elements.append(element)
        
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Visit from...import statements."""
        module = node.module or ""
        for alias in node.names:
            import_name = f"{module}.{alias.name}" if module else alias.name
            self.imports.append(import_name)
            
            element = CodeElement(
                element_type="import_from",
                name=import_name,
                line_number=node.lineno,
                column_number=node.col_offset,
                source_code=self._get_source_code(node)
            )
            self.elements.append(element)
        
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definitions."""
        prev_class = self.current_class
        self.current_class = node.name
        
        # Extract decorators
        decorators = [self._get_source_code(decorator) for decorator in node.decorator_list]
        
        # Calculate complexity
        complexity = self._calculate_complexity(node)
        self.total_complexity += complexity
        
        element = CodeElement(
            element_type="class",
            name=node.name,
            line_number=node.lineno,
            column_number=node.col_offset,
            end_line_number=getattr(node, 'end_lineno', None),
            end_column_number=getattr(node, 'end_col_offset', None),
            source_code=self._get_source_code(node),
            docstring=self._get_docstring(node),
            decorators=decorators,
            parent=prev_class,
            complexity=complexity
        )
        self.elements.append(element)
        
        self.generic_visit(node)
        self.current_class = prev_class
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definitions."""
        # Extract arguments
        arguments = []
        for arg in node.args.args:
            arguments.append(arg.arg)
        
        # Extract decorators
        decorators = [self._get_source_code(decorator) for decorator in node.decorator_list]
        
        # Calculate complexity
        complexity = self._calculate_complexity(node)
        self.total_complexity += complexity
        
        element = CodeElement(
            element_type="function",
            name=node.name,
            line_number=node.lineno,
            column_number=node.col_offset,
            end_line_number=getattr(node, 'end_lineno', None),
            end_column_number=getattr(node, 'end_col_offset', None),
            source_code=self._get_source_code(node),
            docstring=self._get_docstring(node),
            decorators=decorators,
            arguments=arguments,
            parent=self.current_class,
            complexity=complexity
        )
        self.elements.append(element)
        
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function definitions."""
        # Extract arguments
        arguments = []
        for arg in node.args.args:
            arguments.append(arg.arg)
        
        # Extract decorators
        decorators = [self._get_source_code(decorator) for decorator in node.decorator_list]
        
        # Calculate complexity
        complexity = self._calculate_complexity(node)
        self.total_complexity += complexity
        
        element = CodeElement(
            element_type="async_function",
            name=node.name,
            line_number=node.lineno,
            column_number=node.col_offset,
            end_line_number=getattr(node, 'end_lineno', None),
            end_column_number=getattr(node, 'end_col_offset', None),
            source_code=self._get_source_code(node),
            docstring=self._get_docstring(node),
            decorators=decorators,
            arguments=arguments,
            parent=self.current_class,
            complexity=complexity
        )
        self.elements.append(element)
        
        self.generic_visit(node)
    
    def visit_Assign(self, node: ast.Assign):
        """Visit variable assignments."""
        for target in node.targets:
            if isinstance(target, ast.Name):
                element = CodeElement(
                    element_type="variable",
                    name=target.id,
                    line_number=node.lineno,
                    column_number=node.col_offset,
                    source_code=self._get_source_code(node),
                    parent=self.current_class
                )
                self.elements.append(element)
        
        self.generic_visit(node)


# Global parser instance
code_parser = CodeParser()

