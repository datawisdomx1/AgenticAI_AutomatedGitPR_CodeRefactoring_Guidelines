# Installation Guide

This guide provides detailed installation instructions for the Enterprise Code Refactor system.

## 📋 System Requirements

### Minimum Requirements
- **OS**: Linux (Ubuntu 20.04+), macOS (10.15+), or Windows 10+
- **Python**: 3.11 or higher
- **Memory**: 4GB RAM
- **Storage**: 2GB free space
- **Network**: Internet connection for LLM APIs

### Recommended Requirements
- **OS**: Linux (Ubuntu 22.04 LTS)
- **Python**: 3.11
- **Memory**: 8GB RAM
- **Storage**: 10GB free space
- **CPU**: 4+ cores for optimal parallel processing

## 🐳 Installation Options

### Option 1: Docker Installation (Recommended)

Docker installation is the easiest and most reliable method.

#### Prerequisites
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

#### Setup Steps
```bash
# 1. Clone the repository
git clone <repository-url>
cd enterprise_refactor

# 2. Create environment file
cp config.env .env

# 3. Edit configuration (see Configuration section below)
nano .env

# 4. Start services
docker-compose up -d

# 5. Wait for services to be ready
docker-compose logs -f postgres

# 6. Verify installation
docker-compose exec app python main.py status
```

### Option 2: Local Installation

For development or when Docker is not available.

#### Prerequisites

##### Ubuntu/Debian
```bash
# Update package list
sudo apt update

# Install Python 3.11
sudo apt install python3.11 python3.11-venv python3.11-dev

# Install PostgreSQL 15
sudo apt install postgresql-15 postgresql-15-dev

# Install build tools
sudo apt install build-essential git curl
```

##### macOS
```bash
# Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.11
brew install python@3.11

# Install PostgreSQL 15
brew install postgresql@15

# Install Git
brew install git
```

##### Windows
```powershell
# Install Python 3.11 from python.org
# Download and install from: https://www.python.org/downloads/

# Install PostgreSQL 15
# Download from: https://www.postgresql.org/download/windows/

# Install Git
# Download from: https://git-scm.com/download/win
```

#### PostgreSQL Setup

##### Install pgvector Extension

**Ubuntu/Debian:**
```bash
# Install pgvector
sudo apt install postgresql-15-pgvector

# Or build from source
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

**macOS:**
```bash
# Install pgvector via Homebrew
brew install pgvector

# Or build from source
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
make install
```

**Windows:**
```powershell
# Download pre-built binaries from pgvector releases
# Or use conda
conda install -c conda-forge pgvector
```

##### Create Database
```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE enterprise_code_refactor;
CREATE USER coderefactor WITH PASSWORD 'your_password_here';
GRANT ALL PRIVILEGES ON DATABASE enterprise_code_refactor TO coderefactor;
\q

# Run setup script
sudo -u postgres psql enterprise_code_refactor < database/setup_database.sql
```

#### Python Environment Setup
```bash
# 1. Clone repository
git clone <repository-url>
cd enterprise_refactor

# 2. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Upgrade pip
pip install --upgrade pip

# 4. Install dependencies
pip install -r requirements.txt

# 5. Create configuration
cp config.env .env
```

### Option 3: Cloud Deployment

#### AWS Deployment

##### Using AWS ECS
```bash
# 1. Build and push Docker image
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker build -t enterprise-code-refactor .
docker tag enterprise-code-refactor:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/enterprise-code-refactor:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/enterprise-code-refactor:latest

# 2. Deploy using AWS CLI or CloudFormation
aws ecs create-service --service-name code-refactor --cluster default --task-definition code-refactor:1
```

##### Using AWS RDS for PostgreSQL
```bash
# Create RDS PostgreSQL instance with pgvector
aws rds create-db-instance \
    --db-instance-identifier code-refactor-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --engine-version 15.3 \
    --master-username coderefactor \
    --master-user-password YourSecurePassword123 \
    --allocated-storage 20
```

#### Google Cloud Platform

```bash
# 1. Build and deploy using Cloud Run
gcloud builds submit --tag gcr.io/PROJECT-ID/enterprise-code-refactor
gcloud run deploy --image gcr.io/PROJECT-ID/enterprise-code-refactor --platform managed
```

#### Microsoft Azure

```bash
# 1. Create container registry
az acr create --resource-group myResourceGroup --name myRegistry --sku Basic

# 2. Build and push image
az acr build --registry myRegistry --image enterprise-code-refactor .

# 3. Deploy to Container Instances
az container create --resource-group myResourceGroup --name code-refactor --image myRegistry.azurecr.io/enterprise-code-refactor:latest
```

## ⚙️ Configuration

### Environment Variables

Create `.env` file with the following configuration:

```env
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/enterprise_code_refactor
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=enterprise_code_refactor
DATABASE_USER=coderefactor
DATABASE_PASSWORD=your_secure_password
DATABASE_SCHEMA=code_refactor

# LLM Configuration
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-3.5-turbo
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=2048
LLM_TIMEOUT=60

# Vector Database Configuration
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
SIMILARITY_THRESHOLD=0.7
MAX_SIMILAR_RULES=10

# Git Configuration
GIT_USERNAME=your_git_username
GIT_TOKEN=your_git_token
DEFAULT_BRANCH_PREFIX=code-refactor
DEFAULT_COMMIT_MESSAGE=Code refactoring based on standards analysis

