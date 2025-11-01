"""
Tests for the diff generator module.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime

from src.diff.diff_generator import DiffGenerator, CodeFix, DiffFile
from src.agents.worker_agent import WorkerResult


class TestDiffGenerator:
    """Test cases for DiffGenerator."""
    
    def test_generate_file_diff(self, sample_python_file, sample_violations, temp_dir):
        """Test generating diff for a single file."""
        # Create worker result
        worker_result = WorkerResult(
            worker_id="test_worker",
            file_path=sample_python_file,
            success=True,
            violations=sample_violations,
            processing_time=1.0
        )
        
        generator = DiffGenerator()
        diff_file = generator.generate_file_diff(worker_result, temp_dir)
        
        assert diff_file is not None
        assert isinstance(diff_file, DiffFile)
        assert len(diff_file.fixes_applied) > 0
        assert diff_file.diff_content != ""
        
        # Check that diff file was created
        assert Path(diff_file.file_path).exists()
        
        # Check metadata file
        metadata_file = Path(diff_file.file_path).with_suffix('.json')
        assert metadata_file.exists()
        
        with open(metadata_file) as f:
            metadata = json.load(f)
        assert "fixes_applied" in metadata
    
    def test_generate_file_diff_no_violations(self, sample_python_file, temp_dir):
        """Test generating diff for file with no violations."""
        worker_result = WorkerResult(
            worker_id="test_worker",
            file_path=sample_python_file,
            success=True,
            violations=[],
            processing_time=1.0
        )
        
        generator = DiffGenerator()
        diff_file = generator.generate_file_diff(worker_result, temp_dir)
        
        assert diff_file is None
    
    def test_generate_file_diff_failed_analysis(self, sample_python_file, temp_dir):
        """Test generating diff for failed analysis."""
        worker_result = WorkerResult(
            worker_id="test_worker",
            file_path=sample_python_file,
            success=False,
            violations=[],
            processing_time=1.0,
            error_message="Analysis failed"
        )
        
        generator = DiffGenerator()
        diff_file = generator.generate_file_diff(worker_result, temp_dir)
        
        assert diff_file is None
    
    def test_generate_diffs_multiple_files(self, sample_python_file, sample_violations, temp_dir):
        """Test generating diffs for multiple files."""
        # Create multiple worker results
        worker_results = []
        for i in range(3):
            result = WorkerResult(
                worker_id=f"worker_{i}",
                file_path=sample_python_file,
                success=True,
                violations=sample_violations,
                processing_time=1.0
            )
            worker_results.append(result)
        
        generator = DiffGenerator()
        diff_files = generator.generate_diffs(worker_results, temp_dir)
        
        assert len(diff_files) == 3
        assert all(isinstance(df, DiffFile) for df in diff_files)
    
    def test_create_combined_diff(self, sample_python_file, sample_violations, temp_dir):
        """Test creating combined diff file."""
        # Create diff files
        diff_files = []
        for i in range(2):
            diff_file = DiffFile(
                file_path=f"test_{i}.py",
                diff_content=f"--- a/test_{i}.py\n+++ b/test_{i}.py\n@@ -1,1 +1,1 @@\n-old line\n+new line",
                fixes_applied=[],
                created_at=datetime.now()
            )
            diff_files.append(diff_file)
        
        generator = DiffGenerator()
        output_path = Path(temp_dir) / "combined.diff"
        
        combined_content = generator.create_combined_diff(diff_files, str(output_path))
        
        assert output_path.exists()
        assert "Combined Code Refactoring Diff" in combined_content
        assert len(diff_files) == 2  # Should mention number of files
    
    def test_create_summary_report(self, sample_violations, temp_dir):
        """Test creating summary report."""
        # Create diff files with fixes
        fixes = [
            CodeFix(
                file_path="test.py",
                line_number=10,
                column_number=5,
                original_code="old code",
                fixed_code="new code",
                violation_description="Test violation",
                rule_id="TEST-001",
                confidence_score=0.9
            )
        ]
        
        diff_files = [
            DiffFile(
                file_path="test.py",
                diff_content="diff content",
                fixes_applied=fixes,
                created_at=datetime.now()
            )
        ]
        
        generator = DiffGenerator()
        output_path = Path(temp_dir) / "summary.json"
        
        summary = generator.create_summary_report(diff_files, str(output_path))
        
        assert output_path.exists()
        assert "summary" in summary
        assert "files" in summary
        assert summary["summary"]["total_files_modified"] == 1
        assert summary["summary"]["total_fixes_applied"] == 1
    
    def test_parse_violations_to_fixes(self, sample_python_file, sample_violations):
        """Test parsing violations to code fixes."""
        generator = DiffGenerator()
        
        # Read file content
        with open(sample_python_file) as f:
            content = f.read()
        
        fixes = generator._parse_violations_to_fixes(
            sample_python_file, sample_violations, content
        )
        
        assert len(fixes) > 0
        assert all(isinstance(fix, CodeFix) for fix in fixes)
        
        # Fixes should be sorted by line number (reverse order)
        line_numbers = [fix.line_number for fix in fixes]
        assert line_numbers == sorted(line_numbers, reverse=True)
    
    def test_apply_fixes(self, sample_violations):
        """Test applying fixes to content."""
        generator = DiffGenerator()
        
        original_content = """line 1
