"""
RAG (Retrieval-Augmented Generation) system for code analysis using cosine similarity.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json

from ..database.vector_db_manager import vector_db_manager
from ..analysis.code_parser import CodeAnalysis, CodeElement
from ..config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class RelevantRule:
    """Represents a relevant code standard rule."""
    rule_id: str
    title: str
    description: str
    category: str
    severity: str
    similarity: float
    context: Optional[str] = None


@dataclass
class RAGContext:
    """Contains the RAG context for code analysis."""
    file_analysis: CodeAnalysis
    code_element: Optional[CodeElement]
    relevant_rules: List[RelevantRule]
    analysis_prompt: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'file_analysis': self.file_analysis.to_dict(),
            'code_element': self.code_element.__dict__ if self.code_element else None,
            'relevant_rules': [rule.__dict__ for rule in self.relevant_rules],
            'analysis_prompt': self.analysis_prompt
        }


class RAGSystem:
    """RAG system for retrieving relevant code standards and generating analysis prompts."""
    
    def __init__(self):
        self.vector_db = vector_db_manager
        self.settings = settings
    
    async def initialize(self):
        """Initialize the RAG system."""
        try:
            print("🚀 Initializing RAG System...")
            await self.vector_db.initialize()
            print("✅ RAG System initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG system: {e}")
            raise
    
    async def get_relevant_rules(
        self,
        query_text: str,
        language: str = "python",
        category: Optional[str] = None,
        max_rules: Optional[int] = None
    ) -> List[RelevantRule]:
        """Retrieve relevant code standards using cosine similarity."""
        try:
            print(f"🔍 Retrieving relevant rules for: '{query_text[:50]}...'")
            
            max_rules = max_rules or self.settings.vector_db.max_similar_rules
            
            # Search for similar standards
            similar_standards = await self.vector_db.search_similar_standards(
                query_text=query_text,
                language=language,
                category=category,
                limit=max_rules
            )
            
            # Convert to RelevantRule objects
            relevant_rules = []
            for standard in similar_standards:
                rule = RelevantRule(
                    rule_id=standard['rule_id'],
                    title=standard['title'],
                    description=standard['description'],
                    category=standard['category'],
                    severity=standard['severity'],
                    similarity=standard['similarity']
                )
                relevant_rules.append(rule)
            
            print(f"✅ Found {len(relevant_rules)} relevant rules")
            return relevant_rules
            
        except Exception as e:
            logger.error(f"Failed to get relevant rules: {e}")
            raise
    
    async def generate_analysis_context(
        self,
        file_analysis: CodeAnalysis,
        code_element: Optional[CodeElement] = None
    ) -> RAGContext:
        """Generate RAG context for code analysis."""
        try:
            print(f"🧠 Generating analysis context for: {file_analysis.file_path}")
            
            # Create query text based on file analysis and specific element
            if code_element:
                query_text = self._create_element_query(code_element, file_analysis)
                print(f"  📍 Analyzing element: {code_element.element_type} '{code_element.name}'")
            else:
                query_text = self._create_file_query(file_analysis)
                print(f"  📄 Analyzing entire file")
            
            # Get relevant rules
            relevant_rules = await self.get_relevant_rules(query_text)
            
            # Generate analysis prompt
            analysis_prompt = self._generate_analysis_prompt(
                file_analysis, code_element, relevant_rules
            )
            
            # Create RAG context
            context = RAGContext(
                file_analysis=file_analysis,
                code_element=code_element,
                relevant_rules=relevant_rules,
                analysis_prompt=analysis_prompt
            )
            
            print(f"✅ Generated context with {len(relevant_rules)} relevant rules")
            return context
            
        except Exception as e:
            logger.error(f"Failed to generate analysis context: {e}")
            raise
    
    def _create_element_query(self, element: CodeElement, file_analysis: CodeAnalysis) -> str:
        """Create query text for a specific code element."""
        query_parts = []
        
        # Add element type and name
        query_parts.append(f"{element.element_type} named {element.name}")
        
        # Add element details
        if element.element_type == "function":
            if element.arguments:
                query_parts.append(f"with parameters {', '.join(element.arguments)}")
            if element.decorators:
                query_parts.append(f"decorated with {', '.join(element.decorators)}")
            if element.complexity > 5:
                query_parts.append("with high complexity")
        
        elif element.element_type == "class":
            if element.decorators:
                query_parts.append(f"decorated with {', '.join(element.decorators)}")
        
        # Add source code snippet if available
        if element.source_code:
            # Limit source code to first few lines
            source_lines = element.source_code.split('\n')[:3]
            query_parts.append(f"source: {' '.join(source_lines)}")
        
        # Add docstring if available
        if element.docstring:
            # Limit docstring to first sentence
            docstring_sentence = element.docstring.split('.')[0]
            query_parts.append(f"documented as: {docstring_sentence}")
        
        return " ".join(query_parts)
    
    def _create_file_query(self, file_analysis: CodeAnalysis) -> str:
        """Create query text for entire file analysis."""
        query_parts = []
        
        # Add file characteristics
        query_parts.append(f"Python file with {file_analysis.total_lines} lines")
        
        # Add complexity information
        if file_analysis.complexity_score > 20:
            query_parts.append("high complexity")
        elif file_analysis.complexity_score > 10:
            query_parts.append("medium complexity")
        else:
            query_parts.append("low complexity")
        
        # Add element counts
        element_counts = {}
        for element in file_analysis.elements:
            element_counts[element.element_type] = element_counts.get(element.element_type, 0) + 1
        
        if element_counts:
            count_descriptions = []
            for elem_type, count in element_counts.items():
                count_descriptions.append(f"{count} {elem_type}{'s' if count > 1 else ''}")
            query_parts.append(f"containing {', '.join(count_descriptions)}")
        
        # Add import information
        if file_analysis.imports:
            # Mention key imports
            key_imports = [imp for imp in file_analysis.imports[:5]]  # First 5 imports
            query_parts.append(f"importing {', '.join(key_imports)}")
        
        return " ".join(query_parts)
    
    def _generate_analysis_prompt(
        self,
        file_analysis: CodeAnalysis,
        code_element: Optional[CodeElement],
        relevant_rules: List[RelevantRule]
    ) -> str:
        """Generate the analysis prompt for the LLM."""
        
        # Base prompt template
        prompt_template = """You are an expert code reviewer analyzing Python code for compliance with coding standards and best practices.

