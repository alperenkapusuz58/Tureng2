from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('search/', views.search_redirect, name='search'),
    path('api/autocomplete/', views.autocomplete, name='autocomplete'),
    path('en-tr/<slug:slug>/', views.en_tr_detail, name='en_tr_detail'),
    path('tr-en/<slug:slug>/', views.tr_en_detail, name='tr_en_detail'),
]
