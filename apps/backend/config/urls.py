from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def healthcheck(_request):
    return JsonResponse({"status": "ok", "service": "riskfabric-backend"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthcheck, name="healthcheck"),
    path("api/v1/", include("config.api_urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("webui.urls")),
]
