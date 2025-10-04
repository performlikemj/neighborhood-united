import logging
from datetime import datetime, timezone

import stripe
from celery import shared_task
from django.conf import settings
from django.db import transaction

from .models import ChefServicePriceTier

logger = logging.getLogger(__name__)


def _ensure_product(offering):
    if offering.stripe_product_id:
        return offering.stripe_product_id
    stripe.api_key = settings.STRIPE_SECRET_KEY
    name = f"{offering.title} – Offering {offering.id} (Chef {offering.chef_id})"
    try:
        product = stripe.Product.create(
            name=name,
            metadata={"offering_id": str(offering.id), "chef_id": str(offering.chef_id)},
            idempotency_key=f"service_offering_product_{offering.id}"
        )
        offering.stripe_product_id = product.id
        offering.save(update_fields=["stripe_product_id"])
        return product.id
    except Exception as e:
        raise e


def _price_matches_current(price_obj, tier: ChefServicePriceTier) -> bool:
    try:
        ua = getattr(price_obj, 'unit_amount', None)
        cur = getattr(price_obj, 'currency', None)
        rec = getattr(price_obj, 'recurring', None)
        is_rec = bool(rec is not None)
        if ua != tier.desired_unit_amount_cents:
            return False
        if (cur or '').lower() != (tier.currency or '').lower():
            return False
        if bool(tier.is_recurring) != is_rec:
            return False
        if tier.is_recurring:
            interval = getattr(rec, 'interval', None) if rec else None
            if interval != (tier.recurrence_interval or None):
                return False
        return True
    except Exception:
        return False


@shared_task(name="chef_services.tasks.sync_pending_service_tiers")
def sync_pending_service_tiers():
    """Provision Stripe Products/Prices for pending active tiers.
    Idempotent: uses existing price when matching; otherwise creates a new one.
    """
    stripe.api_key = settings.STRIPE_SECRET_KEY
    tiers = ChefServicePriceTier.objects.select_related('offering', 'offering__chef').filter(
        active=True, price_sync_status='pending'
    )
    processed = 0
    for tier in tiers:
        try:
            with transaction.atomic():
                tier = ChefServicePriceTier.objects.select_for_update().select_related('offering', 'offering__chef').get(id=tier.id)
                if not tier.active:
                    continue

                # Ensure product
                product_id = _ensure_product(tier.offering)

                # If a price is already linked, verify if it matches desired config
                if tier.stripe_price_id:
                    try:
                        price = stripe.Price.retrieve(tier.stripe_price_id)
                        if _price_matches_current(price, tier):
                            # Mark success and continue
                            if tier.price_sync_status != 'success':
                                tier.price_sync_status = 'success'
                                tier.price_synced_at = datetime.now(timezone.utc)
                                tier.last_price_sync_error = None
                                tier.save(update_fields=['price_sync_status', 'price_synced_at', 'last_price_sync_error'])
                            processed += 1
                            continue
                    except Exception:
                        # Fall through to create a new price
                        pass

                # Create a new Price
                kwargs = dict(product=product_id, currency=tier.currency, unit_amount=int(tier.desired_unit_amount_cents))
                if tier.is_recurring:
                    kwargs['recurring'] = {'interval': tier.recurrence_interval or 'week'}

                idempotency_key = f"service_tier_{tier.id}_{tier.desired_unit_amount_cents}_{'rec' if tier.is_recurring else 'ot'}"
                price = stripe.Price.create(
                    **kwargs,
                    idempotency_key=idempotency_key
                )

                tier.stripe_price_id = price.id
                tier.price_sync_status = 'success'
                tier.price_synced_at = datetime.now(timezone.utc)
                tier.last_price_sync_error = None
                tier.save(update_fields=['stripe_price_id', 'price_sync_status', 'price_synced_at', 'last_price_sync_error'])
                processed += 1
        except Exception as e:
            # Persist error on tier
            try:
                tier.price_sync_status = 'error'
                tier.last_price_sync_error = str(e)[:500]
                tier.save(update_fields=['price_sync_status', 'last_price_sync_error'])
            except Exception:
                pass
            logger.error(f"Failed to sync tier {tier.id}: {e}")
    return {"processed": processed}
