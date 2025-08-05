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

    path('generer-pdf-ventes/<uuid:ecole_id>/', views.generer_pdf_ventes_ecole, name='generer_pdf_ventes_ecole'),



    path('annees-scolaires/', views.gestion_annees_scolaires, name='annees_scolaires'),
    path('annees-scolaires/creer/', views.creer_annee_scolaire, name='creer_annee_scolaire'),
    path('annees-scolaires/activer/<uuid:annee_id>/', views.activer_annee_scolaire, name='activer_annee_scolaire'),
    
    path('bilans-annuels/', views.bilans_annuels, name='bilans_annuels'),
    path('bilans-annuels/<uuid:annee_id>/', views.detail_bilan_annuel, name='detail_bilan_annuel'),
    path('bilans-annuels/<uuid:annee_id>/pdf/', views.generer_rapport_annuel_pdf, name='generer_rapport_annuel_pdf'),
    
    # Nouvelles URLs pour les bilans mensuels
    path('bilans-mensuels/<uuid:annee_id>/', views.bilans_mensuels, name='bilans_mensuels'),
    path('bilans-mensuels/<uuid:annee_id>/<int:mois>/<int:annee>/', views.detail_bilan_mensuel, name='detail_bilan_mensuel'),
    
    path('comparaison-annees/', views.comparaison_annees, name='comparaison_annees'),
    #path('statistiques-cahiers/', views.statistiques_cahiers, name='statistiques_cahiers'),
]