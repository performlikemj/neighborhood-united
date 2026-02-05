# chefs/models/sous_chef_memory.py
"""
Sous Chef Memory System - OpenClaw-inspired persistent memory for chef assistants.

This module provides:
- ChefWorkspace: Per-chef personality, rules, and configuration (like SOUL.md + AGENTS.md)
- ChefMemory: Long-term memory entries with vector embeddings for semantic search
- ClientContext: Per-client notes and preferences
- MemorySearchMixin: Hybrid BM25 + vector search

Design inspired by OpenClaw's memory architecture:
- Workspace files = personality + rules (injected into every conversation)
- Memory = searchable long-term storage (vector + keyword)
- Client context = per-client preferences (like USER.md per client)
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from pgvector.django import VectorField, CosineDistance
from django.db.models import F, Q

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CHEF WORKSPACE (Personality + Rules)
# ═══════════════════════════════════════════════════════════════════════════════

class ChefWorkspace(models.Model):
    """
    Chef's workspace configuration - injected into every Sous Chef conversation.
    
    Like OpenClaw's SOUL.md + AGENTS.md + TOOLS.md, this defines:
    - Personality/tone for the assistant
    - Business rules and constraints
    - Enabled tools and preferences
    """
    chef = models.OneToOneField(
        'chefs.Chef',
        on_delete=models.CASCADE,
        related_name='workspace'
    )
    
    # Personality (like SOUL.md)
    soul_prompt = models.TextField(
        blank=True,
        default='',
        help_text="Sous Chef personality, tone, and communication style"
    )
    
    # Business rules (like AGENTS.md operating instructions)
    business_rules = models.TextField(
        blank=True,
        default='',
        help_text="Operating constraints: hours, pricing, policies, boundaries"
    )
    
    # Tool configuration
    enabled_tools = models.JSONField(
        default=list,
        blank=True,
        help_text="List of tool names the chef has enabled"
    )
    
    tool_preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="Per-tool configuration overrides"
    )
    
    # Context preferences
    include_analytics = models.BooleanField(
        default=True,
        help_text="Include business analytics in context"
    )
    include_seasonal = models.BooleanField(
        default=True,
        help_text="Include seasonal ingredient suggestions"
    )
    auto_memory_save = models.BooleanField(
        default=True,
        help_text="Automatically save important insights to memory"
    )
    
    # Chef Profile
    chef_nickname = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="How Sous Chef addresses the chef (e.g., 'Chef Marcus', 'Marcus')"
    )
    
    chef_specialties = models.JSONField(
        default=list,
        blank=True,
        help_text="Chef's specialties: ['comfort', 'meal-prep', 'health']"
    )
    
    sous_chef_name = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Custom name for the assistant (default: 'Sous Chef')"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'chefs'
        verbose_name = 'Chef Workspace'
        verbose_name_plural = 'Chef Workspaces'
    
    def __str__(self):
        return f"Workspace for Chef #{self.chef_id}"
    
    def get_system_context(self) -> str:
        """
        Build the system context to inject into conversations.
        Returns a formatted string combining soul + rules.
        """
        parts = []
        
        if self.soul_prompt:
            parts.append(f"## Assistant Personality\n{self.soul_prompt}")
        
        if self.business_rules:
            parts.append(f"## Business Rules & Constraints\n{self.business_rules}")
        
        return "\n\n".join(parts) if parts else ""
    
    @classmethod
    def get_or_create_for_chef(cls, chef) -> 'ChefWorkspace':
        """Get or create workspace with sensible defaults."""
        workspace, created = cls.objects.get_or_create(
            chef=chef,
            defaults={
                'soul_prompt': cls.get_default_soul_prompt(),
                'business_rules': '',
                'enabled_tools': cls.get_default_tools(),
            }
        )
        return workspace
    
    @staticmethod
    def get_default_soul_prompt() -> str:
        return """You are Sous Chef, a knowledgeable culinary assistant helping this chef serve their clients better.

