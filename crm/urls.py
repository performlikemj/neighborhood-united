from django.urls import path

from crm import views


urlpatterns = [
    path("api/leads/", views.LeadListCreateView.as_view(), name="crm_leads"),
    path("api/leads/<int:lead_id>/", views.LeadDetailView.as_view(), name="crm_lead_detail"),
]
