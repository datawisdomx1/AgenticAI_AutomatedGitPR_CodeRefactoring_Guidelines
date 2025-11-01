#!/usr/bin/env python3
"""
Enterprise Code Refactor - Main Application
CLI interface for the enterprise code refactoring system.
"""

import asyncio
import logging
import sys
import json
from typing import Optional
from pathlib import Path
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.logging import RichHandler
from datetime import datetime

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config.settings import settings
from src.database.vector_db_manager import vector_db_manager
from src.analysis.rag_system import rag_system
from src.agents.master_orchestrator import master_orchestrator
from src.diff.diff_generator import diff_generator
from src.git.git_manager import GitManager

# Initialize console for rich output
console = Console()


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)]
    )


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to configuration file')
def cli(verbose: bool, config: Optional[str]):
    """Enterprise Code Refactor - AI-powered code analysis and refactoring tool."""
    setup_logging(verbose)
    
    if config:
        # Load custom configuration
        console.print(f"📁 Loading configuration from: {config}")
        # In a real implementation, you'd load the config file here
    
    console.print("🚀 [bold blue]Enterprise Code Refactor[/bold blue] - Version 1.0.0")


@cli.command()
@click.option('--file', '-f', type=click.Path(exists=True), help='Standards file path')
@click.option('--url', '-u', type=str, help='Standards file URL')
@click.option('--format', '-fmt', type=click.Choice(['json', 'csv', 'txt']), default='json', help='File format')
def load_standards(file: Optional[str], url: Optional[str], format: str):
    """Load code standards into the vector database."""
    
    async def _load_standards():
        try:
            console.print("🔧 Initializing vector database...")
            await vector_db_manager.initialize()
            
            if file:
                console.print(f"📁 Loading standards from file: {file}")
                count = await vector_db_manager.load_standards_from_file(file)
                console.print(f"✅ Loaded {count} standards from file")
            
            elif url:
                console.print(f"🌐 Loading standards from URL: {url}")
                count = await vector_db_manager.load_standards_from_url(url)
                console.print(f"✅ Loaded {count} standards from URL")
            
            else:
                console.print("❌ Please provide either --file or --url option")
                return
            
            # Show summary
            total_count = await vector_db_manager.get_standards_count()
            categories = await vector_db_manager.get_all_categories()
            
            table = Table(title="Standards Database Summary")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")
            
            table.add_row("Total Standards", str(total_count))
            table.add_row("Categories", ", ".join(categories))
            
            console.print(table)
            
        except Exception as e:
            console.print(f"❌ Error loading standards: {e}")
            raise
        finally:
            await vector_db_manager.close()
    
    asyncio.run(_load_standards())


@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--recursive', '-r', is_flag=True, default=True, help='Recursive search')
@click.option('--session-name', '-s', type=str, help='Custom session name')
@click.option('--output-dir', '-o', type=click.Path(), help='Output directory for results')
@click.option('--create-git-branch', is_flag=True, help='Create Git branch for changes')
@click.option('--create-pr', is_flag=True, help='Create pull request after analysis')
def analyze_folder(
    path: str,
    recursive: bool,
    session_name: Optional[str],
    output_dir: Optional[str],
    create_git_branch: bool,
    create_pr: bool
):
    """Analyze Python files in a folder."""
    
    async def _analyze_folder():
        git_manager = None
        
        try:
            console.print(f"📁 Starting folder analysis: {path}")
            
            # Initialize systems
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                init_task = progress.add_task("Initializing systems...", total=None)
                
                await master_orchestrator.initialize()
                await rag_system.initialize()
                
                progress.update(init_task, description="✅ Systems initialized")
                progress.stop()
            
            # Initialize Git if requested
            if create_git_branch or create_pr:
                git_manager = GitManager()
                if git_manager.initialize_repo(path):
                    console.print("✅ Git repository initialized")
                else:
                    console.print("❌ Failed to initialize Git repository")
                    git_manager = None
            
            # Run analysis
            session = await master_orchestrator.analyze_folder(
                folder_path=path,
                session_name=session_name,
                recursive=recursive
            )
            
            # Generate diffs
            output_path = output_dir or settings.app.output_dir
            diff_files = diff_generator.generate_diffs(
                session.worker_results,
                output_path
            )
            
            # Create combined diff
            if diff_files:
                combined_diff_path = Path(output_path) / f"combined_diff_{session.id[:8]}.diff"
                diff_generator.create_combined_diff(diff_files, str(combined_diff_path))
                
                # Create summary report
                summary_path = Path(output_path) / f"summary_{session.id[:8]}.json"
                summary = diff_generator.create_summary_report(diff_files, str(summary_path))
                
                # Display summary
                _display_analysis_summary(session, summary)
                
                # Git operations
                if git_manager and diff_files:
                    if create_git_branch:
                        branch_name = git_manager.create_refactor_branch(session.id)
                        console.print(f"🌿 Created branch: {branch_name}")
                        
                        # Apply diffs
                        for diff_file in diff_files:
                            if git_manager.apply_diff_file(diff_file.file_path):
                                console.print(f"✅ Applied diff: {diff_file.file_path}")
                        
                        # Commit changes
                        commit_hash = git_manager.commit_changes(session.id)
                        if commit_hash:
                            console.print(f"📝 Committed changes: {commit_hash[:8]}")
                        
                        # Create PR
                        if create_pr:
                            pr_url = git_manager.create_pull_request(
                                session.id,
                                f"Code refactoring - Session {session.id[:8]}",
                                f"Automated code refactoring based on standards analysis.\n\nSession: {session.id}\nFiles modified: {len(diff_files)}\nTotal fixes: {summary['summary']['total_fixes_applied']}"
                            )
                            
                            if pr_url:
                                console.print(f"🔀 Pull request created: {pr_url}")
            
            else:
                console.print("ℹ️  No violations found or no diffs generated")
            
        except Exception as e:
            console.print(f"❌ Analysis failed: {e}")
            raise
        finally:
            if git_manager:
                git_manager.cleanup()
            await master_orchestrator.close()
            await rag_system.close()
    
    asyncio.run(_analyze_folder())


