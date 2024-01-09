from django.urls import path, include

from django.contrib import admin
from . import views


admin.autodiscover()

import hello.views

urlpatterns = [
    path("", hello.views.index, name="index"),
    path("ask", hello.views.ask, name="ask"),
    path("question/<int:id>", hello.views.question, name="question"),
    path("db", hello.views.db, name="db"),
    path("admin/", admin.site.urls),
    path('upload-pdf/', views.upload_pdf, name='upload_pdf'),
]
