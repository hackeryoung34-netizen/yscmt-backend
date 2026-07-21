from django.urls import path
from . import api_views


urlpatterns = [

    path(
        'profile/',
        api_views.profile
    ),

]