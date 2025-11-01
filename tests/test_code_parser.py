"""
Tests for the code parser module.
"""

import pytest
from pathlib import Path

from src.analysis.code_parser import CodeParser, CodeElement, CodeAnalysis


class TestCodeParser:
    """Test cases for CodeParser."""
    
    def test_parse_file_success(self, sample_python_file):
        """Test successful file parsing."""
        parser = CodeParser()
        analysis = parser.parse_file(sample_python_file)
        
        assert isinstance(analysis, CodeAnalysis)
        assert analysis.file_path == sample_python_file
        assert analysis.total_lines > 0
        assert analysis.code_lines > 0
        assert len(analysis.elements) > 0
        assert len(analysis.imports) >= 2  # Should have os, sys imports
        assert analysis.syntax_errors == []
    
    def test_parse_file_not_found(self):
        """Test parsing non-existent file."""
        parser = CodeParser()
        
        with pytest.raises(FileNotFoundError):
            parser.parse_file("non_existent_file.py")
    
    def test_parse_file_syntax_error(self, temp_dir):
        """Test parsing file with syntax errors."""
        # Create file with syntax error
        bad_file = Path(temp_dir) / "bad_syntax.py"
        bad_file.write_text("def function(\n    # Missing closing parenthesis")
        
        parser = CodeParser()
        analysis = parser.parse_file(str(bad_file))
        
        assert len(analysis.syntax_errors) > 0
        assert analysis.elements == []
        assert analysis.complexity_score == 0
    
    def test_parse_directory(self, temp_dir):
        """Test directory parsing."""
        # Create multiple Python files
        for i in range(3):
            file_path = Path(temp_dir) / f"test_{i}.py"
            file_path.write_text(f"# Test file {i}\nprint('Hello {i}')")
        
        parser = CodeParser()
        analyses = parser.parse_directory(temp_dir, recursive=False)
        
        assert len(analyses) == 3
        assert all(isinstance(a, CodeAnalysis) for a in analyses)
    
    def test_parse_directory_recursive(self, temp_dir):
        """Test recursive directory parsing."""
        # Create subdirectory with Python files
        subdir = Path(temp_dir) / "subdir"
        subdir.mkdir()
        
        # Files in root
        (Path(temp_dir) / "root_file.py").write_text("print('root')")
        
        # Files in subdirectory
        (subdir / "sub_file.py").write_text("print('sub')")
        
        parser = CodeParser()
        
        # Non-recursive
        analyses_non_recursive = parser.parse_directory(temp_dir, recursive=False)
        assert len(analyses_non_recursive) == 1
        
        # Recursive
        analyses_recursive = parser.parse_directory(temp_dir, recursive=True)
        assert len(analyses_recursive) == 2
    
    def test_code_analysis_to_dict(self, sample_python_file):
        """Test CodeAnalysis to_dict conversion."""
        parser = CodeParser()
        analysis = parser.parse_file(sample_python_file)
        
        data = analysis.to_dict()
        
        assert isinstance(data, dict)
        assert "file_path" in data
        assert "elements" in data
        assert "imports" in data
        assert isinstance(data["elements"], list)
    
    def test_element_extraction(self, sample_python_file):
        """Test extraction of code elements."""
        parser = CodeParser()
        analysis = parser.parse_file(sample_python_file)
        
        # Check for expected elements
        element_types = [e.element_type for e in analysis.elements]
        
        assert "class" in element_types
        assert "function" in element_types
        assert "import" in element_types
        
        # Find the TestClass
        test_class = next((e for e in analysis.elements if e.name == "TestClass"), None)
        assert test_class is not None
        assert test_class.element_type == "class"
        assert test_class.docstring is not None
    
    def test_import_extraction(self, sample_python_file):
        """Test import statement extraction."""
        parser = CodeParser()
        analysis = parser.parse_file(sample_python_file)
        
        # Should have os, sys, and typing imports
        assert "os" in analysis.imports
        assert "sys" in analysis.imports
        assert any("typing.List" in imp for imp in analysis.imports)
    
    def test_complexity_calculation(self, sample_python_file):
        """Test complexity score calculation."""
        parser = CodeParser()
        analysis = parser.parse_file(sample_python_file)
        
        # Should have some complexity due to if statements
        assert analysis.complexity_score > 0
        
        # Functions should have complexity scores
        functions = [e for e in analysis.elements if e.element_type == "function"]
        assert len(functions) > 0
        assert any(f.complexity > 1 for f in functions)


class TestCodeElement:
    """Test cases for CodeElement."""
    
    def test_code_element_creation(self):
        """Test CodeElement creation."""
        element = CodeElement(
            element_type="function",
            name="test_function",
            line_number=10,
            column_number=4,
            source_code="def test_function():\n    pass",
            docstring="Test function",
            arguments=["arg1", "arg2"]
        )
        
        assert element.element_type == "function"
        assert element.name == "test_function"
        assert element.line_number == 10
        assert len(element.arguments) == 2
        assert element.decorators == []  # Should be initialized as empty list
    
    def test_code_element_post_init(self):
        """Test CodeElement __post_init__ method."""
        element = CodeElement(
            element_type="function",
            name="test",
            line_number=1,
            column_number=0
        )
        
        # Lists should be initialized
        assert element.decorators == []
        assert element.arguments == []

