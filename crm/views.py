from rest_framework import generics, permissions

from crm.models import Lead
from crm.serializers import LeadSerializer


class LeadPermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True
        return obj.owner_id == request.user.id

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class LeadListCreateView(generics.ListCreateAPIView):
    serializer_class = LeadSerializer
    permission_classes = [LeadPermission]

    def get_queryset(self):
        qs = Lead.objects.active()
        if not self.request.user.is_staff:
            qs = qs.filter(owner=self.request.user)
        stage = self.request.query_params.get("stage")
        if stage:
            qs = qs.filter(status=stage)
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class LeadDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = LeadSerializer
    permission_classes = [LeadPermission]
    lookup_url_kwarg = "lead_id"

    def get_queryset(self):
        qs = Lead.objects.active()
        if not self.request.user.is_staff:
            qs = qs.filter(owner=self.request.user)
        return qs