@cli.command()
@click.argument('repo_url', type=str)
@click.option('--branch', '-b', type=str, default='main', help='Git branch to analyze')
@click.option('--session-name', '-s', type=str, help='Custom session name')
@click.option('--output-dir', '-o', type=click.Path(), help='Output directory for results')
@click.option('--create-pr', is_flag=True, help='Create pull request after analysis')
def analyze_repo(
    repo_url: str,
    branch: str,
    session_name: Optional[str],
    output_dir: Optional[str],
    create_pr: bool
):
    """Analyze Python files in a Git repository."""
    
    async def _analyze_repo():
        try:
            console.print(f"🌐 Starting repository analysis: {repo_url}")
            
            # Initialize systems
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                init_task = progress.add_task("Initializing systems...", total=None)
                
                await master_orchestrator.initialize()
                await rag_system.initialize()
                
                progress.update(init_task, description="✅ Systems initialized")
                progress.stop()
            
            # Run analysis
            session = await master_orchestrator.analyze_git_repo(
                repo_url=repo_url,
                branch=branch,
                session_name=session_name
            )
            
            # Generate diffs
            output_path = output_dir or settings.app.output_dir
            diff_files = diff_generator.generate_diffs(
                session.worker_results,
                output_path
            )
            
            # Create combined diff and summary
            if diff_files:
                combined_diff_path = Path(output_path) / f"combined_diff_{session.id[:8]}.diff"
                diff_generator.create_combined_diff(diff_files, str(combined_diff_path))
                
                summary_path = Path(output_path) / f"summary_{session.id[:8]}.json"
                summary = diff_generator.create_summary_report(diff_files, str(summary_path))
                
                _display_analysis_summary(session, summary)
                
                if create_pr:
                    console.print("ℹ️  Pull request creation for remote repos is not yet implemented")
                    console.print(f"📄 Use the generated diff file: {combined_diff_path}")
            
            else:
                console.print("ℹ️  No violations found or no diffs generated")
            
        except Exception as e:
            console.print(f"❌ Repository analysis failed: {e}")
            raise
        finally:
            await master_orchestrator.close()
            await rag_system.close()
    
    asyncio.run(_analyze_repo())


@cli.command()
@click.argument('session_id', type=str)
def show_results(session_id: str):
    """Show results of a previous analysis session."""
    
    async def _show_results():
        try:
            await master_orchestrator.initialize()
            
            session = await master_orchestrator.get_session_results(session_id)
            
            if not session:
                console.print(f"❌ Session not found: {session_id}")
                return
            
            # Display session info
            table = Table(title=f"Analysis Session: {session.name}")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="magenta")
            
            table.add_row("Session ID", session.id)
            table.add_row("Source Type", session.source_type)
            table.add_row("Source Path", session.source_path)
            table.add_row("Status", session.status)
            table.add_row("Total Files", str(session.total_files))
            table.add_row("Processed Files", str(session.processed_files))
            table.add_row("Failed Files", str(session.failed_files))
            table.add_row("Start Time", session.start_time.strftime("%Y-%m-%d %H:%M:%S"))
            
            if session.end_time:
                duration = (session.end_time - session.start_time).total_seconds()
                table.add_row("Duration", f"{duration:.2f} seconds")
            
            console.print(table)
            
            # Display file results
            if session.worker_results:
                file_table = Table(title="File Analysis Results")
                file_table.add_column("File", style="cyan")
                file_table.add_column("Status", style="magenta")
                file_table.add_column("Violations", style="yellow")
                
                for result in session.worker_results:
                    status = "✅ Success" if result.success else "❌ Failed"
                    violations = str(len(result.violations)) if result.success else "N/A"
                    file_table.add_row(result.file_path, status, violations)
                
                console.print(file_table)
            
        except Exception as e:
            console.print(f"❌ Failed to show results: {e}")
            raise
        finally:
            await master_orchestrator.close()
    
    asyncio.run(_show_results())


