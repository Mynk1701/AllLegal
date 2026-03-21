# AllLegal - Legal Case Search API

A production-grade **FastAPI** application for searching Indian legal cases with fast boolean queries using **OpenSearch** and **Supabase** authentication.

## 🎯 Problem Statement

Indian legal research apps have major issues:

- **Poor Interfaces**: Difficult navigation and UX
- **High Costs**: Expensive subscriptions
- **Limited Search**: No true boolean search capabilities

**AllLegal Solution:**

- Extract metadata from legal case PDFs
- Index cases in OpenSearch for fast boolean search
- Modern, type-safe API
- Supabase for auth and database
- Scalable production architecture

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│         FastAPI Application                 │
│  (Type-safe endpoints with Pydantic)        │
└────────────────────┬────────────────────────┘
                     │
      ┌──────────────┼──────────────┐
      │              │              │
      ▼              ▼              ▼
┌─────────┐   ┌─────────────┐   ┌──────────┐
│Supabase │   │OpenSearch   │   │  Redis   │
│(Auth &  │   │(Search)     │   │(Cache)   │
│Database)│   │             │   │          │
└─────────┘   └─────────────┘   └──────────┘
```

---

## ⚡ Tech Stack

| Component       | Technology            | Purpose                          |
| --------------- | --------------------- | -------------------------------- |
| **Framework**   | FastAPI               | Modern, fast web framework       |
| **Database**    | Supabase + PostgreSQL | Case metadata storage            |
| **Auth**        | Supabase JWT          | User authentication              |
| **Search**      | OpenSearch            | Fast boolean searching           |
| **Cache**       | Redis                 | Performance optimization         |
| **Type Safety** | Pydantic              | All requests/responses validated |
| **Container**   | Docker Compose        | Local dev environment            |

---

## 🚀 Quick Start (Windows)

### 1️⃣ Setup Virtual Environment

```batch
setup.bat
```

This automatically:

- Creates Python virtual environment
- Installs all dependencies
- Creates required directories

### 2️⃣ Update Supabase Credentials

Edit `.env` file with your Supabase project details:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
```

**Get Supabase credentials:**

1. Go to https://app.supabase.com
2. Create new project
3. Go to Settings → API Keys
4. Copy the keys to `.env`

### 3️⃣ Start Services

```bash
docker-compose up
```

This starts 4 services:

- **PostgreSQL** (port 5432) - Database
- **Redis** (port 6379) - Cache
- **OpenSearch** (port 9200) - Search engine
- **Dashboards** (port 5601) - Search visualization

### 4️⃣ Activate Virtual Environment

```bash
venv\Scripts\activate.bat
```

### 5️⃣ Run Application

```bash
uvicorn main:app --reload
```

✅ App is now running at **http://localhost:8000**

---

## 📚 API Documentation

Interactive Swagger UI: **http://localhost:8000/docs**

### 🔍 Search Endpoint

```http
GET /api/search?query=constitution&limit=10
```

**Parameters:**

- `query` (required): Search term (min 1, max 500 chars)
- `limit` (optional): Max results (default: 10, max: 100)
- `Authorization` (optional): Bearer token

**Response:**

```json
{
  "query": "constitution",
  "total_results": 3,
  "results": [
    {
      "case_id": "case_001",
      "title": "State of Karnataka v. Rishikesh",
      "court": "Supreme Court of India",
      "year": 2015,
      "judge": "Justice R.K. Agarwal",
      "relevance_score": 0.95,
      "summary": "Constitutional validity of right to privacy...",
      "case_number": "Civil Appeal No. 5555"
    }
  ],
  "search_time_ms": 12.5,
  "timestamp": "2024-03-01T10:30:00"
}
```

### 🔐 Authentication

**Login:**

```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123"}'
```

**Response:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Login successful"
}
```

**Use token in searches:**

```bash
curl -X GET "http://localhost:8000/api/search?query=privacy" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## 📁 Project Structure

```
AllLegal/
├── main.py                          # FastAPI app entry point
├── requirements.txt                 # Dependencies
├── .env                            # Configuration (update with Supabase keys)
├── docker-compose.yml              # Services definition
├── setup.bat / setup.sh            # Setup scripts
│
├── app/
│   ├── core/
│   │   ├── config.py              # Type-safe Pydantic settings
│   │   └── __init__.py
│   │
│   ├── services/
│   │   ├── supabase.py            # Supabase client (auth, database)
│   │   ├── opensearch.py          # OpenSearch client (search)
│   │   ├── pdf.py                 # PDF text extraction
│   │   └── __init__.py
│   │
│   ├── schemas/
│   │   ├── schemas.py             # Pydantic models (type safety)
│   │   └── __init__.py
│   │
│   ├── api/
│   │   └── routes/
│   │       ├── search.py          # /api/search endpoint
│   │       ├── auth.py            # /api/auth endpoints
│   │       └── __init__.py
│   │
│   └── __init__.py
│
├── logs/                           # Application logs
└── uploads/                        # Uploaded PDF files
```

---

## 🔑 Key Features

### ✅ Type Safety Everywhere

**Example 1: Configuration**

```python
from app.core.config import settings
opensearch_host: str = settings.OPENSEARCH_HOST  # Fully typed
```

**Example 2: API Response**

