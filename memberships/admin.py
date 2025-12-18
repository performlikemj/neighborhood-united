from django.contrib import admin
from django.utils.html import format_html

from .models import ChefMembership, MembershipPaymentLog


class MembershipPaymentLogInline(admin.TabularInline):
    model = MembershipPaymentLog
    extra = 0
    readonly_fields = [
        'amount_display', 'stripe_invoice_id', 'stripe_payment_intent_id',
        'period_start', 'period_end', 'paid_at'
    ]
    fields = ['amount_display', 'paid_at', 'period_start', 'period_end', 'stripe_invoice_id']
    ordering = ['-paid_at']
    
    def amount_display(self, obj):
        return f"${obj.amount_cents / 100:.2f}"
    amount_display.short_description = 'Amount'
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ChefMembership)
class ChefMembershipAdmin(admin.ModelAdmin):
    list_display = [
        'chef_username', 'status', 'is_founding_member', 'billing_cycle', 
        'current_period_display', 'stripe_link', 'created_at'
    ]
    list_filter = ['status', 'billing_cycle', 'is_founding_member']
    search_fields = [
        'chef__user__username', 'chef__user__email',
        'stripe_customer_id', 'stripe_subscription_id'
    ]
    readonly_fields = [
        'stripe_customer_id', 'stripe_subscription_id',
        'trial_started_at', 'trial_ends_at',
        'current_period_start', 'current_period_end',
        'started_at', 'cancelled_at', 'created_at', 'updated_at'
    ]
    inlines = [MembershipPaymentLogInline]
    actions = ['grant_founding_status', 'revoke_founding_status']
    
    fieldsets = (
        ('Chef', {
            'fields': ('chef',)
        }),
        ('Membership Status', {
            'fields': ('status', 'billing_cycle')
        }),
        ('Founding Member', {
            'fields': ('is_founding_member', 'founding_member_notes'),
            'description': 'Founding members get free access during the testing phase.'
        }),
        ('Stripe Integration', {
            'fields': ('stripe_customer_id', 'stripe_subscription_id'),
            'classes': ('collapse',)
        }),
        ('Trial Period', {
            'fields': ('trial_started_at', 'trial_ends_at'),
            'classes': ('collapse',)
        }),
        ('Billing Period', {
            'fields': ('current_period_start', 'current_period_end')
        }),
        ('Timestamps', {
            'fields': ('started_at', 'cancelled_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    @admin.action(description='Grant founding member status (free access)')
    def grant_founding_status(self, request, queryset):
        updated = queryset.update(
            is_founding_member=True,
            status=ChefMembership.Status.FOUNDING,
            billing_cycle=ChefMembership.BillingCycle.FREE,
        )
        self.message_user(request, f'{updated} membership(s) granted founding member status.')
    
    @admin.action(description='Revoke founding member status')
    def revoke_founding_status(self, request, queryset):
        updated = queryset.update(
            is_founding_member=False,
            status=ChefMembership.Status.TRIAL,
            billing_cycle=ChefMembership.BillingCycle.MONTHLY,
        )
        self.message_user(request, f'{updated} membership(s) had founding status revoked.')
    
    def chef_username(self, obj):
        return obj.chef.user.username
    chef_username.short_description = 'Chef'
    chef_username.admin_order_field = 'chef__user__username'
    
    def current_period_display(self, obj):
        if obj.current_period_start and obj.current_period_end:
            return f"{obj.current_period_start.date()} - {obj.current_period_end.date()}"
        return "-"
    current_period_display.short_description = 'Current Period'
    
    def stripe_link(self, obj):
        if obj.stripe_subscription_id:
            url = f"https://dashboard.stripe.com/subscriptions/{obj.stripe_subscription_id}"
            return format_html(
                '<a href="{}" target="_blank">View in Stripe</a>',
                url
            )
        return "-"
    stripe_link.short_description = 'Stripe'


@admin.register(MembershipPaymentLog)
class MembershipPaymentLogAdmin(admin.ModelAdmin):
    list_display = [
        'membership_chef', 'amount_display', 'paid_at', 
        'period_display', 'stripe_invoice_link'
    ]
    list_filter = ['paid_at']
    search_fields = [
        'membership__chef__user__username',
        'stripe_invoice_id', 'stripe_payment_intent_id'
    ]
    readonly_fields = [
        'membership', 'amount_cents', 'currency',
        'stripe_invoice_id', 'stripe_payment_intent_id', 'stripe_charge_id',
        'period_start', 'period_end', 'paid_at', 'created_at'
    ]
    date_hierarchy = 'paid_at'
    
    def membership_chef(self, obj):
        return obj.membership.chef.user.username
    membership_chef.short_description = 'Chef'
    membership_chef.admin_order_field = 'membership__chef__user__username'
    
    def amount_display(self, obj):
        return f"${obj.amount_cents / 100:.2f} {obj.currency.upper()}"
    amount_display.short_description = 'Amount'
    
    def period_display(self, obj):
        if obj.period_start and obj.period_end:
            return f"{obj.period_start.date()} - {obj.period_end.date()}"
        return "-"
    period_display.short_description = 'Period'
    
    def stripe_invoice_link(self, obj):
        if obj.stripe_invoice_id:
            url = f"https://dashboard.stripe.com/invoices/{obj.stripe_invoice_id}"
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                url, obj.stripe_invoice_id[:20] + "..."
            )
        return "-"
    stripe_invoice_link.short_description = 'Invoice'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False





