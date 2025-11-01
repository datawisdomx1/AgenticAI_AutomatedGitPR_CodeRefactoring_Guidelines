"""
Master orchestrator agent that coordinates worker agents for parallel code analysis.
"""

import asyncio
import logging
import uuid
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
import git

from ..agents.worker_agent import WorkerAgent, WorkerResult
from ..analysis.code_parser import code_parser
from ..database.vector_db_manager import vector_db_manager
from ..config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class AnalysisSession:
    """Represents a code analysis session."""
    id: str
    name: str
    source_type: str  # 'folder' or 'git'
    source_path: str
    status: str
    total_files: int
    processed_files: int
    failed_files: int
    worker_results: List[WorkerResult]
    start_time: datetime
    end_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        result['worker_results'] = [result.to_dict() for result in self.worker_results]
        result['start_time'] = self.start_time.isoformat()
        result['end_time'] = self.end_time.isoformat() if self.end_time else None
        return result


class MasterOrchestrator:
    """Master orchestrator for coordinating multiple worker agents."""
    
    def __init__(self):
        self.settings = settings
        self.current_session: Optional[AnalysisSession] = None
        self.worker_agents: List[WorkerAgent] = []
        
    async def initialize(self):
        """Initialize the master orchestrator."""
        try:
            print("🎯 Initializing Master Orchestrator...")
            
            # Initialize database connection
            await vector_db_manager.initialize()
            
            print("✅ Master Orchestrator initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Master Orchestrator: {e}")
            raise
    
    async def analyze_folder(
        self,
        folder_path: str,
        session_name: Optional[str] = None,
        recursive: bool = True
    ) -> AnalysisSession:
        """Analyze all Python files in a folder."""
        try:
            print(f"📁 Starting folder analysis: {folder_path}")
            
            # Validate folder path
            folder = Path(folder_path)
            if not folder.exists():
                raise FileNotFoundError(f"Folder not found: {folder_path}")
            
            # Find Python files
            if recursive:
                python_files = list(folder.rglob("*.py"))
            else:
                python_files = list(folder.glob("*.py"))
            
            print(f"📄 Found {len(python_files)} Python files")
            
            if not python_files:
                raise ValueError("No Python files found in the specified folder")
            
            # Create analysis session
            session = await self._create_session(
                session_name or f"folder_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "folder",
                str(folder_path),
                len(python_files)
            )
            
            # Process files
            file_paths = [str(f) for f in python_files]
            await self._process_files(session, file_paths)
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to analyze folder {folder_path}: {e}")
            raise
    
    async def analyze_git_repo(
        self,
        repo_url: str,
        branch: str = "main",
        session_name: Optional[str] = None
    ) -> AnalysisSession:
        """Analyze Python files in a Git repository."""
        try:
            print(f"🌐 Starting Git repository analysis: {repo_url}")
            
            # Clone repository to temp directory
            temp_dir = Path(self.settings.app.temp_dir) / f"repo_{uuid.uuid4().hex[:8]}"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            print(f"📥 Cloning repository to: {temp_dir}")
            repo = git.Repo.clone_from(repo_url, temp_dir)
            
            # Checkout specified branch
            if branch != "main" and branch in [ref.name.split('/')[-1] for ref in repo.refs]:
                repo.git.checkout(branch)
                print(f"🔄 Switched to branch: {branch}")
            
            # Find Python files
            python_files = list(temp_dir.rglob("*.py"))
            print(f"📄 Found {len(python_files)} Python files")
            
            if not python_files:
                raise ValueError("No Python files found in the repository")
            
            # Create analysis session
            session = await self._create_session(
                session_name or f"git_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "git",
                repo_url,
                len(python_files)
            )
            
            # Process files
            file_paths = [str(f) for f in python_files]
            await self._process_files(session, file_paths)
            
            # Store git operation
            await self._store_git_operation(session.id, "clone", repo_url, branch)
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to analyze Git repository {repo_url}: {e}")
            raise
        finally:
            # Clean up temp directory
            if 'temp_dir' in locals() and temp_dir.exists():
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                    print(f"🧹 Cleaned up temp directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp directory: {e}")
    
    async def _create_session(
        self,
        session_name: str,
        source_type: str,
        source_path: str,
        total_files: int
    ) -> AnalysisSession:
        """Create a new analysis session."""
        try:
            session_id = str(uuid.uuid4())
            
            # Store session in database
            async with vector_db_manager.session_factory() as db_session:
                from sqlalchemy import text
                
                query = text("""
                    INSERT INTO code_refactor.analysis_sessions 
                    (id, session_name, source_type, source_path, status, total_files, processed_files, failed_files)
                    VALUES (:id, :session_name, :source_type, :source_path, :status, :total_files, :processed_files, :failed_files)
                """)
                
                await db_session.execute(
                    query,
                    {
                        "id": session_id,
                        "session_name": session_name,
                        "source_type": source_type,
                        "source_path": source_path,
                        "status": "in_progress",
                        "total_files": total_files,
                        "processed_files": 0,
                        "failed_files": 0
                    }
                )
                
                await db_session.commit()
            
            # Create session object
            session = AnalysisSession(
                id=session_id,
                name=session_name,
                source_type=source_type,
                source_path=source_path,
                status="in_progress",
                total_files=total_files,
                processed_files=0,
                failed_files=0,
                worker_results=[],
                start_time=datetime.now()
            )
            
            self.current_session = session
            print(f"📋 Created analysis session: {session_name} ({session_id})")
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    async def _process_files(self, session: AnalysisSession, file_paths: List[str]):
        """Process files using worker agents in parallel."""
        try:
            print(f"🚀 Starting parallel processing of {len(file_paths)} files")
            print(f"👥 Using {self.settings.app.max_workers} worker agents")
            
            # Create file analysis records in database
            await self._create_file_analysis_records(session.id, file_paths)
            
            # Create worker agents
            workers = []
            for i in range(self.settings.app.max_workers):
                worker_id = f"worker_{i+1:02d}"
                worker = WorkerAgent(worker_id, session.id)
                await worker.initialize()
                workers.append(worker)
                print(f"🤖 Created worker: {worker_id}")
            
            # Process files in batches
            batch_size = self.settings.app.batch_size
            all_results = []
            
            for i in range(0, len(file_paths), batch_size):
                batch_files = file_paths[i:i + batch_size]
                print(f"📦 Processing batch {i//batch_size + 1}: {len(batch_files)} files")
                
                # Create tasks for this batch
                tasks = []
                for j, file_path in enumerate(batch_files):
                    worker_idx = j % len(workers)
                    worker = workers[worker_idx]
                    task = asyncio.create_task(worker.process_file(file_path))
                    tasks.append(task)
                
                # Wait for batch completion
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process batch results
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error(f"Worker task failed: {result}")
                        session.failed_files += 1
                    else:
                        all_results.append(result)
                        if result.success:
                            session.processed_files += 1
                        else:
                            session.failed_files += 1
                
                # Update session progress
                await self._update_session_progress(session)
                
                print(f"✅ Batch {i//batch_size + 1} completed: {session.processed_files}/{session.total_files} files processed")
            
            # Finalize session
            session.worker_results = all_results
            session.status = "completed"
            session.end_time = datetime.now()
            
            await self._update_session_status(session, "completed")
            
            # Generate summary
            total_violations = sum(len(result.violations) for result in all_results if result.success)
            processing_time = (session.end_time - session.start_time).total_seconds()
            
            print(f"""
🎉 Analysis completed successfully!
📊 Summary:
   - Total files: {session.total_files}
   - Processed: {session.processed_files}
   - Failed: {session.failed_files}
   - Total violations: {total_violations}
   - Processing time: {processing_time:.2f} seconds
            """)
            
        except Exception as e:
            logger.error(f"Failed to process files: {e}")
            session.status = "failed"
            session.end_time = datetime.now()
            await self._update_session_status(session, "failed")
            raise
    
    async def _create_file_analysis_records(self, session_id: str, file_paths: List[str]):
        """Create file analysis records in database."""
        try:
            async with vector_db_manager.session_factory() as db_session:
                from sqlalchemy import text
                
                for file_path in file_paths:
                    # Calculate file hash
                    import hashlib
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        file_hash = hashlib.sha256(content.encode()).hexdigest()
                    except Exception:
                        file_hash = None
                    
                    query = text("""
                        INSERT INTO code_refactor.file_analysis 
                        (session_id, file_path, file_hash, analysis_status)
                        VALUES (:session_id, :file_path, :file_hash, :analysis_status)
                    """)
                    
                    await db_session.execute(
                        query,
                        {
                            "session_id": session_id,
                            "file_path": file_path,
                            "file_hash": file_hash,
                            "analysis_status": "pending"
                        }
                    )
                
                await db_session.commit()
                
        except Exception as e:
            logger.error(f"Failed to create file analysis records: {e}")
            raise
    
    async def _update_session_progress(self, session: AnalysisSession):
        """Update session progress in database."""
        try:
            async with vector_db_manager.session_factory() as db_session:
                from sqlalchemy import text
                
                query = text("""
                    UPDATE code_refactor.analysis_sessions 
                    SET processed_files = :processed_files,
                        failed_files = :failed_files,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :session_id
                """)
                
                await db_session.execute(
                    query,
                    {
                        "processed_files": session.processed_files,
                        "failed_files": session.failed_files,
                        "session_id": session.id
                    }
                )
                
                await db_session.commit()
                
        except Exception as e:
            logger.error(f"Failed to update session progress: {e}")
    
    async def _update_session_status(self, session: AnalysisSession, status: str):
        """Update session status in database."""
        try:
            async with vector_db_manager.session_factory() as db_session:
                from sqlalchemy import text
                
                query = text("""
                    UPDATE code_refactor.analysis_sessions 
                    SET status = :status,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :session_id
                """)
                
                await db_session.execute(
                    query,
                    {"status": status, "session_id": session.id}
                )
                
                await db_session.commit()
                
        except Exception as e:
            logger.error(f"Failed to update session status: {e}")
    
    async def _store_git_operation(
        self,
        session_id: str,
        operation_type: str,
        repo_url: str,
        branch: str
    ):
        """Store git operation in database."""
        try:
            async with vector_db_manager.session_factory() as db_session:
                from sqlalchemy import text
                
                query = text("""
                    INSERT INTO code_refactor.git_operations 
                    (session_id, operation_type, metadata, status)
                    VALUES (:session_id, :operation_type, :metadata, :status)
                """)
                
                metadata = {
                    "repo_url": repo_url,
                    "branch": branch
                }
                
                await db_session.execute(
                    query,
                    {
                        "session_id": session_id,
                        "operation_type": operation_type,
                        "metadata": metadata,
                        "status": "completed"
                    }
                )
                
                await db_session.commit()
                
        except Exception as e:
            logger.error(f"Failed to store git operation: {e}")
    
    async def get_session_results(self, session_id: str) -> Optional[AnalysisSession]:
        """Get analysis session results."""
        try:
            async with vector_db_manager.session_factory() as db_session:
                from sqlalchemy import text
                
                # Get session info
                session_query = text("""
                    SELECT * FROM code_refactor.analysis_sessions 
                    WHERE id = :session_id
                """)
                
                session_result = await db_session.execute(
                    session_query,
                    {"session_id": session_id}
                )
                
                session_row = session_result.fetchone()
                if not session_row:
                    return None
                
                # Get file analysis results
                files_query = text("""
                    SELECT fa.*, COUNT(cv.id) as violation_count
                    FROM code_refactor.file_analysis fa
                    LEFT JOIN code_refactor.code_violations cv ON fa.id = cv.file_analysis_id
                    WHERE fa.session_id = :session_id
                    GROUP BY fa.id
                    ORDER BY fa.created_at
                """)
                
                files_result = await db_session.execute(
                    files_query,
                    {"session_id": session_id}
                )
                
                # Create worker results
                worker_results = []
                for file_row in files_result:
                    result = WorkerResult(
                        worker_id=file_row.worker_agent_id or "unknown",
                        file_path=file_row.file_path,
                        success=file_row.analysis_status == "completed",
                        violations=[],  # Simplified for now
                        processing_time=0.0,  # Would need to calculate
                        error_message=file_row.error_message
                    )
                    worker_results.append(result)
                
                # Create session object
                session = AnalysisSession(
                    id=session_row.id,
                    name=session_row.session_name,
                    source_type=session_row.source_type,
                    source_path=session_row.source_path,
                    status=session_row.status,
                    total_files=session_row.total_files,
                    processed_files=session_row.processed_files,
                    failed_files=session_row.failed_files,
                    worker_results=worker_results,
                    start_time=session_row.created_at,
                    end_time=session_row.updated_at
                )
                
                return session
                
        except Exception as e:
            logger.error(f"Failed to get session results: {e}")
            return None
    
    async def close(self):
        """Close the master orchestrator."""
        try:
            await vector_db_manager.close()
            print("✅ Master Orchestrator closed")
            
        except Exception as e:
            logger.error(f"Error closing Master Orchestrator: {e}")


# Global orchestrator instance
master_orchestrator = MasterOrchestrator()

