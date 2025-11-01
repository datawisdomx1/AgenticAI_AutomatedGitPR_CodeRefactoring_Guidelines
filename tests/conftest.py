"""
Pytest configuration and fixtures for testing.
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
import os
import sys

# Add src to Python path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.config.settings import Settings
from src.database.vector_db_manager import VectorDBManager
from src.analysis.code_parser import CodeParser
from src.analysis.rag_system import RAGSystem


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_python_file(temp_dir):
    """Create a sample Python file for testing."""
    content = '''
"""Sample Python file for testing."""

import os
import sys
from typing import List, Dict

class TestClass:
    """A test class."""
    
    def __init__(self, name: str):
        self.name = name
        self.data = []
    
    def add_data(self, item: str) -> None:
        """Add data to the list."""
        self.data.append(item)
    
    def get_data(self) -> List[str]:
        """Get all data."""
        return self.data

def test_function(x: int, y: int) -> int:
    """A test function with some issues."""
    if x>y:  # Missing spaces around operator
        return x+y  # Missing spaces around operator
    else:
        return y-x  # Missing spaces around operator

def another_function():
    """Function with naming issues."""
    myVariable = "test"  # Should be snake_case
    anotherVar = 42  # Should be snake_case
    return myVariable, anotherVar

# This is a very long line that exceeds the recommended line length and should be split into multiple lines for better readability
long_variable_name_that_is_too_long = "This is a string that makes the line very long and violates PEP 8 guidelines"
'''
    
    file_path = Path(temp_dir) / "test_file.py"
    with open(file_path, 'w') as f:
        f.write(content)
    
    return str(file_path)


@pytest.fixture
def sample_standards_data():
    """Sample code standards data for testing."""
    return [
        {
            "rule_id": "PEP8-E225",
            "title": "Missing whitespace around operator",
            "description": "Always surround binary operators with a single space on either side",
            "category": "formatting",
            "severity": "medium",
            "language": "python"
        },
        {
            "rule_id": "PEP8-N806",
            "title": "Variable name should be lowercase",
            "description": "Variable names should be lowercase with words separated by underscores",
            "category": "naming",
            "severity": "low",
            "language": "python"
        },
        {
            "rule_id": "PEP8-E501",
            "title": "Line too long",
            "description": "Limit all lines to a maximum of 79 characters for code",
            "category": "formatting",
            "severity": "medium",
            "language": "python"
        }
    ]


@pytest.fixture
def test_settings():
    """Create test settings."""
    return Settings(
        database=Settings.DatabaseSettings(
            url="sqlite:///test.db",
            host="localhost",
            port=5432,
            name="test_db",
            user="test_user",
            password="test_pass",
            schema="test_schema"
        ),
        llm=Settings.LLMSettings(
            openai_api_key="test_key",
            default_provider="openai",
            default_model="gpt-3.5-turbo",
            temperature=0.1
        ),
        vector_db=Settings.VectorDatabaseSettings(
            similarity_threshold=0.7,
            max_similar_rules=5
        ),
        app=Settings.ApplicationSettings(
            max_workers=2,
            batch_size=5,
            output_dir="./test_output",
            temp_dir="./test_temp"
        )
    )


@pytest.fixture
async def mock_vector_db():
    """Create a mock vector database manager."""
    class MockVectorDBManager:
        def __init__(self):
            self.standards = []
            self.initialized = False
        
        async def initialize(self):
            self.initialized = True
        
        async def store_code_standard(self, rule_id, title, description, category, severity="medium", language="python", metadata=None):
            standard = {
                "rule_id": rule_id,
                "title": title,
                "description": description,
                "category": category,
                "severity": severity,
                "language": language,
                "metadata": metadata
            }
            self.standards.append(standard)
            return len(self.standards)
        
        async def search_similar_standards(self, query_text, language="python", category=None, threshold=None, limit=None):
            # Simple mock implementation
            return [
                {
                    "rule_id": "TEST-001",
                    "title": "Test Rule",
                    "description": "A test rule for testing",
                    "category": "test",
                    "severity": "medium",
                    "similarity": 0.8
                }
            ]
        
        async def get_standards_count(self):
            return len(self.standards)
        
        async def get_all_categories(self):
            return list(set(s["category"] for s in self.standards))
        
        async def close(self):
            pass
    
    return MockVectorDBManager()


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return '''
    {
        "violations": [
            {
                "rule_id": "PEP8-E225",
                "line_number": 25,
                "column_number": 8,
                "violation_description": "Missing whitespace around operator",
                "problematic_code": "if x>y:",
                "suggested_fix": "if x > y:",
                "severity": "medium",
                "confidence_score": 0.9
            },
            {
                "rule_id": "PEP8-N806",
                "line_number": 31,
                "column_number": 4,
                "violation_description": "Variable name should be lowercase",
                "problematic_code": "myVariable = \"test\"",
                "suggested_fix": "my_variable = \"test\"",
                "severity": "low",
                "confidence_score": 0.8
            }
        ],
        "summary": {
            "total_violations": 2,
            "high_severity": 0,
            "medium_severity": 1,
            "low_severity": 1,
            "overall_assessment": "Code has minor style violations that should be addressed"
        }
    }
    '''


@pytest.fixture
def git_repo(temp_dir):
    """Create a temporary Git repository for testing."""
    import git
    
    repo_path = Path(temp_dir) / "test_repo"
    repo_path.mkdir()
    
    # Initialize repo
    repo = git.Repo.init(repo_path)
    
    # Create a test file
    test_file = repo_path / "test.py"
    test_file.write_text("print('Hello, World!')")
    
    # Initial commit
    repo.index.add([str(test_file)])
    repo.index.commit("Initial commit")
    
    return str(repo_path)


@pytest.fixture
def sample_violations():
    """Sample violations data for testing."""
    return [
        {
            "rule_id": "PEP8-E225",
            "line_number": 25,
            "column_number": 8,
            "violation_description": "Missing whitespace around operator",
            "problematic_code": "if x>y:",
            "suggested_fix": "if x > y:",
            "severity": "medium",
            "confidence_score": 0.9
        },
        {
            "rule_id": "PEP8-N806",
            "line_number": 31,
            "column_number": 4,
            "violation_description": "Variable name should be lowercase",
            "problematic_code": "myVariable = \"test\"",
            "suggested_fix": "my_variable = \"test\"",
            "severity": "low",
            "confidence_score": 0.8
        }
    ]

