"""
Serializers for the community membership models.
"""

from rest_framework import serializers
from .models import ChefMembership, MembershipPaymentLog


class MembershipPaymentLogSerializer(serializers.ModelSerializer):
    """Serializer for payment history."""
    
    amount = serializers.SerializerMethodField()
    
    class Meta:
        model = MembershipPaymentLog
        fields = [
            'id', 'amount', 'currency', 'paid_at',
            'period_start', 'period_end'
        ]
    
    def get_amount(self, obj):
        return obj.amount_cents / 100


class ChefMembershipSerializer(serializers.ModelSerializer):
    """Serializer for membership status."""
    
    chef_username = serializers.CharField(source='chef.user.username', read_only=True)
    is_active = serializers.BooleanField(source='is_active_member', read_only=True)
    is_in_trial = serializers.BooleanField(read_only=True)
    days_until_trial_ends = serializers.IntegerField(read_only=True)
    total_contributed = serializers.SerializerMethodField()
    
    class Meta:
        model = ChefMembership
        fields = [
            'id', 'chef_username', 'status', 'billing_cycle',
            'is_active', 'is_in_trial', 'days_until_trial_ends',
            'trial_ends_at', 'current_period_start', 'current_period_end',
            'started_at', 'cancelled_at', 'total_contributed'
        ]
    
    def get_total_contributed(self, obj):
        from django.db.models import Sum
        total_cents = obj.payment_logs.aggregate(
            total=Sum('amount_cents')
        )['total'] or 0
        return total_cents / 100