**TASK:**
Analyze the provided code and identify any violations of the given coding standards. For each violation found:
1. Specify the exact line number and column (if applicable)
2. Quote the problematic code
3. Explain why it violates the standard
4. Provide a specific fix with the corrected code
5. Assign a confidence score (0.0-1.0)

**RELEVANT CODING STANDARDS:**
{relevant_rules}

**CODE TO ANALYZE:**

File: {file_path}
Total Lines: {total_lines}
Complexity Score: {complexity_score}

{code_section}

**OUTPUT FORMAT:**
Provide your analysis as a JSON object with the following structure:
{{
    "violations": [
        {{
            "rule_id": "rule_identifier",
            "line_number": 10,
            "column_number": 5,
            "violation_description": "Detailed description of the violation",
            "problematic_code": "exact code that violates the standard",
            "suggested_fix": "corrected code following the standard",
            "severity": "high|medium|low",
            "confidence_score": 0.85
        }}
    ],
    "summary": {{
        "total_violations": 2,
        "high_severity": 1,
        "medium_severity": 1,
        "low_severity": 0,
        "overall_assessment": "Brief overall assessment of code quality"
    }}
}}

**ANALYSIS:**"""
        
        # Format relevant rules
        rules_text = ""
        for i, rule in enumerate(relevant_rules, 1):
            rules_text += f"\n{i}. **{rule.rule_id}** ({rule.severity} severity, {rule.similarity:.2f} relevance)\n"
            rules_text += f"   Title: {rule.title}\n"
            rules_text += f"   Description: {rule.description}\n"
        
        if not rules_text:
            rules_text = "\nNo specific coding standards found. Apply general Python best practices."
        
        # Format code section
        if code_element:
            code_section = f"""
**Specific Element Analysis:**
Type: {code_element.element_type}
Name: {code_element.name}
Line: {code_element.line_number}
{f'Arguments: {", ".join(code_element.arguments)}' if code_element.arguments else ''}
{f'Decorators: {", ".join(code_element.decorators)}' if code_element.decorators else ''}

**Code:**
```python
{code_element.source_code or 'Code not available'}
```
"""
        else:
            # Show key elements of the file
            code_section = f"""
**File Elements:**
"""
            for element in file_analysis.elements[:10]:  # Show first 10 elements
                code_section += f"- {element.element_type}: {element.name} (line {element.line_number})\n"
            
            if len(file_analysis.elements) > 10:
                code_section += f"... and {len(file_analysis.elements) - 10} more elements\n"
            
            code_section += f"""
**Imports:**
{', '.join(file_analysis.imports[:10]) if file_analysis.imports else 'None'}

**Note:** Full file analysis requested. Analyze the overall structure and patterns.
"""
        
        # Fill the prompt template
        prompt = prompt_template.format(
            relevant_rules=rules_text,
            file_path=file_analysis.file_path,
            total_lines=file_analysis.total_lines,
            complexity_score=file_analysis.complexity_score,
            code_section=code_section
        )
        
        return prompt
    
    async def close(self):
        """Close the RAG system."""
        try:
            await self.vector_db.close()
            print("✅ RAG System closed")
            
        except Exception as e:
            logger.error(f"Error closing RAG system: {e}")


# Global RAG system instance
rag_system = RAGSystem()

