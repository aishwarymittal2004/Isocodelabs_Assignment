import os
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timedelta, timezone
from typing import Annotated
import jwt
from jwt import InvalidTokenError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import secrets
import hashlib
import base64
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./sitepilot_dev.db')
JWT_SECRET = os.getenv('JWT_SECRET', '')
# Use the same APP_ENV variable as the CORS layer (ENVIRONMENT kept for legacy compatibility).
ENVIRONMENT = os.getenv('APP_ENV', os.getenv('ENVIRONMENT', 'development')).lower()
if ENVIRONMENT == 'production':
    if not DATABASE_URL.startswith(('postgresql+psycopg://', 'postgresql://')):
        raise RuntimeError('A PostgreSQL DATABASE_URL is required in production')
    if len(JWT_SECRET) < 32:
        raise RuntimeError('JWT_SECRET must contain at least 32 characters in production')
if not JWT_SECRET:
    # Development only. Set a stable secret explicitly when testing browser sessions.
    JWT_SECRET = 'local-development-only-change-this-secret-before-deploy'
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
class PasswordHasher:
    def hash(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600_000)
        return 'pbkdf2_sha256$600000$'+base64.urlsafe_b64encode(salt).decode()+'$'+base64.urlsafe_b64encode(hashed).decode()
    def verify(self, password: str, stored: str) -> bool:
        try:
            algorithm, iterations, salt, digest = stored.split('$')
            if algorithm != 'pbkdf2_sha256': return False
            actual = hashlib.pbkdf2_hmac('sha256', password.encode(), base64.urlsafe_b64decode(salt), int(iterations))
            return secrets.compare_digest(actual, base64.urlsafe_b64decode(digest))
        except (ValueError, TypeError):
            return False
password_hasher = PasswordHasher()

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as db:
        yield db

def now():
    return datetime.now(timezone.utc)

def make_token(subject: str, role: str, minutes: int = 120):
    return jwt.encode({'sub': subject, 'role': role, 'exp': now()+timedelta(minutes=minutes), 'iat': now()}, JWT_SECRET, algorithm='HS256')

bearer = HTTPBearer(auto_error=False)

def require_role(role: str):
    def dependency(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        if credentials is None:
            raise HTTPException(401, 'Authentication required', headers={'WWW-Authenticate': 'Bearer'})
        try:
            payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=['HS256'])
        except InvalidTokenError:
            raise HTTPException(401, 'Invalid or expired token')
        if payload.get('role') != role or not payload.get('sub'):
            raise HTTPException(403, 'Not permitted')
        return payload['sub']
    return dependency

buyer = require_role('buyer')
sales = require_role('sales')
