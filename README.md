# AgenticAI_AutomatedGitPR_CodeRefactoring_Guidelines
Agentic AI Automated Git Pull Request for Code Refactoring against Guidelines
# Enterprise Code Refactor

An enterprise-grade code refactoring solution using AI, PostgreSQL vector database, and RAG (Retrieval-Augmented Generation) for analyzing Python code against coding standards and guidelines.

## 🌟 Features

- **AI-Powered Analysis**: Uses LLM (OpenAI/Anthropic) for intelligent code analysis
- **Vector Database**: PostgreSQL with pgvector for efficient similarity search
- **RAG System**: Retrieval-Augmented Generation for contextual code standards matching
- **Parallel Processing**: Master-worker architecture using LangGraph for concurrent file analysis
- **Git Integration**: Automatic branch creation and pull request generation
- **AST-Based Parsing**: Deep code structure analysis using Python AST
- **Diff Generation**: Automatic creation of diff files for code updates
- **Enterprise Ready**: Docker containerization, comprehensive testing, and monitoring

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CLI Interface │    │  Web Interface  │    │   Docker API    │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼───────────────┐
                    │    Master Orchestrator      │
                    │   (LangGraph Coordinator)   │
                    └─────────────┬───────────────┘
                                  │
                ┌─────────────────┼─────────────────┐
                │                 │                 │
         ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
         │ Worker Agent│  │ Worker Agent│  │ Worker Agent│
         │    #1       │  │    #2       │  │    #N       │
         └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
                │                │                │
                └─────────────────┼─────────────────┘
                                  │
                ┌─────────────────▼─────────────────┐
                │        RAG System                 │
                │  ┌─────────────────────────────┐  │
                │  │    Vector Database          │  │
                │  │   (PostgreSQL + pgvector)  │  │
                │  └─────────────────────────────┘  │
                └───────────────────────────────────┘
```

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- Docker and Docker Compose (for containerized deployment)
- Git (for repository analysis and PR creation)
- OpenAI or Anthropic API key

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd enterprise_refactor
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup Database

#### Option A: Using Docker (Recommended)

```bash
# Start PostgreSQL with pgvector
docker-compose up -d postgres

# Wait for database to be ready
docker-compose logs postgres
```

#### Option B: Manual PostgreSQL Setup

```bash
# Install PostgreSQL and pgvector extension
sudo apt-get install postgresql-15 postgresql-15-pgvector

# Create database
sudo -u postgres createdb enterprise_code_refactor

# Run setup script
sudo -u postgres psql enterprise_code_refactor < database/setup_database.sql
```

### 4. Configure Environment

```bash
# Copy configuration template
cp config.env .env

# Edit configuration
nano .env
```

**Required Configuration:**
```env
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/enterprise_code_refactor

# LLM API Keys (choose one)
OPENAI_API_KEY=your_openai_api_key_here
# OR
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Git Integration (optional)
GIT_USERNAME=your_git_username
GIT_TOKEN=your_git_token
```

### 5. Load Code Standards

```bash
# Load standards from JSON file
python main.py load-standards --file standards.json

# Or load from URL
python main.py load-standards --url https://example.com/standards.json

# Check system status
python main.py status
```

### 6. Analyze Code

#### Analyze Local Folder

```bash
# Basic analysis
python main.py analyze-folder /path/to/your/code

# With Git integration
python main.py analyze-folder /path/to/your/code --create-git-branch --create-pr

# Custom session name and output
python main.py analyze-folder /path/to/your/code \
    --session-name "my-refactor-session" \
    --output-dir ./results
```

#### Analyze Git Repository

```bash
# Analyze remote repository
python main.py analyze-repo https://github.com/user/repo.git

# Specific branch
python main.py analyze-repo https://github.com/user/repo.git --branch develop

# With PR creation
python main.py analyze-repo https://github.com/user/repo.git --create-pr
```

## 🐳 Docker Deployment

### Full Stack Deployment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Scale workers (if needed)
docker-compose up -d --scale app=3
```

### Environment Variables for Docker

Create `.env` file:

```env
# Database
DATABASE_USER=coderefactor
DATABASE_PASSWORD=secure_password_123

# LLM Configuration
OPENAI_API_KEY=your_key_here
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-3.5-turbo

# Git Integration
GIT_USERNAME=your_username
GIT_TOKEN=your_token

# Application
MAX_WORKERS=4
LOG_LEVEL=INFO
```

### Services Included

- **PostgreSQL**: Database with pgvector extension
- **App**: Main application container
- **pgAdmin**: Database management (optional, use `--profile tools`)
- **Redis**: Caching layer (optional, use `--profile cache`)

