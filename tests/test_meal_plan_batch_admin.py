import datetime

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from meals.admin import MealPlanBatchJobAdmin
from meals.models import MealPlanBatchJob


@pytest.mark.django_db
def test_meal_plan_batch_job_admin_allows_delete(django_user_model):
    admin_site = AdminSite()
    job_admin = MealPlanBatchJobAdmin(MealPlanBatchJob, admin_site)

    request = RequestFactory().get("/admin/meals/mealplanbatchjob/")
    admin_user = django_user_model.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="password123",
    )
    request.user = admin_user

    job = MealPlanBatchJob.objects.create(
        week_start_date=datetime.date(2025, 9, 29),
        week_end_date=datetime.date(2025, 10, 5),
    )

    assert job_admin.has_delete_permission(request) is True
    assert job_admin.has_delete_permission(request, job) is True
