import json
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponseRedirect
from .models import PostalCode, ChefPostalCode, AdministrativeArea, ServiceAreaRequest


class ChefPostalCodeAdmin(admin.ModelAdmin):
    list_display = ['chef_username', 'postal_code_display', 'country']
    list_filter = ['postal_code__country']
    search_fields = ['chef__user__username', 'postal_code__code', 'postal_code__place_name']
    raw_id_fields = ['chef', 'postal_code']
    list_per_page = 50  # Pagination for large datasets
    list_select_related = ['chef__user', 'postal_code']  # Optimize queries
    
    @admin.display(description='Chef', ordering='chef__user__username')
    def chef_username(self, obj):
        return obj.chef.user.username if obj.chef and obj.chef.user else '—'
    
    @admin.display(description='Postal Code', ordering='postal_code__code')
    def postal_code_display(self, obj):
        pc = obj.postal_code
        if not pc:
            return '—'
        code = pc.display_code or pc.code
        place = pc.place_name or ''
        return f"{code} ({place})" if place else code
    
    @admin.display(description='Country')
    def country(self, obj):
        return obj.postal_code.country.name if obj.postal_code else '—'
    
    def save_model(self, request, obj, form, change):
        try:
            super().save_model(request, obj, form, change)
        except Exception as e:
            self.message_user(request, f"Error saving: {str(e)}", level='ERROR')
            raise


class PostalCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'display_code', 'country', 'place_name', 'admin_area']
    list_filter = ['country', 'admin_area__area_type']
    search_fields = ['code', 'display_code', 'place_name']
    raw_id_fields = ['admin_area']