## 📊 Usage Examples

### 1. Basic Code Analysis

```bash
# Analyze current directory
python main.py analyze-folder .

# Analyze with custom workers
MAX_WORKERS=8 python main.py analyze-folder ./src
```

### 2. Git Workflow Integration

```bash
# Analyze and create refactor branch
python main.py analyze-folder ./src --create-git-branch

# Analyze, commit, and create PR
python main.py analyze-folder ./src --create-git-branch --create-pr
```

### 3. Custom Standards

```bash
# Load custom standards
python main.py load-standards --file ./my-standards.json

# Load from company guidelines URL
python main.py load-standards --url https://company.com/coding-standards.json
```

### 4. Session Management

```bash
# List recent sessions
python main.py list-sessions

# View specific session results
python main.py show-results <session-id>

# Check system status
python main.py status
```

## 📁 Project Structure

```
enterprise_refactor/
├── src/                          # Source code
│   ├── agents/                   # Worker agents and orchestrator
│   │   ├── master_orchestrator.py
│   │   └── worker_agent.py
│   ├── analysis/                 # Code analysis modules
│   │   ├── code_parser.py
│   │   └── rag_system.py
│   ├── config/                   # Configuration management
│   │   └── settings.py
│   ├── database/                 # Database operations
│   │   └── vector_db_manager.py
│   ├── diff/                     # Diff generation
│   │   └── diff_generator.py
│   └── git/                      # Git integration
│       └── git_manager.py
├── database/                     # Database setup scripts
│   └── setup_database.sql
├── tests/                        # Test suite
│   ├── conftest.py
│   ├── test_code_parser.py
│   └── test_diff_generator.py
├── main.py                       # CLI application entry point
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Docker configuration
├── docker-compose.yml            # Multi-service Docker setup
├── config.env                    # Configuration template
└── README.md                     # This file
```

## 🧪 Testing

### Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_code_parser.py

# Run with coverage
pytest --cov=src

# Run only unit tests
pytest -m "not integration"
```

### Test Categories

- **Unit Tests**: Individual component testing
- **Integration Tests**: Multi-component testing
- **Docker Tests**: Containerized environment testing

## 📈 Performance Tuning

### Configuration Options

```env
# Worker Configuration
MAX_WORKERS=8              # Number of parallel workers
BATCH_SIZE=20              # Files per batch

# LLM Configuration
LLM_TEMPERATURE=0.1        # Response variability (0.0-2.0)
LLM_MAX_TOKENS=2048        # Maximum response length
LLM_TIMEOUT=60             # Request timeout in seconds

# Vector Database
SIMILARITY_THRESHOLD=0.7   # Minimum similarity for rule matching
MAX_SIMILAR_RULES=10       # Maximum rules returned per query
EMBEDDING_DIMENSION=384    # Vector dimension size
```

### Performance Guidelines

1. **Worker Count**: Set to number of CPU cores
2. **Batch Size**: 10-50 files per batch for optimal memory usage
3. **Database**: Use connection pooling for high loads
4. **LLM**: Lower temperature for more consistent results

## 🔒 Security Considerations

### API Keys
- Store API keys in environment variables
- Use Docker secrets in production
- Rotate keys regularly

### Database Security
- Use strong passwords
- Enable SSL connections
- Restrict network access
- Regular backups

### Git Integration
- Use personal access tokens
- Limit token permissions
- Review generated PRs before merging

## 🐛 Troubleshooting

### Common Issues

**Database Connection Error**
```bash
# Check PostgreSQL status
docker-compose logs postgres

# Verify pgvector extension
docker-compose exec postgres psql -U coderefactor -d enterprise_code_refactor -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

**LLM API Errors**
```bash
# Check API key
echo $OPENAI_API_KEY

# Test API connectivity
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
```

**Git Integration Issues**
```bash
# Check Git configuration
git config --list

# Verify token permissions
curl -H "Authorization: token $GIT_TOKEN" https://api.github.com/user
```

### Debug Mode

```bash
# Enable verbose logging
python main.py --verbose analyze-folder ./src

# Check system status
python main.py status

# View recent sessions
python main.py list-sessions
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt
pip install pytest pytest-cov black flake8 mypy

# Run pre-commit checks
black src/ tests/
flake8 src/ tests/
mypy src/
pytest
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- OpenAI and Anthropic for LLM APIs
- PostgreSQL and pgvector teams
- LangChain and LangGraph communities
- Python AST and Git communities

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Search existing GitHub issues
3. Create a new issue with detailed information
4. Join our Discord community

---

**Enterprise Code Refactor** - Transforming code quality with AI-powered analysis.

