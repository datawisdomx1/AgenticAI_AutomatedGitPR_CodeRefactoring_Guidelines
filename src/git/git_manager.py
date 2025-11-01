"""
Git integration for branch creation, diff generation, and pull request management.
"""

import os
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import git
from git import Repo
import requests

from ..config.settings import settings
from ..database.vector_db_manager import vector_db_manager

logger = logging.getLogger(__name__)


class GitManager:
    """Manages Git operations for code refactoring."""
    
    def __init__(self):
        self.settings = settings
        self.repo: Optional[Repo] = None
        self.original_branch: Optional[str] = None
        self.refactor_branch: Optional[str] = None
        
    def initialize_repo(self, repo_path: str) -> bool:
        """Initialize Git repository."""
        try:
            print(f"🔧 Initializing Git repository: {repo_path}")
            
            if not Path(repo_path).exists():
                raise FileNotFoundError(f"Repository path not found: {repo_path}")
            
            self.repo = Repo(repo_path)
            
            if self.repo.bare:
                raise ValueError("Cannot work with bare repository")
            
            self.original_branch = self.repo.active_branch.name
            print(f"📍 Current branch: {self.original_branch}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize repository: {e}")
            return False
    
    def create_refactor_branch(self, session_id: str, custom_name: Optional[str] = None) -> str:
        """Create a new branch for refactoring changes."""
        try:
            if not self.repo:
                raise RuntimeError("Repository not initialized")
            
            # Generate branch name
            if custom_name:
                branch_name = f"{self.settings.git.default_branch_prefix}-{custom_name}"
            else:
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                branch_name = f"{self.settings.git.default_branch_prefix}-{timestamp}"
            
            print(f"🌿 Creating refactor branch: {branch_name}")
            
            # Create new branch
            new_branch = self.repo.create_head(branch_name)
            new_branch.checkout()
            
            self.refactor_branch = branch_name
            
            # Store git operation in database
            asyncio.run(self._store_git_operation(
                session_id, "branch_create", branch_name=branch_name
            ))
            
            print(f"✅ Refactor branch created and checked out: {branch_name}")
            return branch_name
            
        except Exception as e:
            logger.error(f"Failed to create refactor branch: {e}")
            raise
    
    def apply_diff_file(self, diff_file_path: str) -> bool:
        """Apply a diff file to the current branch."""
        try:
            print(f"📝 Applying diff file: {diff_file_path}")
            
            if not self.repo:
                raise RuntimeError("Repository not initialized")
            
            if not Path(diff_file_path).exists():
                raise FileNotFoundError(f"Diff file not found: {diff_file_path}")
            
            # Read diff content
            with open(diff_file_path, 'r', encoding='utf-8') as f:
                diff_content = f.read()
            
            # Apply the diff using git apply
            try:
                self.repo.git.apply('--whitespace=fix', '--', diff_file_path)
                print(f"✅ Diff applied successfully: {diff_file_path}")
                return True
                
            except git.exc.GitCommandError as e:
                # If git apply fails, try manual application
                logger.warning(f"git apply failed, trying manual application: {e}")
                return self._apply_diff_manually(diff_content)
                
        except Exception as e:
            logger.error(f"Failed to apply diff file {diff_file_path}: {e}")
            return False
    
    def _apply_diff_manually(self, diff_content: str) -> bool:
        """Manually apply diff content."""
        try:
            print("🔧 Attempting manual diff application...")
            
            # Parse diff content to extract file changes
            changes = self._parse_diff_content(diff_content)
            
            for file_path, file_changes in changes.items():
                if self._apply_file_changes(file_path, file_changes):
                    print(f"✅ Applied changes to: {file_path}")
                else:
                    print(f"❌ Failed to apply changes to: {file_path}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Manual diff application failed: {e}")
            return False
    
    def _parse_diff_content(self, diff_content: str) -> Dict[str, List[Dict[str, Any]]]:
        """Parse diff content to extract file changes."""
        changes = {}
        current_file = None
        current_changes = []
        
        lines = diff_content.split('\n')
        
        for line in lines:
            if line.startswith('--- '):
                # Save previous file changes
                if current_file and current_changes:
                    changes[current_file] = current_changes
                    current_changes = []
                
                # Extract file path
                current_file = line[4:].strip()
                if current_file.startswith('a/'):
                    current_file = current_file[2:]
                    
            elif line.startswith('+++ '):
                # Update file path if needed
                file_path = line[4:].strip()
                if file_path.startswith('b/'):
                    current_file = file_path[2:]
                    
            elif line.startswith('@@'):
                # Parse hunk header
                hunk_info = line.split('@@')[1].strip()
                # Extract line numbers
                parts = hunk_info.split()
                if len(parts) >= 2:
                    old_range = parts[0][1:]  # Remove '-'
                    new_range = parts[1][1:]  # Remove '+'
                    
                    current_changes.append({
                        'type': 'hunk',
                        'old_range': old_range,
                        'new_range': new_range,
                        'lines': []
                    })
                    
            elif current_changes and (line.startswith('+') or line.startswith('-') or line.startswith(' ')):
                # Add line to current hunk
                current_changes[-1]['lines'].append(line)
        
        # Save last file changes
        if current_file and current_changes:
            changes[current_file] = current_changes
        
        return changes
    
    def _apply_file_changes(self, file_path: str, changes: List[Dict[str, Any]]) -> bool:
        """Apply changes to a specific file."""
        try:
            full_path = Path(self.repo.working_dir) / file_path
            
            if not full_path.exists():
                logger.warning(f"File not found for changes: {file_path}")
                return False
            
            # Read current file content
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Apply changes
            for change in changes:
                if change['type'] == 'hunk':
                    lines = self._apply_hunk(lines, change)
            
            # Write modified content back
            with open(full_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply changes to {file_path}: {e}")
            return False
    
    def _apply_hunk(self, lines: List[str], hunk: Dict[str, Any]) -> List[str]:
        """Apply a single hunk to file lines."""
        # This is a simplified implementation
        # In a production system, you'd want more robust diff application
        
        hunk_lines = hunk['lines']
        context_lines = []
        additions = []
        deletions = []
        
        for line in hunk_lines:
            if line.startswith(' '):
                context_lines.append(line[1:])
            elif line.startswith('+'):
                additions.append(line[1:])
            elif line.startswith('-'):
                deletions.append(line[1:])
        
        # Simple replacement strategy
        # This would need to be more sophisticated for complex diffs
        modified_lines = []
        for line in lines:
            if any(line.strip() == del_line.strip() for del_line in deletions):
                # Replace with additions
                modified_lines.extend(additions)
                additions = []  # Only add once
            else:
                modified_lines.append(line)
        
        return modified_lines
    
    def commit_changes(self, session_id: str, message: Optional[str] = None) -> str:
        """Commit the applied changes."""
        try:
            if not self.repo:
                raise RuntimeError("Repository not initialized")
            
            # Check if there are changes to commit
            if not self.repo.is_dirty():
                print("ℹ️  No changes to commit")
                return ""
            
            print("📝 Committing changes...")
            
            # Add all changes
            self.repo.git.add('--all')
            
            # Create commit message
            if not message:
                message = f"{self.settings.git.default_commit_message} - Session: {session_id}"
            
            # Commit changes
            commit = self.repo.index.commit(message)
            commit_hash = commit.hexsha
            
            # Store git operation in database
            asyncio.run(self._store_git_operation(
                session_id, "commit", commit_hash=commit_hash
            ))
            
            print(f"✅ Changes committed: {commit_hash[:8]}")
            return commit_hash
            
        except Exception as e:
            logger.error(f"Failed to commit changes: {e}")
            raise
    
    def create_pull_request(
        self,
        session_id: str,
        title: str,
        description: str,
        base_branch: Optional[str] = None
    ) -> Optional[str]:
        """Create a pull request for the refactored code."""
        try:
            if not self.repo or not self.refactor_branch:
                raise RuntimeError("Repository or refactor branch not available")
            
            print("🔀 Creating pull request...")
            
            # Get repository information
            repo_url = self._get_repo_url()
            if not repo_url:
                raise ValueError("Could not determine repository URL")
            
            # Determine if it's GitHub or GitLab
            if 'github.com' in repo_url:
                pr_url = self._create_github_pr(
                    repo_url, title, description, 
                    base_branch or self.original_branch,
                    self.refactor_branch
                )
            elif 'gitlab.com' in repo_url:
                pr_url = self._create_gitlab_mr(
                    repo_url, title, description,
                    base_branch or self.original_branch,
                    self.refactor_branch
                )
            else:
                logger.warning("Unsupported Git hosting service")
                return None
            
            if pr_url:
                # Store git operation in database
                asyncio.run(self._store_git_operation(
                    session_id, "pull_request", pull_request_url=pr_url
                ))
                
                print(f"✅ Pull request created: {pr_url}")
            
            return pr_url
            
        except Exception as e:
            logger.error(f"Failed to create pull request: {e}")
            return None
    
    def _get_repo_url(self) -> Optional[str]:
        """Get repository URL."""
        try:
            # Try to get origin URL
            origin = self.repo.remote('origin')
            return origin.url
        except Exception:
            return None
    
    def _create_github_pr(
        self,
        repo_url: str,
        title: str,
        description: str,
        base_branch: str,
        head_branch: str
    ) -> Optional[str]:
        """Create GitHub pull request."""
        try:
            # Extract owner and repo from URL
            if repo_url.endswith('.git'):
                repo_url = repo_url[:-4]
            
            parts = repo_url.replace('https://github.com/', '').split('/')
            if len(parts) < 2:
                return None
            
            owner, repo = parts[0], parts[1]
            
            # GitHub API endpoint
            api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
            
            # Request payload
            payload = {
                'title': title,
                'body': description,
                'head': head_branch,
                'base': base_branch
            }
            
            # Headers
            headers = {
                'Authorization': f'token {self.settings.git.token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            # Create pull request
            response = requests.post(api_url, json=payload, headers=headers)
            
            if response.status_code == 201:
                pr_data = response.json()
                return pr_data['html_url']
            else:
                logger.error(f"GitHub API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create GitHub PR: {e}")
            return None
    
    def _create_gitlab_mr(
        self,
        repo_url: str,
        title: str,
        description: str,
        base_branch: str,
        head_branch: str
    ) -> Optional[str]:
        """Create GitLab merge request."""
        try:
            # Extract project path from URL
            if repo_url.endswith('.git'):
                repo_url = repo_url[:-4]
            
            project_path = repo_url.replace('https://gitlab.com/', '')
            project_path_encoded = project_path.replace('/', '%2F')
            
            # GitLab API endpoint
            api_url = f"https://gitlab.com/api/v4/projects/{project_path_encoded}/merge_requests"
            
            # Request payload
            payload = {
                'title': title,
                'description': description,
                'source_branch': head_branch,
                'target_branch': base_branch
            }
            
            # Headers
            headers = {
                'Private-Token': self.settings.git.token,
                'Content-Type': 'application/json'
            }
            
            # Create merge request
            response = requests.post(api_url, json=payload, headers=headers)
            
            if response.status_code == 201:
                mr_data = response.json()
                return mr_data['web_url']
            else:
                logger.error(f"GitLab API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create GitLab MR: {e}")
            return None
    
    async def _store_git_operation(
        self,
        session_id: str,
        operation_type: str,
        branch_name: Optional[str] = None,
        commit_hash: Optional[str] = None,
        pull_request_url: Optional[str] = None
    ):
        """Store git operation in database."""
        try:
            async with vector_db_manager.session_factory() as db_session:
                from sqlalchemy import text
                
                metadata = {}
                if branch_name:
                    metadata['branch_name'] = branch_name
                if commit_hash:
                    metadata['commit_hash'] = commit_hash
                if pull_request_url:
                    metadata['pull_request_url'] = pull_request_url
                
                query = text("""
                    INSERT INTO code_refactor.git_operations 
                    (session_id, operation_type, branch_name, commit_hash, 
                     pull_request_url, status, metadata)
                    VALUES (:session_id, :operation_type, :branch_name, :commit_hash,
                            :pull_request_url, :status, :metadata)
                """)
                
                await db_session.execute(
                    query,
                    {
                        "session_id": session_id,
                        "operation_type": operation_type,
                        "branch_name": branch_name,
                        "commit_hash": commit_hash,
                        "pull_request_url": pull_request_url,
                        "status": "completed",
                        "metadata": json.dumps(metadata) if metadata else None
                    }
                )
                
                await db_session.commit()
                
        except Exception as e:
            logger.error(f"Failed to store git operation: {e}")
    
    def cleanup(self):
        """Cleanup and return to original branch."""
        try:
            if self.repo and self.original_branch:
                print(f"🧹 Returning to original branch: {self.original_branch}")
                self.repo.git.checkout(self.original_branch)
                
        except Exception as e:
            logger.error(f"Failed to cleanup git state: {e}")


# Import asyncio at the top level to avoid issues
import asyncio