class AdministrativeAreaAdmin(admin.ModelAdmin):
    list_display = ['name', 'name_local', 'area_type', 'country', 'parent', 'postal_code_count']
    list_filter = ['country', 'area_type']
    search_fields = ['name', 'name_local', 'geonames_id']
    raw_id_fields = ['parent']
    readonly_fields = ['postal_code_count', 'geonames_id']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'name_local', 'area_type', 'country')
        }),
        ('Hierarchy', {
            'fields': ('parent',)
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'boundary_geojson')
        }),
        ('Metadata', {
            'fields': ('geonames_id', 'postal_code_count'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['update_postal_code_counts']
    
    @admin.action(description="Update postal code counts for selected areas")
    def update_postal_code_counts(self, request, queryset):
        for area in queryset:
            area.update_postal_code_count()
        self.message_user(request, f"Updated counts for {queryset.count()} areas")


class ServiceAreaRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'chef_link', 'status_badge', 'areas_summary', 
        'total_codes', 'created_at', 'reviewed_at', 'action_buttons'
    ]
    list_filter = ['status', 'created_at', 'reviewed_at']
    search_fields = ['chef__user__username', 'chef_notes', 'admin_notes']
    readonly_fields = [
        'chef', 'requested_areas', 'requested_postal_codes',
        'created_at', 'updated_at', 'reviewed_at', 'reviewed_by',
        'areas_detail', 'postal_codes_detail', 'approval_detail'
    ]
    raw_id_fields = ['chef']
    filter_horizontal = ['requested_areas', 'requested_postal_codes']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Request Info', {
            'fields': ('chef', 'status', 'chef_notes')
        }),
        ('Requested Areas', {
            'fields': ('areas_detail', 'postal_codes_detail'),
            'classes': ('wide',)
        }),
        ('Approval Details', {
            'fields': ('approval_detail',),
            'classes': ('wide',),
            'description': 'Shows what was approved vs rejected for partial approvals'
        }),
        ('Review', {
            'fields': ('admin_notes', 'reviewed_by', 'reviewed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_requests', 'reject_requests', 'partial_approve_action']
    change_form_template = 'admin/local_chefs/servicearearequest/change_form.html'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:request_id>/partial-approve/',
                self.admin_site.admin_view(self.partial_approve_view),
                name='local_chefs_servicearearequest_partial_approve'
            ),
        ]
        return custom_urls + urls
    
    def chef_link(self, obj):
        url = reverse('admin:chefs_chef_change', args=[obj.chef.id])
        return format_html('<a href="{}">{}</a>', url, obj.chef.user.username)
    chef_link.short_description = 'Chef'
    chef_link.admin_order_field = 'chef__user__username'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#f0ad4e',
            'approved': '#5cb85c',
            'rejected': '#d9534f',
            'partially_approved': '#5bc0de',
        }
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background:{}; color:#fff; padding:2px 8px; border-radius:3px; font-size:11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def action_buttons(self, obj):
        """Show action buttons for pending requests."""
        if obj.status != 'pending':
            return '—'
        
        partial_url = reverse('admin:local_chefs_servicearearequest_partial_approve', args=[obj.pk])
        return format_html(
            '<a class="button" style="padding:3px 8px; font-size:11px; background:#5bc0de; color:#fff; text-decoration:none; border-radius:3px;" '
            'href="{}">Partial Approve</a>',
            partial_url
        )
    action_buttons.short_description = 'Actions'
    
    def areas_summary(self, obj):
        areas = obj.requested_areas.all()[:3]
        names = [a.name for a in areas]
        count = obj.requested_areas.count()
        if count > 3:
            return f"{', '.join(names)} (+{count - 3} more)"
        return ', '.join(names) or '—'
    areas_summary.short_description = 'Areas'
    
    def total_codes(self, obj):
        return obj.total_postal_codes_requested
    total_codes.short_description = 'Postal Codes'
    
    def areas_detail(self, obj):
        areas = obj.requested_areas.all()
        if not areas:
            return "No areas requested"
        lines = []
        for area in areas:
            # Show approval status if partially approved
            status_icon = ''
            if obj.status == 'partially_approved':
                if obj.approved_areas.filter(id=area.id).exists():
                    status_icon = '✅ '
                else:
                    status_icon = '❌ '
            elif obj.status == 'approved':
                status_icon = '✅ '
            lines.append(f"{status_icon}• {area.name} ({area.area_type}) - {area.postal_code_count} codes")
        return format_html('<br>'.join(lines))
    areas_detail.short_description = 'Requested Areas'
    
    def postal_codes_detail(self, obj):
        codes = obj.requested_postal_codes.all()[:20]
        if not codes:
            return "No individual codes requested"
        code_list = []
        for pc in codes:
            status_icon = ''
            if obj.status == 'partially_approved':
                if obj.approved_postal_codes.filter(id=pc.id).exists():
                    status_icon = '✅ '
                else:
                    status_icon = '❌ '
            elif obj.status == 'approved':
                status_icon = '✅ '
            code_list.append(f"{status_icon}{pc.display_code or pc.code} ({pc.country})")
        total = obj.requested_postal_codes.count()
        result = ', '.join(code_list)
        if total > 20:
            result += f" (+{total - 20} more)"
        return result
    postal_codes_detail.short_description = 'Requested Postal Codes'
    
    def approval_detail(self, obj):
        """Show approval summary for reviewed requests."""
        if obj.status == 'pending':
            return "Request not yet reviewed"
        
        summary = obj.approval_summary
        if not summary:
            return "—"
        
        return format_html(
            '<div style="padding:10px; background:#f8f9fa; border-radius:4px;">'
            '<div style="color:#5cb85c;">✅ Approved: {} areas ({} postal codes)</div>'
            '<div style="color:#d9534f;">❌ Rejected: {} areas ({} postal codes)</div>'
            '</div>',
            summary['approved_areas'], summary['approved_codes'],
            summary['rejected_areas'], summary['rejected_codes']
        )
    approval_detail.short_description = 'Approval Summary'
    
    def partial_approve_view(self, request, request_id):
        """Custom view for partial approval selection."""
        area_request = get_object_or_404(ServiceAreaRequest, pk=request_id)
        
        if area_request.status != 'pending':
            messages.error(request, f"This request has already been {area_request.status}.")
            return HttpResponseRedirect(reverse('admin:local_chefs_servicearearequest_changelist'))
        
        if request.method == 'POST':
            # Process the form - collect all postal code IDs
            admin_notes = request.POST.get('admin_notes', '')
            
            # Individual postal codes from the individual codes section
            selected_code_ids = request.POST.getlist('postal_codes')
            all_code_ids = set(int(x) for x in selected_code_ids if x)
            
            # Codes selected from within areas (format: "area_id:code_id")
            area_code_selections = request.POST.getlist('area_postal_codes')
            for selection in area_code_selections:
                if ':' in selection:
                    _, code_id = selection.split(':', 1)
                    try:
                        all_code_ids.add(int(code_id))
                    except ValueError:
                        pass
            
            if not all_code_ids:
                messages.warning(request, "No postal codes selected. Select at least one postal code to approve.")
            else:
                # Calculate total possible codes for full approval check
                total_requested_codes = set()
                for area in area_request.requested_areas.all():
                    total_requested_codes.update(area.get_all_postal_codes().values_list('id', flat=True))
                total_requested_codes.update(area_request.requested_postal_codes.values_list('id', flat=True))
                
                if all_code_ids >= total_requested_codes:
                    # Full approval - all codes selected
                    area_request.approve(request.user, admin_notes)
                    messages.success(request, f"Request fully approved. All codes added to {area_request.chef.user.username}'s service areas.")
                else:
                    # Partial approval
                    approved_count = area_request.partially_approve(
                        request.user, 
                        postal_code_ids=all_code_ids,
                        notes=admin_notes
                    )
                    messages.success(
                        request, 
                        f"Request partially approved. Added {approved_count} postal codes to {area_request.chef.user.username}'s service areas."
                    )
                
                return HttpResponseRedirect(reverse('admin:local_chefs_servicearearequest_changelist'))
        
        # Prepare data for the template
        requested_areas = list(area_request.requested_areas.all())
        requested_codes = list(area_request.requested_postal_codes.all())
        
        # Calculate total codes for each area with lazy loading support
        INITIAL_CODES_LIMIT = 30  # Show first 30, lazy load rest
        areas_with_counts = []
        for area in requested_areas:
            all_codes = list(area.get_all_postal_codes().values('id', 'code', 'display_code', 'place_name'))
            remaining_codes = all_codes[INITIAL_CODES_LIMIT:]
            areas_with_counts.append({
                'obj': area,
                'id': area.id,
                'name': area.name,
                'name_local': area.name_local,
                'area_type': area.area_type,
                'parent_name': area.parent.name if area.parent else '',
                'postal_code_count': len(all_codes),
                'postal_codes_initial': all_codes[:INITIAL_CODES_LIMIT],
                'postal_codes_remaining_json': json.dumps(remaining_codes),  # JSON string for template
                'has_more': len(all_codes) > INITIAL_CODES_LIMIT,
            })
        
        context = {
            **self.admin_site.each_context(request),
            'title': f'Partial Approve: {area_request}',
            'area_request': area_request,
            'areas': areas_with_counts,
            'postal_codes': requested_codes,
            'opts': self.model._meta,
            'has_change_permission': self.has_change_permission(request, area_request),
        }
        
        return render(request, 'admin/local_chefs/servicearearequest/partial_approve.html', context)
    
    @admin.action(description="Approve selected requests (full)")
    def approve_requests(self, request, queryset):
        approved = 0
        for req in queryset.filter(status='pending'):
            req.approve(request.user, notes='Approved via admin bulk action')
            approved += 1
        self.message_user(request, f"Approved {approved} requests")
    
    @admin.action(description="Reject selected requests")
    def reject_requests(self, request, queryset):
        rejected = 0
        for req in queryset.filter(status='pending'):
            req.reject(request.user, notes='Rejected via admin bulk action')
            rejected += 1
        self.message_user(request, f"Rejected {rejected} requests")
    
    @admin.action(description="Partial approve selected (choose areas)")
    def partial_approve_action(self, request, queryset):
        pending = queryset.filter(status='pending')
        if pending.count() == 0:
            self.message_user(request, "No pending requests selected.", level='WARNING')
            return
        if pending.count() > 1:
            self.message_user(request, "Partial approval can only be done one at a time. Please select a single request.", level='WARNING')
            return
        # Redirect to the partial approve page for the single selected request
        req = pending.first()
        url = reverse('admin:local_chefs_servicearearequest_partial_approve', args=[req.pk])
        return HttpResponseRedirect(url)
    
    def save_model(self, request, obj, form, change):
        # If status changed to approved, run the approval logic
        if change:
            old_obj = ServiceAreaRequest.objects.get(pk=obj.pk)
            if old_obj.status != 'approved' and obj.status == 'approved':
                # Don't save twice - approve() handles the save
                obj.approve(request.user, obj.admin_notes or '')
                return
            elif old_obj.status != 'rejected' and obj.status == 'rejected':
                obj.reject(request.user, obj.admin_notes or '')
                return
        super().save_model(request, obj, form, change)


admin.site.register(PostalCode, PostalCodeAdmin)
admin.site.register(ChefPostalCode, ChefPostalCodeAdmin)
admin.site.register(AdministrativeArea, AdministrativeAreaAdmin)
admin.site.register(ServiceAreaRequest, ServiceAreaRequestAdmin)