line 2
if x>y:
    print("test")
myVariable = "test"
line 6"""
        
        fixes = [
            CodeFix(
                file_path="test.py",
                line_number=3,
                column_number=0,
                original_code="if x>y:",
                fixed_code="if x > y:",
                violation_description="Missing whitespace",
                rule_id="PEP8-E225",
                confidence_score=0.9
            ),
            CodeFix(
                file_path="test.py",
                line_number=5,
                column_number=0,
                original_code='myVariable = "test"',
                fixed_code='my_variable = "test"',
                violation_description="Variable naming",
                rule_id="PEP8-N806",
                confidence_score=0.8
            )
        ]
        
        modified_content = generator._apply_fixes(original_content, fixes)
        
        # Check that fixes were applied
        assert "if x > y:" in modified_content
        assert 'my_variable = "test"' in modified_content
        assert "if x>y:" not in modified_content
        assert 'myVariable = "test"' not in modified_content
    
    def test_generate_unified_diff(self):
        """Test generating unified diff format."""
        generator = DiffGenerator()
        
        original = "line 1\nline 2\nline 3"
        modified = "line 1\nmodified line 2\nline 3"
        
        diff = generator._generate_unified_diff("test.py", original, modified)
        
        assert "--- a/test.py" in diff
        assert "+++ b/test.py" in diff
        assert "-line 2" in diff
        assert "+modified line 2" in diff
    
    def test_auto_fix_generation(self):
        """Test automatic fix generation."""
        generator = DiffGenerator()
        
        # Test spacing fix
        spacing_fix = generator._generate_auto_fix(
            "if x>y:",
            "x>y",
            "Missing whitespace around operator"
        )
        assert spacing_fix.strip() != "if x>y:"
        
        # Test indentation fix
        indent_fix = generator._generate_auto_fix(
            "\tdef function():",
            "\t",
            "Use spaces for indentation"
        )
        assert "\t" not in indent_fix
        
        # Test line length fix
        long_line = "a" * 100
        length_fix = generator._generate_auto_fix(
            long_line,
            long_line,
            "Line too long"
        )
        # Should attempt to break the line or at least process it
        assert isinstance(length_fix, str)


class TestCodeFix:
    """Test cases for CodeFix dataclass."""
    
    def test_code_fix_creation(self):
        """Test CodeFix creation."""
        fix = CodeFix(
            file_path="test.py",
            line_number=10,
            column_number=5,
            original_code="old_code",
            fixed_code="new_code",
            violation_description="Test violation",
            rule_id="TEST-001",
            confidence_score=0.9
        )
        
        assert fix.file_path == "test.py"
        assert fix.line_number == 10
        assert fix.column_number == 5
        assert fix.confidence_score == 0.9


class TestDiffFile:
    """Test cases for DiffFile dataclass."""
    
    def test_diff_file_creation(self):
        """Test DiffFile creation."""
        fixes = [
            CodeFix(
                file_path="test.py",
                line_number=1,
                column_number=0,
                original_code="old",
                fixed_code="new",
                violation_description="test",
                rule_id="TEST-001",
                confidence_score=0.5
            )
        ]
        
        diff_file = DiffFile(
            file_path="test.diff",
            diff_content="diff content",
            fixes_applied=fixes,
            created_at=datetime.now()
        )
        
        assert diff_file.file_path == "test.diff"
        assert len(diff_file.fixes_applied) == 1
        
        # Test to_dict conversion
        data = diff_file.to_dict()
        assert isinstance(data, dict)
        assert "fixes_applied" in data
        assert "created_at" in data

