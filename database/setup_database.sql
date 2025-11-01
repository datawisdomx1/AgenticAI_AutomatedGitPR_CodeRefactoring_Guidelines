-- Enterprise Code Refactor Database Setup
-- This script sets up the PostgreSQL database with pgvector extension

-- Create database (run this as superuser)
-- CREATE DATABASE enterprise_code_refactor;

-- Connect to the database and run the following:
-- \c enterprise_code_refactor;

-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create schema for the application
CREATE SCHEMA IF NOT EXISTS code_refactor;

-- Create table for code standards and guidelines
CREATE TABLE IF NOT EXISTS code_refactor.code_standards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_id VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    severity VARCHAR(20) DEFAULT 'medium',
    language VARCHAR(50) DEFAULT 'python',
    embedding vector(384), -- Using sentence-transformers all-MiniLM-L6-v2 (384 dimensions)
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create table for analysis sessions
CREATE TABLE IF NOT EXISTS code_refactor.analysis_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_name VARCHAR(255) NOT NULL,
    source_type VARCHAR(50) NOT NULL, -- 'folder' or 'git'
    source_path TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- pending, in_progress, completed, failed
    total_files INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    failed_files INTEGER DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create table for file analysis results
CREATE TABLE IF NOT EXISTS code_refactor.file_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES code_refactor.analysis_sessions(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    file_hash VARCHAR(64), -- SHA256 hash of file content
    worker_agent_id VARCHAR(100),
    analysis_status VARCHAR(50) DEFAULT 'pending', -- pending, analyzing, completed, failed
    violations_found INTEGER DEFAULT 0,
    diff_generated BOOLEAN DEFAULT FALSE,
    diff_file_path TEXT,
    error_message TEXT,
    analysis_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create table for code violations
CREATE TABLE IF NOT EXISTS code_refactor.code_violations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_analysis_id UUID NOT NULL REFERENCES code_refactor.file_analysis(id) ON DELETE CASCADE,
    rule_id VARCHAR(100) NOT NULL REFERENCES code_refactor.code_standards(rule_id),
    line_number INTEGER,
    column_number INTEGER,
    violation_description TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL,
    suggested_fix TEXT,
    confidence_score FLOAT DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create table for git operations
CREATE TABLE IF NOT EXISTS code_refactor.git_operations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES code_refactor.analysis_sessions(id) ON DELETE CASCADE,
    operation_type VARCHAR(50) NOT NULL, -- clone, branch_create, commit, pull_request
    branch_name VARCHAR(255),
    commit_hash VARCHAR(64),
    pull_request_url TEXT,
    status VARCHAR(50) DEFAULT 'pending', -- pending, in_progress, completed, failed
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_code_standards_embedding ON code_refactor.code_standards USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_code_standards_category ON code_refactor.code_standards(category);
CREATE INDEX IF NOT EXISTS idx_code_standards_language ON code_refactor.code_standards(language);
CREATE INDEX IF NOT EXISTS idx_analysis_sessions_status ON code_refactor.analysis_sessions(status);
CREATE INDEX IF NOT EXISTS idx_file_analysis_session_id ON code_refactor.file_analysis(session_id);
CREATE INDEX IF NOT EXISTS idx_file_analysis_status ON code_refactor.file_analysis(analysis_status);
CREATE INDEX IF NOT EXISTS idx_code_violations_file_analysis_id ON code_refactor.code_violations(file_analysis_id);
CREATE INDEX IF NOT EXISTS idx_code_violations_rule_id ON code_refactor.code_violations(rule_id);
CREATE INDEX IF NOT EXISTS idx_git_operations_session_id ON code_refactor.git_operations(session_id);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION code_refactor.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updating updated_at
CREATE TRIGGER update_code_standards_updated_at BEFORE UPDATE ON code_refactor.code_standards FOR EACH ROW EXECUTE FUNCTION code_refactor.update_updated_at_column();
CREATE TRIGGER update_analysis_sessions_updated_at BEFORE UPDATE ON code_refactor.analysis_sessions FOR EACH ROW EXECUTE FUNCTION code_refactor.update_updated_at_column();
CREATE TRIGGER update_file_analysis_updated_at BEFORE UPDATE ON code_refactor.file_analysis FOR EACH ROW EXECUTE FUNCTION code_refactor.update_updated_at_column();
CREATE TRIGGER update_git_operations_updated_at BEFORE UPDATE ON code_refactor.git_operations FOR EACH ROW EXECUTE FUNCTION code_refactor.update_updated_at_column();

-- Create a function for similarity search
CREATE OR REPLACE FUNCTION code_refactor.find_similar_standards(
    query_embedding vector(384),
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 10,
    filter_language text DEFAULT NULL,
    filter_category text DEFAULT NULL
)
RETURNS TABLE (
    rule_id VARCHAR(100),
    title VARCHAR(500),
    description TEXT,
    category VARCHAR(100),
    severity VARCHAR(20),
    similarity FLOAT
)
LANGUAGE sql STABLE
AS $$
    SELECT 
        cs.rule_id,
        cs.title,
        cs.description,
        cs.category,
        cs.severity,
        1 - (cs.embedding <=> query_embedding) as similarity
    FROM code_refactor.code_standards cs
    WHERE 
        (1 - (cs.embedding <=> query_embedding)) > match_threshold
        AND (filter_language IS NULL OR cs.language = filter_language)
        AND (filter_category IS NULL OR cs.category = filter_category)
    ORDER BY cs.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- Grant permissions (adjust as needed for your environment)
-- GRANT USAGE ON SCHEMA code_refactor TO your_app_user;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA code_refactor TO your_app_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA code_refactor TO your_app_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA code_refactor TO your_app_user;

