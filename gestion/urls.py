from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('cahiers', views.allcahiers, name='cahiers'),
    path('cahiers/ajouter/', views.ajouter_cahier, name='ajouter_cahier'),
    path('cahiers/modifier/<uuid:cahier_id>/', views.modifier_cahier, name='modifier_cahier'),
    path('cahiers/supprimer/<uuid:cahier_id>/', views.supprimer_cahier, name='supprimer_cahier'),
    path('cahiers/ajouter-stock/', views.ajouter_stock, name='ajouter_stock'),

    
    path('ecoles', views.allecoles, name='ecoles'),
    path('ecoles/ajouter/', views.ajouter_ecole, name='ajouter_ecole'),
    path('ecoles/modifier/<uuid:ecole_id>/', views.modifier_ecole, name='modifier_ecole'),
    path('ecoles/supprimer/<uuid:ecole_id>/', views.supprimer_ecole, name='supprimer_ecole'),

    path("ventes/", views.ventes, name="ventes"),
    path("ventes/ajouter/", views.ajouter_vente, name="ajouter_vente"),
    path("ventes/supprimer/<uuid:id>/", views.supprimer_vente, name="supprimer_vente"),
    path("ventes/paiement/<uuid:vente_id>/", views.ajouter_paiement, name="ajouter_paiement"),
    path('ventes/<uuid:vente_id>/', views.detail_vente, name='detail_vente'),
    path('ventes-ecole/', views.ventes_par_ecole, name='ventes_par_ecole'),
    path('ventes-ajax/<uuid:ecole_id>/', views.ventes_ajax, name='ventes_ajax'),
]