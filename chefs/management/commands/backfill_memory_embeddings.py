# chefs/management/commands/backfill_memory_embeddings.py
"""
Management command to backfill embeddings for existing ChefMemory records.

This enables semantic/hybrid search for memories that were created before
the embedding system was added.

Usage:
    # Backfill all memories without embeddings
    python manage.py backfill_memory_embeddings

    # Backfill for a specific chef
    python manage.py backfill_memory_embeddings --chef-id=123

    # Dry run (see what would be updated)
    python manage.py backfill_memory_embeddings --dry-run

    # Limit batch size
    python manage.py backfill_memory_embeddings --batch-size=50

    # Force regenerate all embeddings (even existing ones)
    python manage.py backfill_memory_embeddings --force
"""

import time
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = 'Backfill embeddings for ChefMemory records to enable semantic search.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--chef-id',
            type=int,
            help='Only backfill memories for a specific chef ID',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of memories to process in each batch (default: 100)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate embeddings even for memories that already have them',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.1,
            help='Delay between API calls in seconds (default: 0.1)',
        )

    def handle(self, *args, **options):
        from customer_dashboard.models import ChefMemory
        
        chef_id = options['chef_id']
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        force = options['force']
        delay = options['delay']

        # Build queryset
        queryset = ChefMemory.objects.filter(is_active=True)
        
        if chef_id:
            queryset = queryset.filter(chef_id=chef_id)
        
        if not force:
            queryset = queryset.filter(embedding__isnull=True)
        
        total_count = queryset.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('No memories need embedding backfill.'))
            return
        
        self.stdout.write(f'Found {total_count} memories to process.')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be made.'))
            self._show_sample(queryset)
            return
        
        # Import embedding service
        try:
            from chefs.services import EmbeddingService
        except ImportError as e:
            raise CommandError(f'EmbeddingService not available: {e}')
        
        # Process in batches
        processed = 0
        success = 0
        failed = 0
        
        self.stdout.write('Starting backfill...')
        
        # Get IDs to process (avoid queryset mutation during iteration)
        memory_ids = list(queryset.values_list('id', flat=True))
        
        for i in range(0, len(memory_ids), batch_size):
            batch_ids = memory_ids[i:i + batch_size]
            batch_memories = ChefMemory.objects.filter(id__in=batch_ids)
            
            for memory in batch_memories:
                processed += 1
                
                try:
                    # Generate embedding
                    embedding = EmbeddingService.get_embedding(memory.content)
                    
                    if embedding:
                        memory.embedding = embedding
                        memory.save(update_fields=['embedding'])
                        success += 1
                    else:
                        failed += 1
                        self.stdout.write(
                            self.style.WARNING(f'  No embedding generated for memory {memory.id}')
                        )
                    
                    # Rate limiting
                    if delay > 0:
                        time.sleep(delay)
                    
                except Exception as e:
                    failed += 1
                    self.stdout.write(
                        self.style.ERROR(f'  Error processing memory {memory.id}: {e}')
                    )
                
                # Progress update
                if processed % 10 == 0:
                    self.stdout.write(f'  Processed {processed}/{total_count}...')
        
        # Final summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Backfill complete!'))
        self.stdout.write(f'  Total processed: {processed}')
        self.stdout.write(f'  Successful: {success}')
        self.stdout.write(f'  Failed: {failed}')
    
    def _show_sample(self, queryset):
        """Show a sample of memories that would be updated."""
        sample = queryset[:5]
        
        self.stdout.write('\nSample of memories to backfill:')
        for memory in sample:
            preview = memory.content[:60] + '...' if len(memory.content) > 60 else memory.content
            self.stdout.write(f'  [{memory.id}] {memory.memory_type}: {preview}')
        
        if queryset.count() > 5:
            self.stdout.write(f'  ... and {queryset.count() - 5} more')
