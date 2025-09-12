from django.shortcuts import *
from gestion.models import AnneeScolaire, LigneVente, Cahiers
from django.contrib import messages
import json
from decimal import Decimal

def allcahiers(request):
    cahiers = Cahiers.objects.all()
    return render(request, 'cahiers.html', {'cahiers': cahiers})


def ajouter_cahier(request):
    if request.method == "POST":
        titre = request.POST.get("titre")
        prix = Decimal(request.POST.get("prix"))
        quantite_stock = int(request.POST.get("quantite_stock"))
        Cahiers.objects.create(titre=titre, prix=prix, quantite_stock=quantite_stock)
    return redirect('cahiers')


def modifier_cahier(request, cahier_id):
    cahier = get_object_or_404(Cahiers, id=cahier_id)
    if request.method == "POST":
        cahier.titre = request.POST.get("titre")
        cahier.prix = Decimal(request.POST.get("prix"))
        cahier.quantite_stock = int(request.POST.get("quantite_stock"))
        cahier.save()
    return redirect('cahiers')


def supprimer_cahier(request, cahier_id):
    cahier = get_object_or_404(Cahiers, id=cahier_id)
    cahier.delete()
    return redirect('cahiers')

def statistiques_cahiers(request):
    annees = AnneeScolaire.objects.all()
    cahiers = Cahiers.objects.all()
    
    # Analyse globale par cahier
    stats_cahiers = []
    for cahier in cahiers:
        stats = {
            'cahier': cahier,
            'total_vendu': 0,
            'total_ca': 0,
            'annees_data': []
        }
        
        for annee in annees:
            lignes_annee = LigneVente.objects.filter(
                vente__annee_scolaire=annee,
                cahier=cahier
            )
            
            quantite_annee = sum(ligne.quantite for ligne in lignes_annee)
            ca_annee = sum(ligne.montant for ligne in lignes_annee)
            
            stats['total_vendu'] += quantite_annee
            stats['total_ca'] += ca_annee
            
            if quantite_annee > 0:
                stats['annees_data'].append({
                    'annee': annee,
                    'quantite': quantite_annee,
                    'ca': ca_annee
                })
        
        # Calculate average CA per year
        if stats['annees_data'] and len(stats['annees_data']) > 0:
            stats['ca_moyen_annuel'] = stats['total_ca'] / len(stats['annees_data'])
        else:
            stats['ca_moyen_annuel'] = 0
        
        if stats['total_vendu'] > 0:
            stats_cahiers.append(stats)
    
    # Trier par CA total
    stats_cahiers.sort(key=lambda x: x['total_ca'], reverse=True)
    
    # Top 10 pour le graphique
    top_cahiers = []
    for stat in stats_cahiers[:10]:
        top_cahiers.append({
            'titre': stat['cahier'].titre,
            'quantite': stat['total_vendu'],
            'ca': float(stat['total_ca'])
        })
    
    context = {
        'stats_cahiers': stats_cahiers,
        'annees': annees,
        'top_cahiers_json': json.dumps(top_cahiers)
    }
    return render(request, 'statistiques_cahiers.html', context)

def ajouter_stock(request):
    if request.method == 'POST':
        cahier_id = request.POST.get('cahier_id')
        quantite = int(request.POST.get('quantite', 0))

        cahier = get_object_or_404(Cahiers, id=cahier_id)
        cahier.quantite_stock += quantite
        cahier.save()

        messages.success(request, f'Stock ajouté pour le cahier "{cahier.titre}".')
    return redirect('cahiers')
