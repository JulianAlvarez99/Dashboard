"""
Authentication utilities for password verification and user validation
"""

from typing import Optional, Dict, Any
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.global_models import User, Tenant


# Initialize Argon2 password hasher with configured parameters
ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
    salt_len=16
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its Argon2 hash.
    
    Args:
        plain_password: The plaintext password to verify
        hashed_password: The Argon2 hash from the database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        ph.verify(hashed_password, plain_password)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2.
    
    Args:
        password: The plaintext password to hash
        
    Returns:
        The Argon2 hash string
    """
    return ph.hash(password)


def authenticate_user(db: Session, username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user against the global database.
    
    Args:
        db: SQLAlchemy session connected to camet_global
        username: Username to authenticate
        password: Plaintext password
        
    Returns:
        Dictionary with user info if authenticated, None if failed
        {
            'user_id': int,
            'username': str,
            'email': str,
            'tenant_id': int,
            'role': str,
            'permissions': dict,
            'tenant_info': {
                'company_name': str,
                'config': dict
            }
        }
    """
    try:
        # Query user with tenant info in a single query (eager loading)
        stmt = (
            select(User, Tenant)
            .join(Tenant, User.tenant_id == Tenant.tenant_id)
            .where(User.username == username)
        )
        result = db.execute(stmt).first()
        
        if not result:
            # User not found
            return None
        
        user, tenant = result
        
        # Check if tenant is active
        if not tenant.is_active:
            return None
        
        # Verify password
        if not verify_password(password, user.password):
            return None
        
        # Return user info with tenant details
        return {
            'user_id': user.user_id,
            'username': user.username,
            'email': user.email,
            'tenant_id': user.tenant_id,
            'role': user.role,
            'permissions': user.permissions or {},
            'tenant_info': {
                'company_name': tenant.company_name,
                'config': tenant.config_tenant
            }
        }
        
    except Exception as e:
        # Log the error in production
        print(f"Authentication error: {e}")
        return None


def get_user_by_id(db: Session, user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get user information by user_id (for session validation).
    
    Args:
        db: SQLAlchemy session connected to camet_global
        user_id: User ID to look up
        
    Returns:
        Dictionary with user info if found, None otherwise
    """
    try:
        stmt = (
            select(User, Tenant)
            .join(Tenant, User.tenant_id == Tenant.tenant_id)
            .where(User.user_id == user_id)
        )
        result = db.execute(stmt).first()
        
        if not result:
            return None
        
        user, tenant = result
        
        if not tenant.is_active:
            return None
        
        return {
            'user_id': user.user_id,
            'username': user.username,
            'email': user.email,
            'tenant_id': user.tenant_id,
            'role': user.role,
            'permissions': user.permissions or {},
            'tenant_info': {
                'company_name': tenant.company_name,
                'config': tenant.config_tenant
            }
        }
        
    except Exception as e:
        print(f"User lookup error: {e}")
        return None
