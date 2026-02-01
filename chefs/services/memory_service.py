# chefs/services/memory_service.py
"""
Sous Chef Memory Service - Embedding, search, and context assembly.

This service provides:
- Embedding generation via OpenAI
- Hybrid search (vector + full-text)
- Context assembly for conversations
- Auto-extraction of memories from conversations
"""

import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone
from django.db.models import Q

from openai import OpenAI

logger = logging.getLogger(__name__)

# Initialize OpenAI client
_openai_client = None

def get_openai_client() -> OpenAI:
    """Get or create OpenAI client."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


# ═══════════════════════════════════════════════════════════════════════════════
# EMBEDDING SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class EmbeddingService:
    """Generate and manage embeddings for memory entries."""
    
    MODEL = "text-embedding-3-small"
    DIMENSIONS = 1536
    
    @classmethod
    def get_embedding(cls, text: str) -> Optional[List[float]]:
        """
        Generate embedding for text.
        
        Returns None if embedding fails.
        """
        if not text or not text.strip():
            return None
        
        try:
            client = get_openai_client()
            response = client.embeddings.create(
                model=cls.MODEL,
                input=text[:8000],  # Truncate to model limit
                dimensions=cls.DIMENSIONS
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None
    
    @classmethod
    def get_embeddings_batch(cls, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts in one API call.
        
        More efficient for bulk operations.
        """
        if not texts:
            return []
        
        try:
            client = get_openai_client()
            # Truncate each text
            truncated = [t[:8000] if t else "" for t in texts]
            
            response = client.embeddings.create(
                model=cls.MODEL,
                input=truncated,
                dimensions=cls.DIMENSIONS
            )
            
            # Map back by index
            embeddings = [None] * len(texts)
            for item in response.data:
                embeddings[item.index] = item.embedding
            
            return embeddings
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            return [None] * len(texts)


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryService:
    """
    Core memory operations for Sous Chef.
    
    Handles creation, search, and retrieval of chef memories.
    Uses the existing ChefMemory model from customer_dashboard.
    """
    
    @classmethod
    def save_memory(
        cls,
        chef,
        content: str,
        memory_type: str = "lesson",
        importance: int = 3,
        client=None,
        lead=None,
        context: Dict[str, Any] = None,
        generate_embedding: bool = True,
    ):
        """
        Save a new memory entry with optional embedding.
        
        Args:
            chef: Chef instance
            content: Memory content
            memory_type: Type classification (pattern, preference, lesson, todo)
            importance: 1-5 importance level
            client: Associated platform client
            lead: Associated CRM lead
            context: Additional metadata
            generate_embedding: Whether to generate embedding
            
        Returns:
            ChefMemory instance
        """
        from customer_dashboard.models import ChefMemory
        
        # Clamp values
        importance = max(1, min(5, importance))
        content = content[:1000]  # Model limit
        
        # Build context metadata
        ctx = context or {}
        ctx.setdefault("source", "memory_service")
        
        # Generate embedding if requested
        embedding = None
        if generate_embedding:
            embedding = EmbeddingService.get_embedding(content)
        
        memory_kwargs = {
            "chef": chef,
            "content": content,
            "memory_type": memory_type,
            "importance": importance,
            "context": ctx,
        }
        
        # Link to client if specified
        if client:
            memory_kwargs["customer"] = client
        if lead:
            memory_kwargs["lead"] = lead
        
        # Add embedding if available
        if embedding:
            memory_kwargs["embedding"] = embedding
        
        memory = ChefMemory.objects.create(**memory_kwargs)
        
        # Track usage
        try:
            from chefs.models import SousChefUsage
            if embedding:
                SousChefUsage.record_usage(
                    chef=chef,
                    input_tokens=len(content.split()) * 2,  # Rough estimate
                    feature='embedding',
                    memory_save=True,
                )
        except Exception as e:
            logger.debug(f"Usage tracking failed: {e}")
        
        logger.info(f"Saved memory for chef {chef.id}: {content[:50]}")
        return memory
    
    @classmethod
    def search_memories(
        cls,
        chef,
        query: str,
        memory_types: List[str] = None,
        client=None,
        lead=None,
        limit: int = 5,
    ) -> List[Tuple[Any, float]]:
        """
        Search chef's memories using hybrid search.
        
        Returns list of (memory, relevance_score) tuples.
        """
        from chefs.models import hybrid_memory_search
        
        # Generate query embedding
        query_embedding = EmbeddingService.get_embedding(query)
        
        # Use hybrid search
        results = hybrid_memory_search(
            chef=chef,
            query=query,
            query_embedding=query_embedding,
            memory_types=memory_types,
            client=client,
            lead=lead,
            limit=limit,
        )
        
        # Record access for returned memories
        for memory, _ in results:
            memory.mark_accessed()
        
        return results
    
    @classmethod
    def get_recent_memories(
        cls,
        chef,
        days: int = 7,
        limit: int = 10,
        memory_types: List[str] = None,
    ) -> List[Any]:
        """Get recently created memories."""
        from customer_dashboard.models import ChefMemory
        
        cutoff = timezone.now() - timedelta(days=days)
        qs = ChefMemory.objects.filter(
            chef=chef,
            is_active=True,
            created_at__gte=cutoff,
        )
        
        if memory_types:
            qs = qs.filter(memory_type__in=memory_types)
        
        return list(qs.order_by('-created_at')[:limit])
    
    @classmethod
    def get_client_memories(
        cls,
        chef,
        client=None,
        lead=None,
        limit: int = 10,
    ) -> List[Any]:
        """Get all memories about a specific client."""
        from customer_dashboard.models import ChefMemory
        
        qs = ChefMemory.objects.filter(chef=chef, is_active=True)
        
        if client:
            qs = qs.filter(customer=client)
        elif lead:
            qs = qs.filter(lead=lead)
        else:
            return []
        
        return list(qs.order_by('-importance', '-created_at')[:limit])


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT ASSEMBLY SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class ContextAssemblyService:
    """
    Build context for Sous Chef conversations.
    
    Like OpenClaw's system prompt assembly, this combines:
    - Chef workspace (soul + rules)
    - Client context (if discussing a specific client)
    - Relevant memories
    - Current state (analytics, seasonal, etc.)
    """
    
    @classmethod
    def build_system_context(
        cls,
        chef,
        client=None,
        lead=None,
        include_memories: bool = True,
        memory_query: str = None,
        include_analytics: bool = True,
        include_seasonal: bool = True,
        max_memory_chars: int = 2000,
    ) -> str:
        """
        Build complete system context for a Sous Chef conversation.
        
        Args:
            chef: Chef instance
            client: Platform client being discussed (optional)
            lead: CRM lead being discussed (optional)
            include_memories: Whether to include relevant memories
            memory_query: Query for memory search (if None, uses client context)
            include_analytics: Include business analytics
            include_seasonal: Include seasonal ingredient suggestions
            max_memory_chars: Max characters for memory snippets
            
        Returns:
            Formatted system context string
        """
        from chefs.models import ChefWorkspace, ClientContext
        
        parts = []
        
        # 1. Workspace (soul + rules)
        workspace = ChefWorkspace.get_or_create_for_chef(chef)
        workspace_context = workspace.get_system_context()
        if workspace_context:
            parts.append(workspace_context)
        
        # 2. Client context (if discussing a specific client)
        if client or lead:
            try:
                client_ctx = ClientContext.get_or_create_for_client(
                    chef=chef, 
                    client=client, 
                    lead=lead
                )
                client_prompt = client_ctx.get_context_prompt()
                if client_prompt:
                    parts.append(client_prompt)
            except Exception as e:
                logger.warning(f"Failed to get client context: {e}")
        
        # 3. Relevant memories
        if include_memories:
            memories_section = cls._build_memories_section(
                chef=chef,
                client=client,
                lead=lead,
                query=memory_query,
                max_chars=max_memory_chars,
            )
            if memories_section:
                parts.append(memories_section)
        
        # 4. Analytics summary
        if include_analytics and workspace.include_analytics:
            analytics = cls._build_analytics_section(chef)
            if analytics:
                parts.append(analytics)
        
        # 5. Seasonal context
        if include_seasonal and workspace.include_seasonal:
            seasonal = cls._build_seasonal_section()
            if seasonal:
                parts.append(seasonal)
        
        # 6. Current date/time
        parts.append(f"## Current Time\n{timezone.now().strftime('%Y-%m-%d %H:%M %Z')}")
        
        return "\n\n---\n\n".join(parts)
    
    @classmethod
    def _build_memories_section(
        cls,
        chef,
        client=None,
        lead=None,
        query: str = None,
        max_chars: int = 2000,
    ) -> str:
        """Build the memories section of context."""
        memories = []
        seen_ids = set()
        
        # Get client-specific memories if applicable
        if client or lead:
            client_memories = MemoryService.get_client_memories(
                chef=chef,
                client=client,
                lead=lead,
                limit=5,
            )
            for m in client_memories:
                if m.id not in seen_ids:
                    memories.append(m)
                    seen_ids.add(m.id)
        
        # Search for relevant memories if query provided
        if query:
            search_results = MemoryService.search_memories(
                chef=chef,
                query=query,
                limit=5,
            )
            for m, _ in search_results:
                if m.id not in seen_ids:
                    memories.append(m)
                    seen_ids.add(m.id)
        
        if not memories:
            return ""
        
        # Build section with character limit
        parts = ["## Relevant Memories"]
        total_chars = 0
        
        for memory in memories[:10]:
            # Format memory snippet
            content = memory.content[:400]
            if len(memory.content) > 400:
                content += "..."
            
            type_label = dict(memory.MEMORY_TYPES).get(memory.memory_type, memory.memory_type)
            snippet = f"[{type_label}] {content}"
            
            if total_chars + len(snippet) > max_chars:
                break
            parts.append(f"- {snippet}")
            total_chars += len(snippet)
        
        return "\n".join(parts)
    
    @classmethod
    def _build_analytics_section(cls, chef) -> str:
        """Build quick analytics summary."""
        try:
            from meals.models import ChefMealOrder
            from django.db.models import Sum, Count
            from datetime import timedelta
            
            # Last 30 days stats
            cutoff = timezone.now() - timedelta(days=30)
            orders = ChefMealOrder.objects.filter(
                event__chef=chef,
                created_at__gte=cutoff,
            )
            
            stats = orders.aggregate(
                total_orders=Count('id'),
                total_revenue=Sum('total_price'),
            )
            
            if not stats['total_orders']:
                return ""
            
            return f"""## Quick Stats (Last 30 Days)
- Orders: {stats['total_orders']}
- Revenue: ${float(stats['total_revenue'] or 0):.2f}"""
            
        except Exception as e:
            logger.warning(f"Failed to build analytics: {e}")
            return ""
    
    @classmethod
    def _build_seasonal_section(cls) -> str:
        """Build seasonal ingredients context."""
        from meals.sous_chef_tools import SEASONAL_INGREDIENTS
        
        month = timezone.now().month
        month_name = timezone.now().strftime('%B')
        
        seasonal = SEASONAL_INGREDIENTS.get(month, {})
        if not seasonal:
            return ""
        
        highlights = []
        for category, items in list(seasonal.items())[:3]:
            if items:
                highlights.append(f"- {category.title()}: {', '.join(items[:5])}")
        
        if not highlights:
            return ""
        
        return f"""## Seasonal Highlights ({month_name})
{chr(10).join(highlights)}"""


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY EXTRACTION SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryExtractionService:
    """
    Auto-extract memories from conversations.
    
    Identifies important information to save for future reference.
    """
    
    # Patterns that indicate memory-worthy content
    MEMORY_TRIGGERS = [
        "remember",
        "note that",
        "important:",
        "allergic to",
        "doesn't like",
        "prefers",
        "loves",
        "hates",
        "birthday",
        "anniversary",
        "learned that",
        "discovered",
        "always",
        "never",
    ]
    
    @classmethod
    def should_extract_memories(cls, message: str) -> bool:
        """Check if a message might contain memory-worthy content."""
        lower = message.lower()
        return any(trigger in lower for trigger in cls.MEMORY_TRIGGERS)
    
    @classmethod
    def extract_memories_from_conversation(
        cls,
        chef,
        messages: List[Dict[str, str]],
        client=None,
        lead=None,
        source_thread=None,
    ) -> List[Any]:
        """
        Use LLM to extract memory-worthy insights from a conversation.
        
        Args:
            chef: Chef instance
            messages: Conversation messages
            client: Associated client
            lead: Associated lead
            source_thread: Source SousChefThread
            
        Returns:
            List of created ChefMemory instances
        """
        if not messages:
            return []
        
        # Build conversation text
        conversation = "\n".join([
            f"{m.get('role', 'unknown')}: {m.get('content', '')}"
            for m in messages[-20:]  # Last 20 messages
        ])
        
        # Check if worth extracting
        if not cls.should_extract_memories(conversation):
            return []
        
        try:
            client_api = get_openai_client()
            
            extraction_prompt = f"""Analyze this conversation between a chef and their AI assistant (Sous Chef).
Extract any important facts, preferences, or insights that should be remembered for future reference.

Focus on:
- Client dietary restrictions or allergies
- Food preferences (likes/dislikes)
- Special occasions (birthdays, anniversaries)
- Cooking preferences or instructions
- Important dates or deadlines
- Business learnings or patterns

Conversation:
{conversation}

Return a JSON array of memories to save. Each memory should have:
- "title": Brief title (max 100 chars)
- "content": Full content to remember
- "type": One of: client, business, recipe, preference, lesson, seasonal, general
- "tags": List of relevant tags

If there's nothing worth remembering, return an empty array: []

Return ONLY valid JSON, no other text."""

            response = client_api.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.3,
                max_tokens=1000,
            )
            
            import json
            memories_data = json.loads(response.choices[0].message.content)
            
            created_memories = []
            for mem_data in memories_data[:5]:  # Max 5 memories per extraction
                memory = MemoryService.save_memory(
                    chef=chef,
                    title=mem_data.get('title', ''),
                    content=mem_data.get('content', ''),
                    memory_type=mem_data.get('type', 'general'),
                    tags=mem_data.get('tags', []),
                    client=client,
                    lead=lead,
                    source_thread=source_thread,
                    auto_generated=True,
                )
                created_memories.append(memory)
            
            return created_memories
            
        except Exception as e:
            logger.error(f"Memory extraction failed: {e}")
            return []
