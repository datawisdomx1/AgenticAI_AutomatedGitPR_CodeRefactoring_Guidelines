"""
Diff generator for creating code update files based on violations.
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
import difflib
import ast

from ..agents.worker_agent import WorkerResult
from ..config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class CodeFix:
    """Represents a code fix for a violation."""
    file_path: str
    line_number: int
    column_number: Optional[int]
    original_code: str
    fixed_code: str
    violation_description: str
    rule_id: str
    confidence_score: float


@dataclass
class DiffFile:
    """Represents a diff file with metadata."""
    file_path: str
    diff_content: str
    fixes_applied: List[CodeFix]
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'file_path': self.file_path,
            'diff_content': self.diff_content,
            'fixes_applied': [asdict(fix) for fix in self.fixes_applied],
            'created_at': self.created_at.isoformat()
        }


class DiffGenerator:
    """Generates diff files for code refactoring based on violations."""
    
    def __init__(self):
        self.settings = settings
        
    def generate_diffs(
        self,
        worker_results: List[WorkerResult],
        output_dir: Optional[str] = None
    ) -> List[DiffFile]:
        """Generate diff files for all worker results."""
        try:
            print("🔧 Generating diff files...")
            
            output_dir = output_dir or self.settings.app.output_dir
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            all_diff_files = []
            
            for result in worker_results:
                if result.success and result.violations:
                    print(f"📝 Processing {result.file_path}: {len(result.violations)} violations")
                    
                    diff_file = self.generate_file_diff(result, str(output_path))
                    if diff_file:
                        all_diff_files.append(diff_file)
                        print(f"✅ Generated diff for {result.file_path}")
                else:
                    print(f"⏭️  Skipping {result.file_path}: {'no violations' if result.success else 'failed analysis'}")
            
            print(f"🎉 Generated {len(all_diff_files)} diff files")
            return all_diff_files
            
        except Exception as e:
            logger.error(f"Failed to generate diffs: {e}")
            raise
    
    def generate_file_diff(
        self,
        worker_result: WorkerResult,
        output_dir: str
    ) -> Optional[DiffFile]:
        """Generate a diff file for a single file's violations."""
        try:
            if not worker_result.violations:
                return None
            
            # Read the original file
            original_content = self._read_file(worker_result.file_path)
            if original_content is None:
                return None
            
            # Parse violations and generate fixes
            fixes = self._parse_violations_to_fixes(
                worker_result.file_path,
                worker_result.violations,
                original_content
            )
            
            if not fixes:
                logger.warning(f"No fixes generated for {worker_result.file_path}")
                return None
            
            # Apply fixes to create modified content
            modified_content = self._apply_fixes(original_content, fixes)
            
            # Generate unified diff
            diff_content = self._generate_unified_diff(
                worker_result.file_path,
                original_content,
                modified_content
            )
            
            # Create diff file
            diff_file_name = self._get_diff_file_name(worker_result.file_path)
            diff_file_path = Path(output_dir) / diff_file_name
            
            # Write diff file
            with open(diff_file_path, 'w', encoding='utf-8') as f:
                f.write(diff_content)
            
            # Create DiffFile object
            diff_file = DiffFile(
                file_path=str(diff_file_path),
                diff_content=diff_content,
                fixes_applied=fixes,
                created_at=datetime.now()
            )
            
            # Also write metadata
            metadata_file = diff_file_path.with_suffix('.json')
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(diff_file.to_dict(), f, indent=2, ensure_ascii=False)
            
            return diff_file
            
        except Exception as e:
            logger.error(f"Failed to generate diff for {worker_result.file_path}: {e}")
            return None
    
    def _read_file(self, file_path: str) -> Optional[str]:
        """Read file content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return None
    
    def _parse_violations_to_fixes(
        self,
        file_path: str,
        violations: List[Dict[str, Any]],
        file_content: str
    ) -> List[CodeFix]:
        """Parse violations and convert to code fixes."""
        fixes = []
        lines = file_content.split('\n')
        
        for violation in violations:
            try:
                fix = self._create_fix_from_violation(violation, lines, file_path)
                if fix:
                    fixes.append(fix)
            except Exception as e:
                logger.warning(f"Failed to create fix for violation: {e}")
                continue
        
        # Sort fixes by line number (reverse order to avoid line number shifts)
        fixes.sort(key=lambda x: x.line_number, reverse=True)
        
        return fixes
    
    def _create_fix_from_violation(
        self,
        violation: Dict[str, Any],
        lines: List[str],
        file_path: str
    ) -> Optional[CodeFix]:
        """Create a code fix from a violation."""
        try:
            line_number = violation.get('line_number')
            if line_number is None or line_number < 1 or line_number > len(lines):
                return None
            
            # Get original code
            original_line = lines[line_number - 1]  # Convert to 0-based index
            
            # Extract suggested fix
            suggested_fix = violation.get('suggested_fix', '').strip()
            if not suggested_fix:
                # Try to extract fix from problematic_code
                problematic_code = violation.get('problematic_code', '').strip()
                if problematic_code:
                    suggested_fix = self._generate_auto_fix(
                        original_line,
                        problematic_code,
                        violation.get('violation_description', '')
                    )
            
            if not suggested_fix:
                logger.warning(f"No fix available for violation at line {line_number}")
                return None
            
            return CodeFix(
                file_path=file_path,
                line_number=line_number,
                column_number=violation.get('column_number'),
                original_code=original_line,
                fixed_code=suggested_fix,
                violation_description=violation.get('violation_description', ''),
                rule_id=violation.get('rule_id', 'unknown'),
                confidence_score=violation.get('confidence_score', 0.0)
            )
            
        except Exception as e:
            logger.error(f"Failed to create fix from violation: {e}")
            return None
    
    def _generate_auto_fix(
        self,
        original_line: str,
        problematic_code: str,
        violation_description: str
    ) -> str:
        """Generate automatic fix based on common patterns."""
        try:
            # Common fixes based on violation patterns
            
            # Indentation fixes
            if 'indentation' in violation_description.lower():
                return self._fix_indentation(original_line)
            
            # Spacing fixes
            if 'space' in violation_description.lower():
                return self._fix_spacing(original_line)
            
            # Import fixes
            if 'import' in violation_description.lower():
                return self._fix_imports(original_line)
            
            # Line length fixes
            if 'line too long' in violation_description.lower():
                return self._fix_line_length(original_line)
            
            # Naming convention fixes
            if 'naming' in violation_description.lower() or 'convention' in violation_description.lower():
                return self._fix_naming_convention(original_line, problematic_code)
            
            # Default: return original line with basic cleanup
            return original_line.rstrip() + '\n'
            
        except Exception:
            return original_line
    
    def _fix_indentation(self, line: str) -> str:
        """Fix indentation issues."""
        # Convert tabs to spaces
        line = line.expandtabs(4)
        
        # Fix basic indentation (assuming 4 spaces)
        stripped = line.lstrip()
        if stripped:
            indent_level = (len(line) - len(stripped)) // 4
            return '    ' * indent_level + stripped
        
        return line
    
    def _fix_spacing(self, line: str) -> str:
        """Fix spacing issues."""
        # Fix spacing around operators
        line = re.sub(r'([=+\-*/%<>!]=?)\s*', r'\1 ', line)
        line = re.sub(r'\s*([=+\-*/%<>!]=?)', r' \1', line)
        
        # Fix spacing after commas
        line = re.sub(r',(\S)', r', \1', line)
        
        # Fix spacing around parentheses
        line = re.sub(r'\(\s+', '(', line)
        line = re.sub(r'\s+\)', ')', line)
        
        # Remove trailing whitespace
        return line.rstrip()
    
    def _fix_imports(self, line: str) -> str:
        """Fix import statement issues."""
        # Sort imports (basic implementation)
        if line.strip().startswith('import ') or line.strip().startswith('from '):
            return line.strip()
        
        return line
    
    def _fix_line_length(self, line: str, max_length: int = 88) -> str:
        """Fix line length issues."""
        if len(line) <= max_length:
            return line
        
        # Simple line breaking for long lines
        stripped = line.strip()
        
        # Break at logical points
        for break_point in [', ', ' and ', ' or ', ' + ', ' - ']:
            if break_point in stripped:
                parts = stripped.split(break_point)
                if len(parts) > 1:
                    # Find a good breaking point
                    for i in range(1, len(parts)):
                        first_part = break_point.join(parts[:i])
                        if len(first_part) < max_length:
                            indent = '    '  # Add extra indentation
                            remaining = break_point.join(parts[i:])
                            return first_part + break_point.rstrip() + '\n' + indent + remaining
        
        return line
    
    def _fix_naming_convention(self, line: str, problematic_code: str) -> str:
        """Fix naming convention issues."""
        # Convert camelCase to snake_case for variables
        def camel_to_snake(name):
            s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
            return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        
        # Find camelCase identifiers and convert them
        words = re.findall(r'\b[a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*\b', line)
        for word in words:
            snake_case = camel_to_snake(word)
            line = line.replace(word, snake_case)
        
        return line
    
    def _apply_fixes(self, original_content: str, fixes: List[CodeFix]) -> str:
        """Apply all fixes to the original content."""
        try:
            lines = original_content.split('\n')
            
            # Apply fixes (already sorted in reverse order)
            for fix in fixes:
                if 1 <= fix.line_number <= len(lines):
                    # Replace the line with the fixed version
                    lines[fix.line_number - 1] = fix.fixed_code.rstrip()
            
            return '\n'.join(lines)
            
        except Exception as e:
            logger.error(f"Failed to apply fixes: {e}")
            return original_content
    
    def _generate_unified_diff(
        self,
        file_path: str,
        original_content: str,
        modified_content: str
    ) -> str:
        """Generate unified diff format."""
        try:
            original_lines = original_content.splitlines(keepends=True)
            modified_lines = modified_content.splitlines(keepends=True)
            
            diff = difflib.unified_diff(
                original_lines,
                modified_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm=''
            )
            
            return ''.join(diff)
            
        except Exception as e:
            logger.error(f"Failed to generate unified diff: {e}")
            return ""
    
    def _get_diff_file_name(self, file_path: str) -> str:
        """Generate diff file name."""
        file_name = Path(file_path).name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{file_name}_{timestamp}.diff"
    
    def create_combined_diff(
        self,
        diff_files: List[DiffFile],
        output_path: str
    ) -> str:
        """Create a combined diff file from multiple individual diffs."""
        try:
            print("📋 Creating combined diff file...")
            
            combined_content = []
            
            # Add header
            combined_content.append(f"# Combined Code Refactoring Diff")
            combined_content.append(f"# Generated on: {datetime.now().isoformat()}")
            combined_content.append(f"# Total files modified: {len(diff_files)}")
            combined_content.append("")
            
            # Combine all diffs
            for diff_file in diff_files:
                combined_content.append(f"# File: {diff_file.file_path}")
                combined_content.append(f"# Fixes applied: {len(diff_file.fixes_applied)}")
                combined_content.append("")
                combined_content.append(diff_file.diff_content)
                combined_content.append("")
                combined_content.append("# " + "="*50)
                combined_content.append("")
            
            # Write combined diff
            combined_diff_content = '\n'.join(combined_content)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(combined_diff_content)
            
            print(f"✅ Combined diff created: {output_path}")
            return combined_diff_content
            
        except Exception as e:
            logger.error(f"Failed to create combined diff: {e}")
            raise
    
    def create_summary_report(
        self,
        diff_files: List[DiffFile],
        output_path: str
    ) -> Dict[str, Any]:
        """Create a summary report of all changes."""
        try:
            print("📊 Creating summary report...")
            
            # Collect statistics
            total_files = len(diff_files)
            total_fixes = sum(len(df.fixes_applied) for df in diff_files)
            
            # Group by rule types
            rule_counts = {}
            confidence_scores = []
            
            for diff_file in diff_files:
                for fix in diff_file.fixes_applied:
                    rule_id = fix.rule_id
                    rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1
                    confidence_scores.append(fix.confidence_score)
            
            # Calculate average confidence
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
            
            # Create summary
            summary = {
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'total_files_modified': total_files,
                    'total_fixes_applied': total_fixes,
                    'average_confidence_score': round(avg_confidence, 3),
                    'most_common_violations': dict(sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)[:10])
                },
                'files': []
            }
            
            # Add file details
            for diff_file in diff_files:
                file_summary = {
                    'file_path': diff_file.file_path,
                    'fixes_count': len(diff_file.fixes_applied),
                    'fixes': [
                        {
                            'line_number': fix.line_number,
                            'rule_id': fix.rule_id,
                            'description': fix.violation_description,
                            'confidence': fix.confidence_score
                        }
                        for fix in diff_file.fixes_applied
                    ]
                }
                summary['files'].append(file_summary)
            
            # Write summary report
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Summary report created: {output_path}")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to create summary report: {e}")
            raise


# Global diff generator instance
diff_generator = DiffGenerator()

