from django.urls import path
from gestion.views import *
from gestion.Views.book import *
from gestion.Views.sale import *
from gestion.Views.school import *
from gestion.Views.year import *
from gestion.Views.payment import *

urlpatterns = [
    path('', home, name='home'),
    path('cahiers', allcahiers, name='cahiers'),
    path('cahiers/ajouter/', ajouter_cahier, name='ajouter_cahier'),
    path('cahiers/modifier/<uuid:cahier_id>/', modifier_cahier, name='modifier_cahier'),
    path('cahiers/supprimer/<uuid:cahier_id>/', supprimer_cahier, name='supprimer_cahier'),
    path('cahiers/ajouter-stock/', ajouter_stock, name='ajouter_stock'),

    
    path('ecoles', allecoles, name='ecoles'),
    path('ecoles/ajouter/', ajouter_ecole, name='ajouter_ecole'),
    path('ecoles/modifier/<uuid:ecole_id>/', modifier_ecole, name='modifier_ecole'),
    path('ecoles/supprimer/<uuid:ecole_id>/', supprimer_ecole, name='supprimer_ecole'),

    path("ventes/", ventes, name="ventes"),
    path("ventes/ajouter/", ajouter_vente, name="ajouter_vente"),
    path("ventes/supprimer/<uuid:id>/", supprimer_vente, name="supprimer_vente"),
    path("ventes/paiement/<uuid:vente_id>/", ajouter_paiement, name="ajouter_paiement"),
    path('ventes/<uuid:vente_id>/', detail_vente, name='detail_vente'),
    path('ventes-ecole/', ventes_par_ecole, name='ventes_par_ecole'),
    path('ventes-ajax/<uuid:ecole_id>/', ventes_ajax, name='ventes_ajax'),

    path('generer-pdf-ventes/<uuid:ecole_id>/', generer_pdf_ventes_ecole, name='generer_pdf_ventes_ecole'),

    path('annees-scolaires/', gestion_annees_scolaires, name='annees_scolaires'),
    path('annees-scolaires/creer/', creer_annee_scolaire, name='creer_annee_scolaire'),
    path('annees-scolaires/activer/<uuid:annee_id>/', activer_annee_scolaire, name='activer_annee_scolaire'),
    
    path('bilans-annuels/', bilans_annuels, name='bilans_annuels'),
    path('bilans-annuels/<uuid:annee_id>/', detail_bilan_annuel, name='detail_bilan_annuel'),
    path('bilans-annuels/<uuid:annee_id>/pdf/', generer_rapport_annuel_pdf, name='generer_rapport_annuel_pdf'),
    
    # Nouvelles URLs pour les bilans mensuels
    path('bilans-mensuels/<uuid:annee_id>/', bilans_mensuels, name='bilans_mensuels'),
    path('bilans-mensuels/<uuid:annee_id>/<int:mois>/<int:annee>/', detail_bilan_mensuel, name='detail_bilan_mensuel'),
    
    path('comparaison-annees/', comparaison_annees, name='comparaison_annees'),
    #path('statistiques-cahiers/', statistiques_cahiers, name='statistiques_cahiers'),
    path('modifier-dette-vente/<uuid:vente_id>/', modifier_dette_vente, name='modifier_dette_vente'),
    path('ventes/modifier/<uuid:vente_id>/', modifier_vente, name='modifier_vente'),
    path('ventes/<uuid:vente_id>/ligne/<int:ligne_id>/modifier-quantite/', modifier_quantite_ligne, name='modifier_quantite_ligne'),
    path('ventes/<uuid:vente_id>/ligne/<int:ligne_id>/supprimer/', supprimer_ligne_vente, name='supprimer_ligne_vente'),

]