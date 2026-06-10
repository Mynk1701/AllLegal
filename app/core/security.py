from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
import jwt
from jwt import PyJWKClient
import logging

# Set up logging for this specific module
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("security_logger")

security = HTTPBearer()

# The JWKS endpoint for your Supabase project
jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
logger.info(f"🔍 Security Init: JWKS URL is {jwks_url}")

# We pass the anon key in headers if the endpoint is private
jwks_client = PyJWKClient(jwks_url, headers={"apikey": settings.SUPABASE_ANON_KEY})

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Validates a Supabase JWT token using JWKS with enhanced logging.
    """
    token = credentials.credentials
    logger.debug(f"🔑 Received token prefix: {token[:15]}...")
    
    try:
        # 1. Fetching Key
        logger.debug("🔄 Fetching signing key from JWKS...")
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        logger.debug("✅ Signing key fetched successfully.")
        
        # 2. Decoding
        logger.debug("🔄 Decoding JWT...")
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"], 
            audience="authenticated"
        )
        logger.info(f"✅ JWT validated for user: {payload.get('sub')}")
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.error("⏰ Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except Exception as e:
        logger.error(f"❌ AUTH_DEBUG_FAIL: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )
