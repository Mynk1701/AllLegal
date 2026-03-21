"""
Type-safe Pydantic schemas for API requests and responses.
Provides automatic validation and documentation.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# ==================== Case Schemas ====================

class CaseResponse(BaseModel):
    """Schema for a single legal case in search results"""
    case_id: str = Field(..., description="Unique case identifier")
    title: str = Field(..., min_length=1, max_length=500, description="Case title")
    court: str = Field(..., description="Court name (e.g., Supreme Court)")
    year: int = Field(..., ge=1950, le=2100, description="Year of judgment")
    judge: Optional[str] = Field(None, description="Judge name")
    summary: Optional[str] = Field(None, description="Case summary")
    case_number: Optional[str] = Field(None, description="Official case number")
    relevance_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Search relevance score (0-1)"
    )
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "case_id": "case_001",
                "title": "State of Karnataka v. Rishikesh",
                "court": "Supreme Court of India",
                "year": 2015,
                "judge": "Justice R.K. Agarwal",
                "relevance_score": 0.95,
                "summary": "Constitutional validity of right to privacy",
                "case_number": "Civil Appeal No. 5555"
            }
        }

class SearchResponse(BaseModel):
    """Schema for search API response"""
    query: str = Field(..., description="Search query that was executed")
    total_results: int = Field(..., ge=0, description="Total number of results found")
    results: List[CaseResponse] = Field(default_factory=list, description="List of matching cases")
    search_time_ms: float = Field(..., description="Search execution time in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "constitution",
                "total_results": 3,
                "results": [],
                "search_time_ms": 12.5,
                "timestamp": "2024-03-01T10:30:00"
            }
        }

# ==================== Authentication Schemas ====================

class LoginRequest(BaseModel):
    """Schema for login request"""
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password")

class SignUpRequest(BaseModel):
    """Schema for sign up request"""
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password")

class AuthResponse(BaseModel):
    """Schema for authentication response"""
    access_token: str = Field(..., description="JWT access token")
    user_id: str = Field(..., description="User ID")
    message: str = Field(default="Authentication successful")

# ==================== Error Response ====================

class ErrorResponse(BaseModel):
    """Schema for error responses"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Error details")
    status_code: int = Field(...)