Tone: Professional but warm. You're a trusted kitchen partner, not a corporate bot.

Guidelines:
- Be concise but thorough when discussing dietary needs or safety
- Proactively mention relevant client preferences you remember
- Ask clarifying questions rather than making assumptions
- When suggesting dishes, consider the client's history and preferences
- Flag potential allergen issues immediately and clearly"""
    
    @staticmethod
    def get_default_tools() -> List[str]:
        return [
            'get_family_dietary_summary',
            'check_recipe_compliance', 
            'suggest_family_menu',
            'search_chef_dishes',
            'suggest_ingredient_substitution',
            'get_chef_analytics',
            'get_seasonal_ingredients',
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# HYBRID MEMORY SEARCH (Works with existing ChefMemory in customer_dashboard)
# ═══════════════════════════════════════════════════════════════════════════════

def hybrid_memory_search(
    chef,
    query: str,
    query_embedding: Optional[List[float]] = None,
    memory_types: Optional[List[str]] = None,
    client=None,
    lead=None,
    limit: int = 10,
    vector_weight: float = 0.7,
    text_weight: float = 0.3,
    min_score: float = 0.1,
) -> List[Tuple[Any, float]]:
    """
    Hybrid search combining vector similarity and full-text search.
    
    Uses the existing ChefMemory model from customer_dashboard, with optional
    embedding field for vector search.
    
    Args:
        chef: Chef instance to search memories for
        query: Search query text
        query_embedding: Pre-computed embedding vector (optional)
        memory_types: Filter by memory type(s)
        client: Filter by specific client
        lead: Filter by specific lead
        limit: Maximum results to return
        vector_weight: Weight for vector similarity (0-1)
        text_weight: Weight for text/BM25 similarity (0-1)
        min_score: Minimum combined score threshold
        
    Returns:
        List of (ChefMemory, score) tuples sorted by score descending
    """
    from customer_dashboard.models import ChefMemory
    from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
    from pgvector.django import CosineDistance
    
    # Base queryset
    qs = ChefMemory.objects.filter(chef=chef, is_active=True)
    
    if memory_types:
        qs = qs.filter(memory_type__in=memory_types)
    if client:
        qs = qs.filter(customer=client)
    if lead:
        qs = qs.filter(lead=lead)
    
    results = []
    
    # Vector search (if embedding available and model has embedding field)
    vector_scores = {}
    if query_embedding:
        try:
            vector_qs = qs.filter(embedding__isnull=False).annotate(
                vector_distance=CosineDistance(F('embedding'), query_embedding)
            ).values('id', 'vector_distance')
            
            for row in vector_qs:
                # Convert distance to similarity (1 - distance)
                vector_scores[row['id']] = max(0, 1 - row['vector_distance'])
        except Exception as e:
            # Embedding field might not exist yet - fall back to text-only
            logger.debug(f"Vector search not available: {e}")
    
    # Full-text search (BM25-style via PostgreSQL)
    text_scores = {}
    if query:
        try:
            search_vector = SearchVector('content', weight='A')
            search_query = SearchQuery(query, search_type='websearch')
            
            text_qs = qs.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(search=search_query).values('id', 'rank')
            
            # Normalize ranks to 0-1 range
            ranks = list(text_qs)
            max_rank = max((row['rank'] for row in ranks), default=1) or 1
            for row in ranks:
                text_scores[row['id']] = row['rank'] / max_rank
        except Exception as e:
            # Fall back to simple icontains search
            logger.debug(f"Full-text search not available, using fallback: {e}")
            fallback_qs = qs.filter(content__icontains=query).values('id')
            for row in fallback_qs:
                text_scores[row['id']] = 0.5  # Default score for fallback matches
    
    # Combine scores
    all_ids = set(vector_scores.keys()) | set(text_scores.keys())
    combined_scores = {}
    
    # If no vector scores, weight text fully
    if not vector_scores:
        vector_weight = 0
        text_weight = 1
    
    for mem_id in all_ids:
        v_score = vector_scores.get(mem_id, 0)
        t_score = text_scores.get(mem_id, 0)
        combined = (vector_weight * v_score) + (text_weight * t_score)
        if combined >= min_score:
            combined_scores[mem_id] = combined
    
    # Sort and fetch full objects
    sorted_ids = sorted(combined_scores.keys(), key=lambda x: combined_scores[x], reverse=True)[:limit]
    
    if sorted_ids:
        memories = {m.id: m for m in qs.filter(id__in=sorted_ids)}
        results = [(memories[mid], combined_scores[mid]) for mid in sorted_ids if mid in memories]
    
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENT CONTEXT (Per-client Preferences)
# ═══════════════════════════════════════════════════════════════════════════════

class ClientContext(models.Model):
    """
    Per-client context notes for a chef - like a mini USER.md per client.
    
    Stores structured + unstructured preferences that get injected when
    the chef is discussing this particular client.
    """
    chef = models.ForeignKey(
        'chefs.Chef',
        on_delete=models.CASCADE,
        related_name='client_contexts'
    )
    
    # Either a platform customer OR a CRM lead
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='chef_contexts'
    )
    lead = models.ForeignKey(
        'crm.Lead',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='chef_contexts'
    )
    
    # Quick reference notes
    nickname = models.CharField(
        max_length=100,
        blank=True,
        help_text="How chef refers to this client"
    )
    summary = models.TextField(
        blank=True,
        help_text="Quick summary of this client (auto-generated or manual)"
    )
    
    # Structured preferences
    cuisine_preferences = models.JSONField(
        default=list,
        blank=True,
        help_text="Preferred cuisines/styles"
    )
    flavor_profile = models.JSONField(
        default=dict,
        blank=True,
        help_text="Flavor preferences: spicy, sweet, etc."
    )
    cooking_notes = models.TextField(
        blank=True,
        help_text="Notes on cooking for this client"
    )
    
    # Communication preferences
    communication_style = models.CharField(
        max_length=50,
        blank=True,
        help_text="How client prefers to communicate"
    )
    special_occasions = models.JSONField(
        default=list,
        blank=True,
        help_text="Birthdays, anniversaries, etc."
    )
    
    # Service history summary
    total_orders = models.PositiveIntegerField(default=0)
    total_spent_cents = models.PositiveIntegerField(default=0)
    first_order_date = models.DateField(null=True, blank=True)
    last_order_date = models.DateField(null=True, blank=True)
    
    # Embedding for client profile
    profile_embedding = VectorField(
        dimensions=1536,
        null=True,
        blank=True,
        help_text="Embedding of client preferences for similarity matching"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'chefs'
        verbose_name = 'Client Context'
        verbose_name_plural = 'Client Contexts'
        unique_together = [
            ('chef', 'client'),
            ('chef', 'lead'),
        ]
        indexes = [
            models.Index(fields=['chef', 'client']),
            models.Index(fields=['chef', 'lead']),
        ]
    
    def __str__(self):
        client_name = self.get_client_name()
        return f"Context for {client_name} (chef_id={self.chef_id})"
    
    def get_client_name(self) -> str:
        """Get display name for the client."""
        if self.nickname:
            return self.nickname
        if self.client:
            return self.client.get_full_name() or self.client.username
        if self.lead:
            return f"{self.lead.first_name} {self.lead.last_name}".strip()
        return "Unknown"
    
    def get_context_prompt(self) -> str:
        """
        Build context string to inject when discussing this client.
        """
        parts = [f"## Client: {self.get_client_name()}"]
        
        if self.summary:
            parts.append(self.summary)
        
        if self.cuisine_preferences:
            prefs = ", ".join(self.cuisine_preferences)
            parts.append(f"**Cuisine preferences:** {prefs}")
        
        if self.flavor_profile:
            flavors = ", ".join(f"{k}: {v}" for k, v in self.flavor_profile.items())
            parts.append(f"**Flavor profile:** {flavors}")
        
        if self.cooking_notes:
            parts.append(f"**Cooking notes:** {self.cooking_notes}")
        
        if self.special_occasions:
            occasions = "; ".join(
                f"{o.get('name', 'Event')}: {o.get('date', 'TBD')}" 
                for o in self.special_occasions
            )
            parts.append(f"**Special occasions:** {occasions}")
        
        if self.total_orders > 0:
            parts.append(f"**Order history:** {self.total_orders} orders, ${self.total_spent_cents/100:.2f} total")
        
        return "\n".join(parts)
    
    @classmethod
    def get_or_create_for_client(cls, chef, client=None, lead=None) -> 'ClientContext':
        """Get or create context for a specific client."""
        if client:
            context, _ = cls.objects.get_or_create(chef=chef, client=client)
        elif lead:
            context, _ = cls.objects.get_or_create(chef=chef, lead=lead)
        else:
            raise ValueError("Must provide either client or lead")
        return context


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION TRACKING (Token Usage)
# ═══════════════════════════════════════════════════════════════════════════════

class SousChefUsage(models.Model):
    """
    Track token usage per chef for cost management.
    
    Aggregates daily usage to help chefs understand their AI costs.
    """
    chef = models.ForeignKey(
        'chefs.Chef',
        on_delete=models.CASCADE,
        related_name='sous_chef_usage'
    )
    date = models.DateField()
    
    # Token counts
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    
    # Breakdown by feature
    conversation_tokens = models.PositiveIntegerField(default=0)
    memory_search_tokens = models.PositiveIntegerField(default=0)
    embedding_tokens = models.PositiveIntegerField(default=0)
    
    # Request counts
    request_count = models.PositiveIntegerField(default=0)
    tool_call_count = models.PositiveIntegerField(default=0)
    memory_saves = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'chefs'
        unique_together = ('chef', 'date')
        ordering = ['-date']
        indexes = [
            models.Index(fields=['chef', '-date']),
        ]
    
    def __str__(self):
        total = self.input_tokens + self.output_tokens
        return f"Usage for chef {self.chef_id} on {self.date}: {total} tokens"
    
    @classmethod
    def record_usage(
        cls,
        chef,
        input_tokens: int = 0,
        output_tokens: int = 0,
        feature: str = 'conversation',
        tool_calls: int = 0,
        memory_save: bool = False,
    ):
        """Record token usage for today."""
        today = timezone.now().date()
        usage, _ = cls.objects.get_or_create(chef=chef, date=today)
        
        usage.input_tokens += input_tokens
        usage.output_tokens += output_tokens
        usage.request_count += 1
        usage.tool_call_count += tool_calls
        
        if memory_save:
            usage.memory_saves += 1
        
        # Track by feature
        feature_tokens = input_tokens + output_tokens
        if feature == 'conversation':
            usage.conversation_tokens += feature_tokens
        elif feature == 'memory_search':
            usage.memory_search_tokens += feature_tokens
        elif feature == 'embedding':
            usage.embedding_tokens += feature_tokens
        
        usage.save()
        return usage
    
    @classmethod
    def get_monthly_summary(cls, chef, year: int, month: int) -> Dict[str, Any]:
        """Get usage summary for a month."""
        from django.db.models import Sum
        
        usage = cls.objects.filter(
            chef=chef,
            date__year=year,
            date__month=month
        ).aggregate(
            total_input=Sum('input_tokens'),
            total_output=Sum('output_tokens'),
            total_requests=Sum('request_count'),
            total_tool_calls=Sum('tool_call_count'),
            total_memory_saves=Sum('memory_saves'),
        )
        
        return {
            'year': year,
            'month': month,
            'input_tokens': usage['total_input'] or 0,
            'output_tokens': usage['total_output'] or 0,
            'total_tokens': (usage['total_input'] or 0) + (usage['total_output'] or 0),
            'requests': usage['total_requests'] or 0,
            'tool_calls': usage['total_tool_calls'] or 0,
            'memory_saves': usage['total_memory_saves'] or 0,
        }