# Application Configuration
MAX_WORKERS=4
BATCH_SIZE=10
LOG_LEVEL=INFO
OUTPUT_DIR=./output
TEMP_DIR=./temp
```

### API Keys Setup

#### OpenAI API Key
1. Visit [OpenAI API](https://platform.openai.com/api-keys)
2. Create a new API key
3. Add to `.env` file: `OPENAI_API_KEY=sk-...`

#### Anthropic API Key
1. Visit [Anthropic Console](https://console.anthropic.com/)
2. Create a new API key
3. Add to `.env` file: `ANTHROPIC_API_KEY=sk-ant-...`

#### Git Token (Optional)
1. **GitHub**: Settings → Developer settings → Personal access tokens
2. **GitLab**: User Settings → Access Tokens
3. Required permissions: `repo`, `write:repo_hook`
4. Add to `.env` file: `GIT_TOKEN=ghp_...`

## 🏥 Health Checks

### Verify Installation

```bash
# 1. Check Python version
python --version

# 2. Check database connection
python -c "
import asyncio
import sys
sys.path.append('src')
from src.database.vector_db_manager import vector_db_manager

async def test():
    await vector_db_manager.initialize()
    count = await vector_db_manager.get_standards_count()
    print(f'Database connected. Standards count: {count}')
    await vector_db_manager.close()

asyncio.run(test())
"

# 3. Check LLM API
python -c "
import os
import openai
openai.api_key = os.getenv('OPENAI_API_KEY')
try:
    models = openai.Model.list()
    print('OpenAI API connected successfully')
except Exception as e:
    print(f'OpenAI API error: {e}')
"

# 4. Run system status check
python main.py status
```

### Docker Health Checks

```bash
# Check all services
docker-compose ps

# Check specific service logs
docker-compose logs postgres
docker-compose logs app

# Check database connectivity
docker-compose exec postgres pg_isready -U coderefactor

# Check pgvector extension
docker-compose exec postgres psql -U coderefactor -d enterprise_code_refactor -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

## 🔧 Troubleshooting

### Common Installation Issues

#### Python Version Issues
```bash
# Check Python version
python --version

# Install specific Python version (Ubuntu)
sudo apt install python3.11

# Create virtual environment with specific version
python3.11 -m venv venv
```

#### PostgreSQL Connection Issues
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Check if pgvector is installed
sudo -u postgres psql -c "SELECT * FROM pg_available_extensions WHERE name='vector';"

# Check database exists
sudo -u postgres psql -l | grep enterprise_code_refactor
```

#### Permission Issues
```bash
# Fix PostgreSQL permissions
sudo -u postgres psql enterprise_code_refactor -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA code_refactor TO coderefactor;"
sudo -u postgres psql enterprise_code_refactor -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA code_refactor TO coderefactor;"
```

#### Docker Issues
```bash
# Check Docker daemon
sudo systemctl status docker

# Check Docker Compose version
docker-compose --version

# Reset Docker environment
docker-compose down -v
docker-compose up -d
```

#### Memory Issues
```bash
# Check available memory
free -h

# Reduce worker count for low memory systems
echo "MAX_WORKERS=2" >> .env
echo "BATCH_SIZE=5" >> .env
```

### Performance Optimization

#### Database Optimization
```sql
-- Increase shared memory (PostgreSQL)
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET work_mem = '16MB';
SELECT pg_reload_conf();
```

#### Application Optimization
```env
# Optimize for your system
MAX_WORKERS=8              # Number of CPU cores
BATCH_SIZE=20              # Increase for more memory
LLM_TIMEOUT=120            # Increase for slower networks
```

## 📊 Monitoring Setup

### Logging Configuration
```env
# Enable debug logging
LOG_LEVEL=DEBUG

# Log to file
LOG_FILE=./logs/app.log
```

### Metrics Collection
```bash
# Install monitoring tools (optional)
pip install prometheus-client grafana-api

# Enable metrics endpoint
echo "ENABLE_METRICS=true" >> .env
```

### Database Monitoring
```sql
-- Monitor database performance
SELECT * FROM pg_stat_activity WHERE datname = 'enterprise_code_refactor';
SELECT * FROM pg_stat_user_tables WHERE schemaname = 'code_refactor';
```

## 🔄 Updates and Maintenance

### Update Application
```bash
# Pull latest changes
git pull origin main

# Update dependencies
pip install -r requirements.txt --upgrade

# Run database migrations (if any)
python manage.py migrate

# Restart services
docker-compose restart app
```

### Backup and Recovery
```bash
# Backup database
pg_dump -U coderefactor enterprise_code_refactor > backup.sql

# Restore database
psql -U coderefactor enterprise_code_refactor < backup.sql

# Backup Docker volumes
docker run --rm -v enterprise_refactor_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz /data
```

## 🎯 Next Steps

After successful installation:

1. **Load Code Standards**: `python main.py load-standards --file standards.json`
2. **Test Analysis**: `python main.py analyze-folder ./test-code`
3. **Configure Git Integration**: Set up Git tokens for PR creation
4. **Set Up Monitoring**: Configure logging and metrics
5. **Scale Workers**: Adjust `MAX_WORKERS` based on your system

For detailed usage instructions, see the main [README.md](README.md) file.

