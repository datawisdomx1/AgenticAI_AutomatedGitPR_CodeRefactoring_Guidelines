"""
Worker agents for parallel code analysis using LangGraph and LangChain.
"""

import asyncio
import logging
import json
import uuid
from typing import Dict, List, Any, Optional, TypedDict
from datetime import datetime
from dataclasses import dataclass, asdict

from langchain.llms.base import BaseLLM
from langchain_openai import ChatOpenAI
from langchain_community.llms import Anthropic
from langgraph.graph import StateGraph, END
# from langgraph.checkpoint.sqlite import SqliteSaver  # Not available in langgraph 0.6.5

from ..analysis.code_parser import CodeAnalysis, code_parser
from ..analysis.rag_system import RAGContext, rag_system
from ..database.vector_db_manager import vector_db_manager
from ..config.settings import settings

logger = logging.getLogger(__name__)


class WorkerState(TypedDict):
    """State for worker agent."""
    worker_id: str
    file_path: str
    analysis_status: str
    code_analysis: Optional[Dict[str, Any]]
    rag_context: Optional[Dict[str, Any]]
    llm_response: Optional[str]
    violations: Optional[List[Dict[str, Any]]]
    error_message: Optional[str]
    processing_time: Optional[float]


@dataclass
class WorkerResult:
    """Result from worker agent processing."""
    worker_id: str
    file_path: str
    success: bool
    violations: List[Dict[str, Any]]
    processing_time: float
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class WorkerAgent:
    """Individual worker agent for analyzing a single file."""
    
    def __init__(self, worker_id: str, session_id: str):
        self.worker_id = worker_id
        self.session_id = session_id
        self.llm = None
        self.graph = None
        self.checkpointer = None
        
    async def initialize(self):
        """Initialize the worker agent."""
        try:
            print(f"🤖 Worker {self.worker_id}: Initializing...")
            
            # Initialize LLM
            self.llm = self._create_llm()
            
            # Initialize checkpointer for state persistence
            # self.checkpointer = SqliteSaver.from_conn_string(":memory:")  # Not available in langgraph 0.6.5
            self.checkpointer = None
            
            # Create the workflow graph
            self.graph = self._create_workflow()
            
            print(f"✅ Worker {self.worker_id}: Initialized successfully")
            
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Failed to initialize: {e}")
            raise
    
    def _create_llm(self) -> BaseLLM:
        """Create LLM instance based on configuration."""
        llm_settings = settings.llm
        
        if llm_settings.default_provider == "openai":
            if not llm_settings.openai_api_key:
                raise ValueError("OpenAI API key not provided")
            
            return ChatOpenAI(
                openai_api_key=llm_settings.openai_api_key,
                model_name=llm_settings.default_model,
                temperature=llm_settings.temperature,
                max_tokens=llm_settings.max_tokens,
                timeout=llm_settings.timeout
            )
            
        elif llm_settings.default_provider == "anthropic":
            if not llm_settings.anthropic_api_key:
                raise ValueError("Anthropic API key not provided")
            
            return Anthropic(
                anthropic_api_key=llm_settings.anthropic_api_key,
                model=llm_settings.default_model,
                temperature=llm_settings.temperature,
                max_tokens_to_sample=llm_settings.max_tokens,
                timeout=llm_settings.timeout
            )
            
        else:
            raise ValueError(f"Unsupported LLM provider: {llm_settings.default_provider}")
    
    def _create_workflow(self) -> StateGraph:
        """Create the workflow graph for code analysis."""
        workflow = StateGraph(WorkerState)
        
        # Add nodes
        workflow.add_node("parse_code", self._parse_code_node)
        workflow.add_node("generate_context", self._generate_context_node)
        workflow.add_node("analyze_with_llm", self._analyze_with_llm_node)
        workflow.add_node("process_results", self._process_results_node)
        workflow.add_node("handle_error", self._handle_error_node)
        
        # Set entry point
        workflow.set_entry_point("parse_code")
        
        # Add edges
        workflow.add_edge("parse_code", "generate_context")
        workflow.add_edge("generate_context", "analyze_with_llm")
        workflow.add_edge("analyze_with_llm", "process_results")
        workflow.add_edge("process_results", END)
        workflow.add_edge("handle_error", END)
        
        # Add conditional edges for error handling
        workflow.add_conditional_edges(
            "parse_code",
            lambda state: "generate_context" if state.get("error_message") is None else "handle_error"
        )
        
        workflow.add_conditional_edges(
            "generate_context",
            lambda state: "analyze_with_llm" if state.get("error_message") is None else "handle_error"
        )
        
        workflow.add_conditional_edges(
            "analyze_with_llm",
            lambda state: "process_results" if state.get("error_message") is None else "handle_error"
        )
        
        return workflow.compile(checkpointer=self.checkpointer)
    
    async def _parse_code_node(self, state: WorkerState) -> WorkerState:
        """Parse the code file using AST."""
        try:
            print(f"🔍 Worker {self.worker_id}: Parsing code file: {state['file_path']}")
            
            # Update status in database
            await self._update_file_status("analyzing")
            
            # Parse the file
            code_analysis = code_parser.parse_file(state["file_path"])
            
            # Store analysis in state
            state["code_analysis"] = code_analysis.to_dict()
            state["analysis_status"] = "parsed"
            
            print(f"✅ Worker {self.worker_id}: Code parsed successfully - {len(code_analysis.elements)} elements found")
            
        except Exception as e:
            error_msg = f"Failed to parse code: {str(e)}"
            print(f"❌ Worker {self.worker_id}: {error_msg}")
            state["error_message"] = error_msg
            state["analysis_status"] = "parse_failed"
        
        return state
    
    async def _generate_context_node(self, state: WorkerState) -> WorkerState:
        """Generate RAG context for analysis."""
        try:
            print(f"🧠 Worker {self.worker_id}: Generating RAG context...")
            
            # Convert dict back to CodeAnalysis object
            code_analysis_dict = state["code_analysis"]
            code_analysis = self._dict_to_code_analysis(code_analysis_dict)
            
            # Generate RAG context
            rag_context = await rag_system.generate_analysis_context(code_analysis)
            
            # Store context in state
            state["rag_context"] = rag_context.to_dict()
            state["analysis_status"] = "context_generated"
            
            print(f"✅ Worker {self.worker_id}: RAG context generated with {len(rag_context.relevant_rules)} relevant rules")
            
        except Exception as e:
            error_msg = f"Failed to generate context: {str(e)}"
            print(f"❌ Worker {self.worker_id}: {error_msg}")
            state["error_message"] = error_msg
            state["analysis_status"] = "context_failed"
        
        return state
    
    async def _analyze_with_llm_node(self, state: WorkerState) -> WorkerState:
        """Analyze code using LLM."""
        try:
            print(f"🤖 Worker {self.worker_id}: Analyzing with LLM...")
            
            # Get the analysis prompt
            rag_context_dict = state["rag_context"]
            analysis_prompt = rag_context_dict["analysis_prompt"]
            
            # Call LLM
            response = await self.llm.agenerate([analysis_prompt])
            llm_response = response.generations[0][0].text
            
            # Store response in state
            state["llm_response"] = llm_response
            state["analysis_status"] = "llm_analyzed"
            
            print(f"✅ Worker {self.worker_id}: LLM analysis completed")
            
        except Exception as e:
            error_msg = f"Failed LLM analysis: {str(e)}"
            print(f"❌ Worker {self.worker_id}: {error_msg}")
            state["error_message"] = error_msg
            state["analysis_status"] = "llm_failed"
        
        return state
    
    async def _process_results_node(self, state: WorkerState) -> WorkerState:
        """Process LLM response and extract violations."""
        try:
            print(f"📊 Worker {self.worker_id}: Processing results...")
            
            # Parse LLM response
            llm_response = state["llm_response"]
            violations = self._parse_llm_response(llm_response)
            
            # Store violations in state
            state["violations"] = violations
            state["analysis_status"] = "completed"
            
            # Update database with results
            await self._store_violations(violations, state["file_path"])
            await self._update_file_status("completed", len(violations))
            
            print(f"✅ Worker {self.worker_id}: Found {len(violations)} violations")
            
        except Exception as e:
            error_msg = f"Failed to process results: {str(e)}"
            print(f"❌ Worker {self.worker_id}: {error_msg}")
            state["error_message"] = error_msg
            state["analysis_status"] = "processing_failed"
        
        return state
    
    async def _handle_error_node(self, state: WorkerState) -> WorkerState:
        """Handle errors in processing."""
        try:
            error_message = state.get("error_message", "Unknown error")
            print(f"❌ Worker {self.worker_id}: Handling error: {error_message}")
            
            # Update database with error status
            await self._update_file_status("failed", 0, error_message)
            
            # Set empty violations
            state["violations"] = []
            
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Error in error handler: {e}")
        
        return state
    
    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response to extract violations."""
        try:
            # Try to extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed_response = json.loads(json_str)
                
                if "violations" in parsed_response:
                    return parsed_response["violations"]
            
            # If JSON parsing fails, try to extract violations manually
            violations = []
            lines = response.split('\n')
            
            current_violation = {}
            for line in lines:
                line = line.strip()
                if line.startswith('- ') or line.startswith('* '):
                    if current_violation:
                        violations.append(current_violation)
                    current_violation = {
                        "rule_id": "manual_extract",
                        "violation_description": line[2:],
                        "severity": "medium",
                        "confidence_score": 0.7
                    }
            
            if current_violation:
                violations.append(current_violation)
            
            return violations
            
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return []
    
    def _dict_to_code_analysis(self, analysis_dict: Dict[str, Any]) -> CodeAnalysis:
        """Convert dictionary back to CodeAnalysis object."""
        from ..analysis.code_parser import CodeAnalysis, CodeElement
        
        elements = []
        for elem_dict in analysis_dict.get("elements", []):
            element = CodeElement(**elem_dict)
            elements.append(element)
        
        return CodeAnalysis(
            file_path=analysis_dict["file_path"],
            file_hash=analysis_dict["file_hash"],
            total_lines=analysis_dict["total_lines"],
            code_lines=analysis_dict["code_lines"],
            comment_lines=analysis_dict["comment_lines"],
            blank_lines=analysis_dict["blank_lines"],
            elements=elements,
            imports=analysis_dict["imports"],
            syntax_errors=analysis_dict["syntax_errors"],
            complexity_score=analysis_dict["complexity_score"]
        )
    
    async def _update_file_status(self, status: str, violations_count: int = 0, error_message: str = None):
        """Update file analysis status in database."""
        try:
            async with vector_db_manager.session_factory() as session:
                from sqlalchemy import text
                
                query = text("""
                    UPDATE code_refactor.file_analysis 
                    SET analysis_status = :status,
                        violations_found = :violations_count,
                        error_message = :error_message,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = :session_id AND file_path = :file_path
                """)
                
                await session.execute(
                    query,
                    {
                        "status": status,
                        "violations_count": violations_count,
                        "error_message": error_message,
                        "session_id": self.session_id,
                        "file_path": None  # Will be set when processing
                    }
                )
                
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to update file status: {e}")
    
    async def _store_violations(self, violations: List[Dict[str, Any]], file_path: str = None):
        """Store violations in database."""
        try:
            if not violations:
                return
                
            if not file_path and hasattr(self, 'current_file_path'):
                file_path = self.current_file_path
                
            if not file_path:
                logger.error("Cannot store violations: file_path not provided")
                return
                
            async with vector_db_manager.session_factory() as session:
                from sqlalchemy import text
                
                # First get the file_analysis_id
                query = text("""
                    SELECT id FROM code_refactor.file_analysis 
                    WHERE session_id = :session_id AND file_path = :file_path
                """)
                
                result = await session.execute(
                    query,
                    {"session_id": self.session_id, "file_path": file_path}
                )
                
                file_analysis_id = result.scalar()
                
                if not file_analysis_id:
                    return
                
                # Insert violations
                for violation in violations:
                    insert_query = text("""
                        INSERT INTO code_refactor.code_violations 
                        (file_analysis_id, rule_id, line_number, column_number, 
                         violation_description, severity, suggested_fix, confidence_score)
                        VALUES (:file_analysis_id, :rule_id, :line_number, :column_number,
                                :violation_description, :severity, :suggested_fix, :confidence_score)
                    """)
                    
                    await session.execute(
                        insert_query,
                        {
                            "file_analysis_id": file_analysis_id,
                            "rule_id": violation.get("rule_id", "unknown"),
                            "line_number": violation.get("line_number"),
                            "column_number": violation.get("column_number"),
                            "violation_description": violation.get("violation_description", ""),
                            "severity": violation.get("severity", "medium"),
                            "suggested_fix": violation.get("suggested_fix"),
                            "confidence_score": violation.get("confidence_score", 0.0)
                        }
                    )
                
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to store violations: {e}")
    
    async def process_file(self, file_path: str) -> WorkerResult:
        """Process a single file using direct function calls (bypassing LangGraph)."""
        start_time = datetime.now()
        violations = []
        error_message = None
        
        try:
            print(f"🚀 Worker {self.worker_id}: Starting analysis of {file_path}")
            
            # Step 1: Parse code
            print(f"🔍 Worker {self.worker_id}: Parsing code file: {file_path}")
            await self._update_file_status("analyzing")
            code_analysis = code_parser.parse_file(file_path)
            print(f"✅ Worker {self.worker_id}: Code parsed successfully - {len(code_analysis.elements)} elements found")
            
            # Step 2: Generate RAG context
            print(f"🧠 Worker {self.worker_id}: Generating RAG context...")
            rag_context = await rag_system.generate_analysis_context(code_analysis)
            print(f"✅ Worker {self.worker_id}: RAG context generated with {len(rag_context.relevant_rules)} relevant rules")
            
            # Step 3: Analyze with LLM
            print(f"🤖 Worker {self.worker_id}: Analyzing with LLM...")
            analysis_prompt = rag_context.analysis_prompt
            
            # Call LLM using invoke method (more compatible)
            try:
                llm_response = await self.llm.ainvoke(analysis_prompt)
                # Handle different response formats
                if hasattr(llm_response, 'content'):
                    llm_response_text = llm_response.content
                elif isinstance(llm_response, str):
                    llm_response_text = llm_response
                else:
                    llm_response_text = str(llm_response)
                    
                print(f"✅ Worker {self.worker_id}: LLM analysis completed")
                
                # Step 4: Parse results
                print(f"📊 Worker {self.worker_id}: Processing results...")
                violations = self._parse_llm_response(llm_response_text)
                
                # Store violations in database
                await self._store_violations(violations, file_path)
                await self._update_file_status("completed", len(violations))
                
                print(f"✅ Worker {self.worker_id}: Found {len(violations)} violations")
                
            except Exception as llm_error:
                logger.warning(f"LLM analysis failed: {llm_error}. Falling back to rule-based analysis...")
                # Fallback: use rule-based violations from RAG context
                violations = []
                for rule in rag_context.relevant_rules:
                    violations.append({
                        "rule_id": rule.rule_id,
                        "violation_description": f"Potential violation of: {rule.title}",
                        "severity": rule.severity,
                        "suggested_fix": rule.description,
                        "confidence_score": rule.similarity,
                        "line_number": None,
                        "column_number": None
                    })
                
                await self._store_violations(violations, file_path)
                await self._update_file_status("completed", len(violations))
                print(f"✅ Worker {self.worker_id}: Found {len(violations)} potential violations (rule-based)")
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Create result
            result = WorkerResult(
                worker_id=self.worker_id,
                file_path=file_path,
                success=True,
                violations=violations,
                processing_time=processing_time,
                error_message=None
            )
            
            print(f"✅ Worker {self.worker_id}: Completed {file_path} in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"Worker processing failed: {str(e)}"
            logger.error(f"Worker {self.worker_id}: {error_msg}")
            
            # Update database with error
            try:
                await self._update_file_status("failed", 0, error_msg)
            except:
                pass
            
            return WorkerResult(
                worker_id=self.worker_id,
                file_path=file_path,
                success=False,
                violations=[],
                processing_time=processing_time,
                error_message=error_msg
            )