@cli.command()
def list_sessions():
    """List all analysis sessions."""
    
    async def _list_sessions():
        try:
            await vector_db_manager.initialize()
            
            async with vector_db_manager.session_factory() as db_session:
                from sqlalchemy import text
                
                query = text("""
                    SELECT id, session_name, source_type, source_path, status, 
                           total_files, processed_files, failed_files, created_at
                    FROM code_refactor.analysis_sessions 
                    ORDER BY created_at DESC
                    LIMIT 20
                """)
                
                result = await db_session.execute(query)
                sessions = result.fetchall()
                
                if not sessions:
                    console.print("ℹ️  No analysis sessions found")
                    return
                
                table = Table(title="Recent Analysis Sessions")
                table.add_column("ID", style="cyan")
                table.add_column("Name", style="magenta")
                table.add_column("Type", style="yellow")
                table.add_column("Status", style="green")
                table.add_column("Files", style="blue")
                table.add_column("Created", style="dim")
                
                for session in sessions:
                    short_id = session.id[:8]
                    files_info = f"{session.processed_files}/{session.total_files}"
                    if session.failed_files > 0:
                        files_info += f" ({session.failed_files} failed)"
                    
                    created_str = session.created_at.strftime("%Y-%m-%d %H:%M")
                    
                    table.add_row(
                        short_id,
                        session.session_name,
                        session.source_type,
                        session.status,
                        files_info,
                        created_str
                    )
                
                console.print(table)
            
        except Exception as e:
            console.print(f"❌ Failed to list sessions: {e}")
            raise
        finally:
            await vector_db_manager.close()
    
    asyncio.run(_list_sessions())


@cli.command()
def status():
    """Show system status and statistics."""
    
    async def _status():
        try:
            console.print("🔍 Checking system status...")
            
            await vector_db_manager.initialize()
            
            # Get database statistics
            standards_count = await vector_db_manager.get_standards_count()
            categories = await vector_db_manager.get_all_categories()
            
            # Get session statistics
            async with vector_db_manager.session_factory() as db_session:
                from sqlalchemy import text
                
                session_query = text("""
                    SELECT status, COUNT(*) as count
                    FROM code_refactor.analysis_sessions 
                    GROUP BY status
                """)
                
                session_result = await db_session.execute(session_query)
                session_stats = dict(session_result.fetchall())
            
            # Display status
            table = Table(title="System Status")
            table.add_column("Component", style="cyan")
            table.add_column("Status", style="magenta")
            table.add_column("Details", style="yellow")
            
            table.add_row("Database", "✅ Connected", f"PostgreSQL with pgvector")
            table.add_row("Vector DB", "✅ Ready", f"{standards_count} standards loaded")
            table.add_row("Categories", "📊 Available", f"{len(categories)} categories")
            table.add_row("LLM Provider", "🤖 Configured", settings.llm.default_provider)
            table.add_row("Sessions", "📈 History", f"{sum(session_stats.values())} total")
            
            console.print(table)
            
            # Show categories
            if categories:
                console.print(f"\n📂 Available categories: {', '.join(categories)}")
            
            # Show session breakdown
            if session_stats:
                console.print(f"\n📊 Session breakdown: {dict(session_stats)}")
            
        except Exception as e:
            console.print(f"❌ Failed to get system status: {e}")
            raise
        finally:
            await vector_db_manager.close()
    
    asyncio.run(_status())


def _display_analysis_summary(session, summary: dict):
    """Display analysis summary in a formatted table."""
    
    # Main summary table
    table = Table(title="Analysis Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    
    summary_data = summary['summary']
    table.add_row("Files Modified", str(summary_data['total_files_modified']))
    table.add_row("Total Fixes", str(summary_data['total_fixes_applied']))
    table.add_row("Average Confidence", f"{summary_data['average_confidence_score']:.3f}")
    table.add_row("Processing Time", f"{(session.end_time - session.start_time).total_seconds():.2f}s")
    
    console.print(table)
    
    # Top violations table
    if summary_data['most_common_violations']:
        violations_table = Table(title="Most Common Violations")
        violations_table.add_column("Rule ID", style="cyan")
        violations_table.add_column("Count", style="magenta")
        
        for rule_id, count in list(summary_data['most_common_violations'].items())[:5]:
            violations_table.add_row(rule_id, str(count))
        
        console.print(violations_table)


if __name__ == "__main__":
    cli()

