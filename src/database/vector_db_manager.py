"""
Vector Database Manager for storing and retrieving code standards as embeddings.
"""

import asyncio
import logging
import json
from typing import List, Dict, Optional, Tuple, Any
from uuid import UUID, uuid4
import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import asyncpg

from ..config.settings import settings


logger = logging.getLogger(__name__)


class VectorDBManager:
    """Manages vector database operations for code standards."""
    
    def __init__(self):
        self.settings = settings
        self.embedding_model = None
        self.engine = None
        self.async_engine = None
        self.session_factory = None
        
    async def initialize(self):
        """Initialize the vector database manager."""
        try:
            print("🚀 Initializing Vector Database Manager...")
            
            # Initialize embedding model
            print("📊 Loading embedding model...")
            self.embedding_model = SentenceTransformer(
                self.settings.vector_db.embedding_model
            )
            print(f"✅ Embedding model loaded: {self.settings.vector_db.embedding_model}")
            
            # Initialize database connections
            self.engine = create_engine(self.settings.database.url)
            self.async_engine = create_async_engine(
                self.settings.database.url.replace("postgresql://", "postgresql+asyncpg://")
            )
            self.session_factory = sessionmaker(
                self.async_engine, class_=AsyncSession, expire_on_commit=False
            )
            
            print("✅ Vector Database Manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize VectorDBManager: {e}")
            raise
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for given text."""
        try:
            if self.embedding_model is None:
                raise RuntimeError("Embedding model not initialized")
            
            # Generate embedding
            embedding = self.embedding_model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise
    
    async def store_code_standard(
        self,
        rule_id: str,
        title: str,
        description: str,
        category: str,
        severity: str = "medium",
        language: str = "python",
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """Store a code standard with its embedding."""
        try:
            print(f"💾 Storing code standard: {rule_id}")
            
            # Generate embedding for the combined text
            combined_text = f"{title}. {description}"
            embedding = self.generate_embedding(combined_text)
            
            # Store in database
            async with self.session_factory() as session:
                query = text("""
                    INSERT INTO code_refactor.code_standards 
                    (rule_id, title, description, category, severity, language, embedding, metadata)
                    VALUES (:rule_id, :title, :description, :category, :severity, :language, :embedding, :metadata)
                    ON CONFLICT (rule_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        category = EXCLUDED.category,
                        severity = EXCLUDED.severity,
                        language = EXCLUDED.language,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                """)
                
                # Convert embedding list to string format for pgvector
                embedding_str = str(embedding.tolist() if hasattr(embedding, 'tolist') else embedding)
                
                result = await session.execute(
                    query,
                    {
                        "rule_id": rule_id,
                        "title": title,
                        "description": description,
                        "category": category,
                        "severity": severity,
                        "language": language,
                        "embedding": embedding_str,
                        "metadata": json.dumps(metadata) if metadata else None
                    }
                )
                
                await session.commit()
                record_id = result.scalar()
                
                print(f"✅ Code standard stored: {rule_id}")
                return record_id
                
        except Exception as e:
            logger.error(f"Failed to store code standard {rule_id}: {e}")
            raise
    
    async def search_similar_standards(
        self,
        query_text: str,
        language: str = "python",
        category: Optional[str] = None,
        threshold: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar code standards using cosine similarity."""
        try:
            print(f"🔍 Searching for similar standards to: '{query_text[:50]}...'")
            
            # Generate embedding for query
            query_embedding = self.generate_embedding(query_text)
            
            # Use default values if not provided
            threshold = threshold or self.settings.vector_db.similarity_threshold
            limit = limit or self.settings.vector_db.max_similar_rules
            
            # Search in database
            async with self.session_factory() as session:
                # Convert embedding to string for pgvector
                embedding_list = query_embedding.tolist() if hasattr(query_embedding, 'tolist') else query_embedding
                embedding_str = str(embedding_list)
                
                # Use f-string for embedding since asyncpg doesn't support ::vector casting with bind parameters
                query = text(f"""
                    SELECT * FROM code_refactor.find_similar_standards(
                        '{embedding_str}'::vector,
                        :match_threshold,
                        :match_count,
                        :filter_language,
                        :filter_category
                    )
                """)
                
                result = await session.execute(
                    query,
                    {
                        "match_threshold": threshold,
                        "match_count": limit,
                        "filter_language": language,
                        "filter_category": category
                    }
                )
                
                results = []
                for row in result:
                    results.append({
                        "rule_id": row.rule_id,
                        "title": row.title,
                        "description": row.description,
                        "category": row.category,
                        "severity": row.severity,
                        "similarity": row.similarity
                    })
                
                print(f"✅ Found {len(results)} similar standards")
                return results
                
        except Exception as e:
            logger.error(f"Failed to search similar standards: {e}")
            raise
    
    async def load_standards_from_file(self, file_path: str) -> int:
        """Load code standards from a file (JSON, CSV, or text)."""
        try:
            print(f"📁 Loading standards from file: {file_path}")
            
            import pandas as pd
            from pathlib import Path
            
            file_path = Path(file_path)
            
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            standards_loaded = 0
            
            if file_path.suffix.lower() == '.json':
                # Load from JSON file
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if isinstance(data, list):
                    for item in data:
                        await self.store_code_standard(
                            rule_id=item.get('rule_id', f"rule_{uuid4().hex[:8]}"),
                            title=item.get('title', ''),
                            description=item.get('description', ''),
                            category=item.get('category', 'general'),
                            severity=item.get('severity', 'medium'),
                            language=item.get('language', 'python'),
                            metadata=item.get('metadata')
                        )
                        standards_loaded += 1
                        
            elif file_path.suffix.lower() == '.csv':
                # Load from CSV file
                df = pd.read_csv(file_path)
                
                for _, row in df.iterrows():
                    await self.store_code_standard(
                        rule_id=row.get('rule_id', f"rule_{uuid4().hex[:8]}"),
                        title=row.get('title', ''),
                        description=row.get('description', ''),
                        category=row.get('category', 'general'),
                        severity=row.get('severity', 'medium'),
                        language=row.get('language', 'python'),
                        metadata={'source_file': str(file_path)}
                    )
                    standards_loaded += 1
                    
            elif file_path.suffix.lower() == '.txt':
                # Load from text file (assume each line is a rule)
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for i, line in enumerate(lines):
                    line = line.strip()
                    if line:
                        await self.store_code_standard(
                            rule_id=f"rule_{i+1:04d}",
                            title=f"Rule {i+1}",
                            description=line,
                            category='general',
                            severity='medium',
                            language='python',
                            metadata={'source_file': str(file_path), 'line_number': i+1}
                        )
                        standards_loaded += 1
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")
            
            print(f"✅ Loaded {standards_loaded} standards from {file_path}")
            return standards_loaded
            
        except Exception as e:
            logger.error(f"Failed to load standards from file {file_path}: {e}")
            raise
    
    async def load_standards_from_url(self, url: str) -> int:
        """Load code standards from a web URL."""
        try:
            print(f"🌐 Loading standards from URL: {url}")
            
            import aiohttp
            import tempfile
            from pathlib import Path
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to fetch URL: {response.status}")
                    
                    content = await response.read()
                    
                    # Determine file type from URL or content-type
                    content_type = response.headers.get('content-type', '')
                    
                    if 'json' in content_type or url.endswith('.json'):
                        suffix = '.json'
                    elif 'csv' in content_type or url.endswith('.csv'):
                        suffix = '.csv'
                    else:
                        suffix = '.txt'
                    
                    # Save to temporary file and load
                    with tempfile.NamedTemporaryFile(mode='wb', suffix=suffix, delete=False) as f:
                        f.write(content)
                        temp_path = f.name
                    
                    try:
                        standards_loaded = await self.load_standards_from_file(temp_path)
                        return standards_loaded
                    finally:
                        Path(temp_path).unlink()  # Clean up temp file
                        
        except Exception as e:
            logger.error(f"Failed to load standards from URL {url}: {e}")
            raise
    
    async def get_all_categories(self) -> List[str]:
        """Get all unique categories from stored standards."""
        try:
            async with self.session_factory() as session:
                query = text("""
                    SELECT DISTINCT category 
                    FROM code_refactor.code_standards 
                    ORDER BY category
                """)
                
                result = await session.execute(query)
                categories = [row[0] for row in result]
                
                return categories
                
        except Exception as e:
            logger.error(f"Failed to get categories: {e}")
            raise
    
    async def get_standards_count(self) -> int:
        """Get total count of stored standards."""
        try:
            async with self.session_factory() as session:
                query = text("SELECT COUNT(*) FROM code_refactor.code_standards")
                result = await session.execute(query)
                count = result.scalar()
                
                return count
                
        except Exception as e:
            logger.error(f"Failed to get standards count: {e}")
            raise
    
    async def close(self):
        """Close database connections."""
        try:
            if self.async_engine:
                await self.async_engine.dispose()
            print("✅ Vector Database Manager closed")
            
        except Exception as e:
            logger.error(f"Error closing VectorDBManager: {e}")


# Global instance
vector_db_manager = VectorDBManager()

