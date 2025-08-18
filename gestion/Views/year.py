from django.shortcuts import *
from gestion.models import AnneeScolaire, BilanAnneeScolaire
from django.contrib import messages
import json

def gestion_annees_scolaires(request):
    annees = AnneeScolaire.objects.all()
    annee_courante = AnneeScolaire.get_annee_courante()
    
    context = {
        'annees': annees,
        'annee_courante': annee_courante,
    }
    return render(request, 'annees_scolaires.html', context)


def creer_annee_scolaire(request):
    if request.method == 'POST':
        try:
            annee_debut = int(request.POST.get('annee_debut'))
            
            # Vérifier si l'année existe déjà
            if AnneeScolaire.objects.filter(annee_debut=annee_debut).exists():
                messages.error(request, f"L'année scolaire {annee_debut}-{annee_debut+1} existe déjà.")
            else:
                annee = AnneeScolaire.creer_annee_scolaire(annee_debut)
                messages.success(request, f"Année scolaire {annee} créée avec succès.")
                
        except ValueError:
            messages.error(request, "Année invalide.")
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
    
    return redirect('annees_scolaires')


def activer_annee_scolaire(request, annee_id):
    try:
        annee = get_object_or_404(AnneeScolaire, id=annee_id)
        annee.activer()
        messages.success(request, f"Année scolaire {annee} activée avec succès.")
    except Exception as e:
        messages.error(request, f"Erreur : {str(e)}")
    
    return redirect('annees_scolaires')

def comparaison_annees(request):
    annees = AnneeScolaire.objects.all().order_by('-annee_debut')[:5]  
    
    comparaison_data = []
    for annee in annees:
        bilan = BilanAnneeScolaire.generer_bilan(annee)
        comparaison_data.append({
            'annee': annee,
            'bilan': bilan,
            'taux_recouvrement': round((float(bilan.montant_total_paye) / float(bilan.montant_total_ventes) * 100) if bilan.montant_total_ventes > 0 else 0, 1)
        })
    
    # Calcul de l'évolution entre la première et la deuxième année
    evolution_ca = None
    if len(comparaison_data) >= 2:
        first = comparaison_data[0]
        second = comparaison_data[1]
        evolution_ca = float(first['bilan'].montant_total_ventes) - float(second['bilan'].montant_total_ventes)
    
    # Données pour le graphique de comparaison
    graphique_comparaison = []
    for data in comparaison_data:
        graphique_comparaison.append({
            'annee': str(data['annee']),
            'ventes': float(data['bilan'].montant_total_ventes),
            'paiements': float(data['bilan'].montant_total_paye),
            'nb_ventes': data['bilan'].nombre_ventes_total,
            'nb_ecoles': data['bilan'].nombre_ecoles_actives
        })
    
    # Calculs pour les cards de statistiques
    premier_ca = float(comparaison_data[0]['bilan'].montant_total_ventes) if comparaison_data else 0
    meilleur_taux = max([data['taux_recouvrement'] for data in comparaison_data]) if comparaison_data else 0
    
    context = {
        'comparaison_data': comparaison_data,
        'graphique_comparaison_json': json.dumps(graphique_comparaison),
        'evolution_ca': evolution_ca,
        'premier_ca': premier_ca,
        'meilleur_taux': meilleur_taux,
    }
    return render(request, 'comparaison_annees.html', context)
