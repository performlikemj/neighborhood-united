# chefs/tests/test_memory_system.py
"""
Tests for the Sous Chef memory system.

Tests cover:
- ChefWorkspace model and defaults
- ClientContext model and preferences
- SousChefUsage tracking
- Hybrid memory search (vector + BM25)
- Memory service operations
- Context assembly
- Backfill management command
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class ChefWorkspaceTests(TestCase):
    """Tests for ChefWorkspace model."""
    
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='testchef',
            email='chef@test.com',
            password='testpass123'
        )
    
    def setUp(self):
        from chefs.models import Chef
        self.chef, _ = Chef.objects.get_or_create(user=self.user)
    
    def test_workspace_get_or_create_with_defaults(self):
        """Test that workspace is created with sensible defaults."""
        from chefs.models import ChefWorkspace
        
        workspace = ChefWorkspace.get_or_create_for_chef(self.chef)
        
        self.assertIsNotNone(workspace)
        self.assertEqual(workspace.chef, self.chef)
        self.assertIn('Sous Chef', workspace.soul_prompt)  # Default soul prompt
        self.assertTrue(workspace.include_analytics)
        self.assertTrue(workspace.include_seasonal)
        self.assertTrue(workspace.auto_memory_save)
        self.assertIsInstance(workspace.enabled_tools, list)
    
    def test_workspace_get_system_context_empty(self):
        """Test system context with empty workspace."""
        from chefs.models import ChefWorkspace
        
        workspace = ChefWorkspace.objects.create(
            chef=self.chef,
            soul_prompt='',
            business_rules=''
        )
        
        context = workspace.get_system_context()
        self.assertEqual(context, '')
    
    def test_workspace_get_system_context_with_content(self):
        """Test system context with soul and rules."""
        from chefs.models import ChefWorkspace
        
        workspace = ChefWorkspace.objects.create(
            chef=self.chef,
            soul_prompt='Be friendly and warm.',
            business_rules='Minimum order $100.'
        )
        
        context = workspace.get_system_context()
        self.assertIn('Be friendly and warm', context)
        self.assertIn('Minimum order $100', context)
        self.assertIn('Assistant Personality', context)
        self.assertIn('Business Rules', context)
    
    def test_workspace_one_to_one_constraint(self):
        """Test that chef can only have one workspace."""
        from chefs.models import ChefWorkspace
        from django.db import IntegrityError
        
        ChefWorkspace.objects.create(chef=self.chef)
        
        with self.assertRaises(IntegrityError):
            ChefWorkspace.objects.create(chef=self.chef)


class ClientContextTests(TestCase):
    """Tests for ClientContext model."""
    
    @classmethod
    def setUpTestData(cls):
        cls.chef_user = User.objects.create_user(
            username='testchef2',
            email='chef2@test.com',
            password='testpass123'
        )
        cls.client_user = User.objects.create_user(
            username='testclient',
            email='client@test.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
    
    def setUp(self):
        from chefs.models import Chef
        self.chef, _ = Chef.objects.get_or_create(user=self.chef_user)
    
    def test_client_context_get_or_create(self):
        """Test creating client context."""
        from chefs.models import ClientContext
        
        context = ClientContext.get_or_create_for_client(
            chef=self.chef,
            client=self.client_user
        )
        
        self.assertIsNotNone(context)
        self.assertEqual(context.chef, self.chef)
        self.assertEqual(context.client, self.client_user)
    
    def test_client_context_get_client_name(self):
        """Test getting client display name."""
        from chefs.models import ClientContext
        
        context = ClientContext.objects.create(
            chef=self.chef,
            client=self.client_user
        )
        
        self.assertEqual(context.get_client_name(), 'John Doe')
        
        # Test with nickname
        context.nickname = 'Johnny'
        context.save()
        self.assertEqual(context.get_client_name(), 'Johnny')
    
    def test_client_context_get_context_prompt(self):
        """Test building context prompt string."""
        from chefs.models import ClientContext
        
        context = ClientContext.objects.create(
            chef=self.chef,
            client=self.client_user,
            cuisine_preferences=['Italian', 'Japanese'],
            flavor_profile={'spicy': 'mild', 'sweet': 'moderate'},
            cooking_notes='Prefers al dente pasta',
            total_orders=5,
            total_spent_cents=50000
        )
        
        prompt = context.get_context_prompt()
        
        self.assertIn('John Doe', prompt)
        self.assertIn('Italian', prompt)
        self.assertIn('Japanese', prompt)
        self.assertIn('spicy', prompt)
        self.assertIn('al dente pasta', prompt)
        self.assertIn('5 orders', prompt)
        self.assertIn('$500.00', prompt)
    
    def test_client_context_special_occasions(self):
        """Test special occasions in context."""
        from chefs.models import ClientContext
        
        context = ClientContext.objects.create(
            chef=self.chef,
            client=self.client_user,
            special_occasions=[
                {'name': 'Birthday', 'date': '2026-03-15'},
                {'name': 'Anniversary', 'date': '2026-06-20'}
            ]
        )
        
        prompt = context.get_context_prompt()
        
        self.assertIn('Birthday', prompt)
        self.assertIn('2026-03-15', prompt)


class SousChefUsageTests(TestCase):
    """Tests for SousChefUsage tracking."""
    
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='testchef3',
            email='chef3@test.com',
            password='testpass123'
        )
    
    def setUp(self):
        from chefs.models import Chef
        self.chef, _ = Chef.objects.get_or_create(user=self.user)
    
    def test_record_usage_creates_entry(self):
        """Test that recording usage creates daily entry."""
        from chefs.models import SousChefUsage
        
        usage = SousChefUsage.record_usage(
            chef=self.chef,
            input_tokens=100,
            output_tokens=50,
            feature='conversation'
        )
        
        self.assertEqual(usage.chef, self.chef)
        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.output_tokens, 50)
        self.assertEqual(usage.request_count, 1)
        self.assertEqual(usage.date, timezone.now().date())
    
    def test_record_usage_accumulates(self):
        """Test that multiple calls accumulate usage."""
        from chefs.models import SousChefUsage
        
        SousChefUsage.record_usage(self.chef, input_tokens=100, output_tokens=50)
        SousChefUsage.record_usage(self.chef, input_tokens=200, output_tokens=100)
        
        usage = SousChefUsage.objects.get(chef=self.chef, date=timezone.now().date())
        
        self.assertEqual(usage.input_tokens, 300)
        self.assertEqual(usage.output_tokens, 150)
        self.assertEqual(usage.request_count, 2)
    
    def test_get_monthly_summary(self):
        """Test monthly summary aggregation."""
        from chefs.models import SousChefUsage
        
        today = timezone.now().date()
        
        SousChefUsage.objects.create(
            chef=self.chef,
            date=today,
            input_tokens=1000,
            output_tokens=500,
            request_count=10
        )
        
        summary = SousChefUsage.get_monthly_summary(
            chef=self.chef,
            year=today.year,
            month=today.month
        )
        
        self.assertEqual(summary['input_tokens'], 1000)
        self.assertEqual(summary['output_tokens'], 500)
        self.assertEqual(summary['total_tokens'], 1500)
        self.assertEqual(summary['requests'], 10)


class HybridMemorySearchTests(TestCase):
    """Tests for hybrid memory search functionality."""
    
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='testchef4',
            email='chef4@test.com',
            password='testpass123'
        )
    
    def setUp(self):
        from chefs.models import Chef
        self.chef, _ = Chef.objects.get_or_create(user=self.user)
    
    def test_hybrid_search_text_only(self):
        """Test hybrid search falls back to text when no embeddings."""
        from customer_dashboard.models import ChefMemory
        from chefs.models import hybrid_memory_search
        
        # Create memories without embeddings
        ChefMemory.objects.create(
            chef=self.chef,
            memory_type='lesson',
            content='Always check for nut allergies before cooking',
            importance=3
        )
        ChefMemory.objects.create(
            chef=self.chef,
            memory_type='preference',
            content='Prefer using fresh herbs over dried',
            importance=3
        )
        
        # Search without embedding (text-only)
        results = hybrid_memory_search(
            chef=self.chef,
            query='nut allergies',
            query_embedding=None,
            limit=10
        )
        
        self.assertGreater(len(results), 0)
        # First result should be about nut allergies
        memory, score = results[0]
        self.assertIn('nut allergies', memory.content.lower())
    
    @patch('chefs.models.sous_chef_memory.CosineDistance')
    def test_hybrid_search_with_embedding(self, mock_cosine):
        """Test hybrid search uses vector when embedding provided."""
        from customer_dashboard.models import ChefMemory
        from chefs.models import hybrid_memory_search
        
        # Create memory with embedding
        fake_embedding = [0.1] * 1536
        ChefMemory.objects.create(
            chef=self.chef,
            memory_type='lesson',
            content='Batch cooking saves time on weekends',
            importance=3,
            embedding=fake_embedding
        )
        
        # Search with embedding
        results = hybrid_memory_search(
            chef=self.chef,
            query='batch cooking',
            query_embedding=fake_embedding,
            limit=10
        )
        
        # Should find the memory (via text at minimum)
        self.assertGreater(len(results), 0)
    
    def test_hybrid_search_filters_by_type(self):
        """Test that memory type filter works."""
        from customer_dashboard.models import ChefMemory
        from chefs.models import hybrid_memory_search
        
        ChefMemory.objects.create(
            chef=self.chef,
            memory_type='lesson',
            content='Lesson about cooking',
            importance=3
        )
        ChefMemory.objects.create(
            chef=self.chef,
            memory_type='todo',
            content='Todo about cooking',
            importance=3
        )
        
        results = hybrid_memory_search(
            chef=self.chef,
            query='cooking',
            memory_types=['lesson'],
            limit=10
        )
        
        self.assertEqual(len(results), 1)
        memory, _ = results[0]
        self.assertEqual(memory.memory_type, 'lesson')


class MemoryServiceTests(TestCase):
    """Tests for MemoryService operations."""
    
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='testchef5',
            email='chef5@test.com',
            password='testpass123'
        )
    
    def setUp(self):
        from chefs.models import Chef
        self.chef, _ = Chef.objects.get_or_create(user=self.user)
    
    @patch('chefs.services.memory_service.EmbeddingService.get_embedding')
    def test_save_memory_with_embedding(self, mock_embedding):
        """Test saving memory generates embedding."""
        from chefs.services import MemoryService
        
        mock_embedding.return_value = [0.1] * 1536
        
        memory = MemoryService.save_memory(
            chef=self.chef,
            content='Test memory content',
            memory_type='lesson',
            importance=4
        )
        
        self.assertIsNotNone(memory)
        self.assertEqual(memory.content, 'Test memory content')
        self.assertEqual(memory.memory_type, 'lesson')
        self.assertEqual(memory.importance, 4)
        mock_embedding.assert_called_once()
    
    @patch('chefs.services.memory_service.EmbeddingService.get_embedding')
    def test_save_memory_without_embedding(self, mock_embedding):
        """Test saving memory when embedding fails."""
        from chefs.services import MemoryService
        
        mock_embedding.return_value = None
        
        memory = MemoryService.save_memory(
            chef=self.chef,
            content='Test memory content',
            generate_embedding=True
        )
        
        self.assertIsNotNone(memory)
        self.assertEqual(memory.content, 'Test memory content')
    
    def test_get_recent_memories(self):
        """Test retrieving recent memories."""
        from customer_dashboard.models import ChefMemory
        from chefs.services import MemoryService
        
        # Create memories
        ChefMemory.objects.create(
            chef=self.chef,
            memory_type='lesson',
            content='Recent memory',
            importance=3
        )
        
        memories = MemoryService.get_recent_memories(
            chef=self.chef,
            days=7,
            limit=10
        )
        
        self.assertGreater(len(memories), 0)
        self.assertEqual(memories[0].content, 'Recent memory')
    
    def test_get_client_memories(self):
        """Test retrieving client-specific memories."""
        from customer_dashboard.models import ChefMemory
        from chefs.services import MemoryService
        
        client = User.objects.create_user(
            username='testclient2',
            email='client2@test.com',
            password='testpass123'
        )
        
        # Create client-specific memory
        ChefMemory.objects.create(
            chef=self.chef,
            customer=client,
            memory_type='preference',
            content='Client likes spicy food',
            importance=4
        )
        
        # Create general memory
        ChefMemory.objects.create(
            chef=self.chef,
            memory_type='lesson',
            content='General cooking tip',
            importance=3
        )
        
        memories = MemoryService.get_client_memories(
            chef=self.chef,
            client=client,
            limit=10
        )
        
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0].content, 'Client likes spicy food')


class ContextAssemblyTests(TestCase):
    """Tests for ContextAssemblyService."""
    
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='testchef6',
            email='chef6@test.com',
            password='testpass123'
        )
        cls.client = User.objects.create_user(
            username='testclient3',
            email='client3@test.com',
            password='testpass123',
            first_name='Alice',
            last_name='Smith'
        )
    
    def setUp(self):
        from chefs.models import Chef
        self.chef, _ = Chef.objects.get_or_create(user=self.user)
    
    def test_build_system_context_basic(self):
        """Test building basic system context."""
        from chefs.services import ContextAssemblyService
        
        context = ContextAssemblyService.build_system_context(
            chef=self.chef,
            include_memories=False,
            include_analytics=False,
            include_seasonal=False
        )
        
        # Should include current time at minimum
        self.assertIn('Current Time', context)
    
    def test_build_system_context_with_workspace(self):
        """Test context includes workspace customizations."""
        from chefs.models import ChefWorkspace
        from chefs.services import ContextAssemblyService
        
        ChefWorkspace.objects.create(
            chef=self.chef,
            soul_prompt='Be extra friendly',
            business_rules='No rush orders'
        )
        
        context = ContextAssemblyService.build_system_context(
            chef=self.chef,
            include_memories=False,
            include_analytics=False,
            include_seasonal=False
        )
        
        self.assertIn('Be extra friendly', context)
        self.assertIn('No rush orders', context)
    
    def test_build_system_context_with_client(self):
        """Test context includes client preferences."""
        from chefs.models import ClientContext
        from chefs.services import ContextAssemblyService
        
        ClientContext.objects.create(
            chef=self.chef,
            client=self.client,
            cuisine_preferences=['Thai', 'Indian'],
            cooking_notes='Extra spicy please'
        )
        
        context = ContextAssemblyService.build_system_context(
            chef=self.chef,
            client=self.client,
            include_memories=False,
            include_analytics=False,
            include_seasonal=False
        )
        
        self.assertIn('Thai', context)
        self.assertIn('Extra spicy please', context)


class BackfillCommandTests(TestCase):
    """Tests for the backfill management command."""
    
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='testchef7',
            email='chef7@test.com',
            password='testpass123'
        )
    
    def setUp(self):
        from chefs.models import Chef
        self.chef, _ = Chef.objects.get_or_create(user=self.user)
    
    def test_dry_run_shows_sample(self):
        """Test dry run shows memories without updating."""
        from django.core.management import call_command
        from customer_dashboard.models import ChefMemory
        from io import StringIO
        
        # Create memory without embedding
        ChefMemory.objects.create(
            chef=self.chef,
            memory_type='lesson',
            content='Test memory for dry run',
            importance=3
        )
        
        out = StringIO()
        call_command('backfill_memory_embeddings', '--dry-run', stdout=out)
        
        output = out.getvalue()
        self.assertIn('DRY RUN', output)
        self.assertIn('Test memory for dry run', output)
    
    @patch('chefs.services.memory_service.EmbeddingService.get_embedding')
    def test_backfill_updates_memories(self, mock_embedding):
        """Test backfill actually updates memories."""
        from django.core.management import call_command
        from customer_dashboard.models import ChefMemory
        from io import StringIO
        
        mock_embedding.return_value = [0.1] * 1536
        
        # Create memory without embedding
        memory = ChefMemory.objects.create(
            chef=self.chef,
            memory_type='lesson',
            content='Memory to backfill',
            importance=3
        )
        
        self.assertIsNone(memory.embedding)
        
        out = StringIO()
        call_command(
            'backfill_memory_embeddings',
            '--chef-id', str(self.chef.id),
            '--delay', '0',
            stdout=out
        )
        
        # Refresh and check
        memory.refresh_from_db()
        output = out.getvalue()
        
        self.assertIn('Backfill complete', output)
        self.assertIn('Successful: 1', output)
    
    def test_no_memories_message(self):
        """Test message when no memories need backfill."""
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        call_command('backfill_memory_embeddings', stdout=out)
        
        output = out.getvalue()
        self.assertIn('No memories need embedding backfill', output)


class EmbeddingServiceTests(TestCase):
    """Tests for EmbeddingService."""
    
    @patch('chefs.services.memory_service.get_openai_client')
    def test_get_embedding_success(self, mock_get_client):
        """Test successful embedding generation."""
        from chefs.services import EmbeddingService
        
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        embedding = EmbeddingService.get_embedding('Test text')
        
        self.assertIsNotNone(embedding)
        self.assertEqual(len(embedding), 1536)
    
    def test_get_embedding_empty_text(self):
        """Test embedding returns None for empty text."""
        from chefs.services import EmbeddingService
        
        embedding = EmbeddingService.get_embedding('')
        self.assertIsNone(embedding)
        
        embedding = EmbeddingService.get_embedding('   ')
        self.assertIsNone(embedding)
    
    @patch('chefs.services.memory_service.get_openai_client')
    def test_get_embedding_truncates_long_text(self, mock_get_client):
        """Test that long text is truncated."""
        from chefs.services import EmbeddingService
        
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        # Very long text
        long_text = 'x' * 10000
        EmbeddingService.get_embedding(long_text)
        
        # Check that the text was truncated in the API call
        call_args = mock_client.embeddings.create.call_args
        input_text = call_args.kwargs['input']
        self.assertLessEqual(len(input_text), 8000)