```python
@router.get("/api/search", response_model=SearchResponse)
async def search(...) -> SearchResponse:
    # Return type must match SearchResponse schema
```

**Example 3: Service Method**

```python
def search(self, query: str, limit: int = 10) -> Tuple[List[Dict], float]:
    # Types checked for parameters and return value
```

### 🔐 Supabase Integration

- **Authentication**: JWT tokens via Supabase Auth
- **Database**: Cases and search logs stored in PostgreSQL
- **Type Safety**: All database operations type-checked

### 🚀 Production Ready

- ✅ Comprehensive logging with timestamps
- ✅ Error handling and validation
- ✅ CORS support for frontend
- ✅ Health check endpoints
- ✅ Docker containerization
- ✅ Environment-based configuration

### 📊 Current Status

**Implemented:**

- ✅ FastAPI project structure
- ✅ Supabase authentication endpoints
- ✅ `/api/search` with **hardcoded mock data** (3 test cases)
- ✅ Type-safe schemas and responses
- ✅ Docker dev environment
- ✅ Comprehensive logging

**Next Phase (TODO):**

- 🔄 Replace mock data with real OpenSearch search
- 📄 Add `/api/upload` endpoint for PDF files
- 🔄 Extract metadata from uploaded PDFs
- 📊 Implement case indexing in OpenSearch
- 💾 Store extracted cases in Supabase
- 🧪 Add test suite

---

## 🧪 Testing Search Endpoint

### Test with cURL

```bash
# Basic search
curl "http://localhost:8000/api/search?query=constitution"

# With limit
curl "http://localhost:8000/api/search?query=privacy&limit=5"

# View API docs
curl "http://localhost:8000/docs"
```

### Current Response (Mock Data)

The `/api/search` endpoint currently returns **3 hardcoded legal cases**:

1. **State of Karnataka v. Rishikesh** (2015)
   - Court: Supreme Court of India
   - Judge: Justice R.K. Agarwal
   - Score: 0.95

2. **Right to Information v. Government of India** (2018)
   - Court: High Court of Delhi
   - Judge: Justice Manmohan
   - Score: 0.87

3. **Constitutional Rights - Fundamental Rights Case** (2020)
   - Court: Supreme Court of India
   - Judge: Justice D.Y. Chandrachud
   - Score: 0.92

---

## 🛠️ Troubleshooting

### Port Already in Use

```bash
# Kill process using port 8000 (Windows)
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Supabase Connection Error

```bash
# Check .env credentials
# Verify network connectivity
# Check Supabase project is active
```

### OpenSearch Not Starting

```bash
# Increase Docker memory: Settings → Resources → Memory (2GB+)
# Check Docker logs: docker-compose logs opensearch
```

### Package Installation Issues

```bash
# Clear pip cache and reinstall
pip cache purge
pip install -r requirements.txt --force-reinstall
```

---

## 📖 Understanding the Code

### 1. **main.py** - Application Entry Point

```python
from fastapi import FastAPI
app = FastAPI(...)  # Create app
app.include_router(search.router, prefix="/api")  # Add routes
```

### 2. **app/core/config.py** - Type-Safe Settings

```python
class Settings(BaseSettings):
    SUPABASE_URL: str  # Must be string
    OPENSEARCH_PORT: int  # Must be integer
    CORS_ORIGINS: List[str]  # Must be list of strings
```

### 3. **app/services/supabase.py** - Database Operations

```python
def verify_token(self, token: str) -> Optional[Dict]:
    # Verify JWT and return user info
```

### 4. **app/api/routes/search.py** - Search Endpoint

```python
@router.get("/search")
async def search(query: str) -> SearchResponse:
    # Returns 3 mock cases (will be real OpenSearch results)
```

---

## 📊 Logging

Logs are automatically created in `logs/` directory:

```
logs/
├── app.log           # All application events
└── errors.log        # Errors and warnings
```

Log format includes: `timestamp | level | module | message`

---

## 🎓 For Beginners

### What is FastAPI?

- Modern Python web framework for building APIs
- Automatic documentation generation
- Type safety with Pydantic
- Very fast performance

### What is Supabase?

- Open-source Firebase alternative
- Provides PostgreSQL database
- Built-in authentication (Auth)
- Real-time capabilities

### What is OpenSearch?

- Open-source search engine (based on Elasticsearch)
- Full-text search capabilities
- Boolean operators (AND, OR, NOT)
- Fuzzy matching for typos

### What is Type Safety?

- Ensures variables have correct types
- Catches errors before runtime
- Makes code self-documenting
- Better IDE support

---

## 🚀 Next Steps

1. **Get Supabase account** → Update `.env` credentials
2. **Run setup** → `setup.bat`
3. **Start services** → `docker-compose up`
4. **Test API** → http://localhost:8000/docs
5. **Replace mock data** → Integrate real OpenSearch
6. **Add PDF upload** → Implement metadata extraction
7. **Deploy** → Prepare for production

---

## 📞 Support

- **API Docs**: http://localhost:8000/docs
- **Supabase Docs**: https://supabase.com/docs
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **OpenSearch Docs**: https://opensearch.org/docs

## 📝 License

MIT - Feel free to use and modify

---

**Created:** March 1, 2026  
**Status:** 🟡 In Active Development  
**Version:** 1.0.0 (Beta)
