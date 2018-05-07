"""Tp_gkj URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter
from apps.wash_machine.api import WashMachineInfoViewSet, WashMachineStartViewSet, \
    WashMachineStopViewSet, WashMachineResetViewSet,DownloadLogsViewSet

if settings.DEBUG:
    router = DefaultRouter(schema_title='Pastebin API', schema_url='api')
else:
    router = SimpleRouter()

urlpatterns = [
    url(r'^admin/', include(admin.site.urls)),
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),
    url(r'^api/', include(router.urls)),
    url(r'^api/api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^docs/', include('rest_framework_swagger.urls'))
]

urlpatterns += [
    url(r'^info$', WashMachineInfoViewSet.as_view(), name='wash_machine_info'),
    url(r'^start$', WashMachineStartViewSet.as_view(), name='wash_machine_start'),
    url(r'^stop$', WashMachineStopViewSet.as_view(), name='wash_machine_stop'),
    url(r'^reset$', WashMachineResetViewSet.as_view(), name='wash_machine_reset'),
    url(r'^download$', DownloadLogsViewSet.as_view(), name='download_logs')
]