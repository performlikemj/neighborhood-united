# Chef services module - business logic for chef CRM functionality
from .client_insights import (
    get_dashboard_summary,
    get_client_stats,
    get_client_list_with_stats,
    get_revenue_breakdown,
    get_upcoming_orders,
)
from .proactive_insights import (
    generate_chef_insights,
    save_insights,
    expire_old_insights,
    get_insights_for_chef,
)
from .memory_service import (
    EmbeddingService,
    MemoryService,
    ContextAssemblyService,
    MemoryExtractionService,
)

__all__ = [
    # Client insights
    'get_dashboard_summary',
    'get_client_stats',
    'get_client_list_with_stats',
    'get_revenue_breakdown',
    'get_upcoming_orders',
    # Proactive insights
    'generate_chef_insights',
    'save_insights',
    'expire_old_insights',
    'get_insights_for_chef',
    # Memory service
    'EmbeddingService',
    'MemoryService',
    'ContextAssemblyService',
    'MemoryExtractionService',
]
