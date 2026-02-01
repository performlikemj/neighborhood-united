# chefs/models/__init__.py
"""
Chefs models package.

Re-exports all models for backward compatibility.
"""

# Import from parent to maintain backward compatibility
# The main models are still in chefs/models.py (parent directory)
# This subpackage is for new organized models

from .sous_chef_memory import (
    ChefWorkspace,
    ClientContext,
    SousChefUsage,
    hybrid_memory_search,
)

__all__ = [
    'ChefWorkspace',
    'ClientContext',
    'SousChefUsage',
    'hybrid_memory_search',
]
