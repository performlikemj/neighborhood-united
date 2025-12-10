from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from django.utils import timezone

from crm.models import Lead, LeadInteraction


@dataclass
class LeadContext:
    user: Any
    chef_user: Any
    offering: Any | None = None


def _build_lead_defaults(context: LeadContext, source: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    user = context.user
    defaults = {
        "first_name": user.first_name or user.username or "",
        "last_name": user.last_name or "",
        "email": getattr(user, "email", ""),
        "phone": getattr(user, "phone_number", ""),
        "owner": context.chef_user,
        "offering": context.offering,
        "source": source,
    }
    if extra:
        defaults.update(extra)
    return defaults


def _append_interaction(
    lead: Lead,
    *,
    interaction_type: str,
    summary: str,
    details: str | None = None,
    happened_at: Any | None = None,
    author: Any | None = None,
    next_steps: str | None = None,
) -> LeadInteraction:
    return LeadInteraction.objects.create(
        lead=lead,
        author=author,
        interaction_type=interaction_type,
        summary=summary,
        details=details or "",
        happened_at=happened_at or timezone.now(),
        next_steps=next_steps or "",
    )


def create_or_update_lead_for_user(
    *,
    user: Any,
    chef_user: Any,
    source: str,
    offering: Any | None = None,
    summary: str,
    details: str | None = None,
    interaction_type: str = LeadInteraction.InteractionType.NOTE,
    interaction_payload: Optional[Dict[str, Any]] = None,
    next_steps: str | None = None,
) -> Lead:
    """Create (or update) a lead for a customer interacting with a chef.

    The helper keeps a single lead per customer/chef combination to avoid
    duplication. Each call appends a ``LeadInteraction`` with the supplied
    context so downstream users can see the full timeline.
    """
    # Only use offering if it's the correct model type (services.ServiceOffering)
    # ChefServiceOffering from chef_services app is a different model
    from services.models import ServiceOffering
    valid_offering = offering if isinstance(offering, ServiceOffering) else None
    
    context = LeadContext(user=user, chef_user=chef_user, offering=valid_offering)
    defaults = _build_lead_defaults(context, source, interaction_payload)

    # Look up by owner and email only - offering may vary across orders
    lead, created = Lead.objects.get_or_create(
        owner=chef_user,
        email=defaults.get("email") or None,
        defaults=defaults,
    )

    # Fill in missing fields when we find a pre-existing lead
    if not created:
        updated = False
        for field, value in defaults.items():
            if not getattr(lead, field) and value:
                setattr(lead, field, value)
                updated = True
        if updated:
            lead.save()

    _append_interaction(
        lead,
        interaction_type=interaction_type,
        summary=summary,
        details=details,
        author=chef_user,
        next_steps=next_steps,
    )
    return lead

