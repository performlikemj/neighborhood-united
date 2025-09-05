"""
URL configuration for hood_united project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.conf.urls.static import static
from django.conf import settings


urlpatterns = [
    # Simple health check endpoint for load balancers and CI smoke tests
    path('healthz/', lambda request: HttpResponse('ok'), name='healthz'),
    path('admin/', admin.site.urls),
    path('chefs/', include('chefs.urls')),
    path('chef_admin/', include('chef_admin.urls')),
    path('customer_dashboard/', include('customer_dashboard.urls')),
    path('auth/', include('custom_auth.urls')),
    path('meals/', include('meals.urls')),
    path('reviews/', include('reviews.urls')),
    path('events/', include('events.urls')),
    path('local_chefs/', include('local_chefs.urls')),
]

# Conditionally expose gamification routes
if getattr(settings, 'GAMIFICATION_ENABLED', False):
    urlpatterns.append(path('gamification/', include('gamification.urls')))

# Serve media files in development only
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Static files are automatically served by Django's development server when DEBUG=True


