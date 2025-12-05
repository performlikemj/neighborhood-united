from django.urls import path

from chefs.api import waitlist as waitlist_api
from chefs.api import dashboard as dashboard_api
from chefs.api import clients as clients_api
from chefs.api import analytics as analytics_api
from chefs.api import leads as leads_api
from chefs.api import unified_clients as unified_api
from chefs.api import sous_chef as sous_chef_api
from chefs.api import availability as availability_api
from chefs.api import meal_plans as meal_plans_api
from . import views


app_name = 'chefs'

urlpatterns = [
    # Chef Availability API
    path('api/availability/', availability_api.check_chef_availability, name='check_chef_availability'),
    path('api/availability/check/', availability_api.check_area_chef_availability, name='check_area_chef_availability'),
    
    # Area Waitlist API
    path('api/area-waitlist/join/', availability_api.join_area_waitlist, name='join_area_waitlist'),
    path('api/area-waitlist/leave/', availability_api.leave_area_waitlist, name='leave_area_waitlist'),
    path('api/area-waitlist/status/', availability_api.area_waitlist_status, name='area_waitlist_status'),
    
    # Public API
    path('api/public/<int:chef_id>/', views.chef_public, name='chef_public'),
    path('api/public/by-username/<slug:slug>/', views.chef_public_by_username, name='chef_public_by_username'),
    path('api/lookup/by-username/<str:username>/', views.chef_lookup_by_username, name='chef_lookup_by_username'),
    path('api/public/', views.chef_public_directory, name='chef_public_directory'),
    path('api/public/<int:chef_id>/serves-my-area/', views.chef_serves_my_area, name='chef_serves_my_area'),
    path('api/public/<int:chef_id>/stripe-status/', views.chef_stripe_status, name='chef_stripe_status'),
    
    # Waitlist API
    path('api/waitlist/config/', waitlist_api.waitlist_config, name='waitlist_config'),
    path('api/public/<int:chef_id>/waitlist/status/', waitlist_api.waitlist_status, name='waitlist_status'),
    path('api/public/<int:chef_id>/waitlist/subscribe', waitlist_api.waitlist_subscribe, name='waitlist_subscribe'),
    path('api/public/<int:chef_id>/waitlist/unsubscribe', waitlist_api.waitlist_unsubscribe, name='waitlist_unsubscribe'),
    
    # Gallery API - Public endpoints for chef photo galleries
    path('api/<str:username>/photos/', views.chef_gallery_photos, name='chef_gallery_photos'),
    path('api/<str:username>/gallery/stats/', views.chef_gallery_stats, name='chef_gallery_stats'),
    path('api/<str:username>/photos/<int:photo_id>/', views.chef_gallery_photo_detail, name='chef_gallery_photo_detail'),
    
    # React API endpoints for chef profile management
    path('api/me/chef/profile/', views.me_chef_profile, name='me_chef_profile'),
    path('api/me/chef/profile/update/', views.me_update_profile, name='me_update_profile'),
    path('api/me/chef/break/', views.me_set_break, name='me_set_break'),
    path('api/me/chef/photos/', views.me_upload_photo, name='me_upload_photo'),
    path('api/me/chef/photos/<int:photo_id>/', views.me_delete_photo, name='me_delete_photo'),
    
    # Chef-related endpoints
    path('api/check-chef-status/', views.check_chef_status, name='check_chef_status'),
    path('api/submit-chef-request/', views.submit_chef_request, name='submit_chef_request'),
    
    # ==========================================================================
    # Chef CRM Dashboard API Endpoints
    # ==========================================================================
    
    # Dashboard Summary
    path('api/me/dashboard/', dashboard_api.dashboard_summary, name='chef_dashboard'),
    
    # Client Management
    path('api/me/clients/', clients_api.client_list, name='chef_clients'),
    path('api/me/clients/<int:customer_id>/', clients_api.client_detail, name='chef_client_detail'),
    path('api/me/clients/<int:customer_id>/notes/', clients_api.client_notes, name='chef_client_notes'),
    
    # Revenue & Analytics
    path('api/me/revenue/', analytics_api.revenue_breakdown, name='chef_revenue'),
    path('api/me/orders/upcoming/', analytics_api.upcoming_orders, name='chef_upcoming_orders'),
    
    # Lead Pipeline (CRM) - Contacts / Off-Platform Clients
    path('api/me/leads/', leads_api.lead_list, name='chef_leads'),
    path('api/me/leads/<int:lead_id>/', leads_api.lead_detail, name='chef_lead_detail'),
    path('api/me/leads/<int:lead_id>/interactions/', leads_api.lead_interactions, name='chef_lead_interactions'),
    path('api/me/leads/<int:lead_id>/household/', leads_api.lead_household_members, name='chef_lead_household'),
    path('api/me/leads/<int:lead_id>/household/<int:member_id>/', leads_api.lead_household_member_detail, name='chef_lead_household_detail'),
    
    # Unified Clients View (All Clients - Platform + Manual)
    path('api/me/all-clients/', unified_api.unified_client_list, name='chef_all_clients'),
    path('api/me/all-clients/<str:client_id>/', unified_api.unified_client_detail, name='chef_all_client_detail'),
    path('api/me/dietary-summary/', unified_api.dietary_summary, name='chef_dietary_summary'),
    
    # ==========================================================================
    # Sous Chef AI Assistant Endpoints
    # ==========================================================================
    
    # Streaming message endpoint
    path('api/me/sous-chef/stream/', sous_chef_api.sous_chef_stream_message, name='sous_chef_stream'),
    
    # Non-streaming message endpoint
    path('api/me/sous-chef/message/', sous_chef_api.sous_chef_send_message, name='sous_chef_message'),
    
    # Structured output message endpoint (new - returns JSON blocks)
    path('api/me/sous-chef/structured/', sous_chef_api.sous_chef_structured_message, name='sous_chef_structured'),
    
    # Start new conversation
    path('api/me/sous-chef/new-conversation/', sous_chef_api.sous_chef_new_conversation, name='sous_chef_new_conversation'),
    
    # Get conversation history for a family
    path('api/me/sous-chef/history/<str:family_type>/<int:family_id>/', sous_chef_api.sous_chef_thread_history, name='sous_chef_history'),
    
    # Get family context for display
    path('api/me/sous-chef/context/<str:family_type>/<int:family_id>/', sous_chef_api.sous_chef_family_context, name='sous_chef_context'),
    
    # ==========================================================================
    # Collaborative Meal Plans API (Chef endpoints)
    # ==========================================================================
    
    # Client meal plans
    path('api/me/clients/<int:client_id>/plans/', meal_plans_api.client_plans, name='chef_client_plans'),
    
    # Plan management
    path('api/me/plans/<int:plan_id>/', meal_plans_api.plan_detail, name='chef_plan_detail'),
    path('api/me/plans/<int:plan_id>/publish/', meal_plans_api.publish_plan, name='chef_publish_plan'),
    path('api/me/plans/<int:plan_id>/archive/', meal_plans_api.archive_plan, name='chef_archive_plan'),
    
    # Plan days
    path('api/me/plans/<int:plan_id>/days/', meal_plans_api.add_plan_day, name='chef_add_plan_day'),
    path('api/me/plans/<int:plan_id>/days/<int:day_id>/', meal_plans_api.plan_day_detail, name='chef_plan_day_detail'),
    
    # Plan items
    path('api/me/plans/<int:plan_id>/days/<int:day_id>/items/', meal_plans_api.add_plan_item, name='chef_add_plan_item'),
    path('api/me/plans/<int:plan_id>/days/<int:day_id>/items/<int:item_id>/', meal_plans_api.plan_item_detail, name='chef_plan_item_detail'),
    
    # Suggestions management
    path('api/me/plans/<int:plan_id>/suggestions/', meal_plans_api.plan_suggestions, name='chef_plan_suggestions'),
    path('api/me/suggestions/<int:suggestion_id>/respond/', meal_plans_api.respond_to_suggestion, name='chef_respond_suggestion'),
    
    # AI meal generation (async)
    path('api/me/plans/<int:plan_id>/generate/', meal_plans_api.generate_meals_for_plan, name='chef_generate_meals'),
    path('api/me/plans/<int:plan_id>/generation-jobs/', meal_plans_api.list_generation_jobs, name='chef_list_generation_jobs'),
    path('api/me/generation-jobs/<int:job_id>/', meal_plans_api.get_generation_job_status, name='chef_generation_job_status'),
    
    # Chef's saved dishes
    path('api/me/dishes/', meal_plans_api.chef_dishes, name='chef_dishes'),
]