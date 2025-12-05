# Chef CRM Dashboard API
# This module provides the backend API for the chef dashboard and CRM functionality.

from . import waitlist
from . import dashboard
from . import clients
from . import analytics
from . import leads
from . import serializers
from . import sous_chef
from . import availability

__all__ = [
    'waitlist',
    'dashboard',
    'clients',
    'analytics',
    'leads',
    'serializers',
    'sous_chef',
    'availability',
]


