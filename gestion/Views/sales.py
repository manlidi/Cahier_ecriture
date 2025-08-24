from django.shortcuts import *
from gestion.models import Vente, AnneeScolaire, Ecoles
from django.db.models import Sum
from decimal import Decimal
from gestion.models import Cahiers
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404, redirect
from gestion.models import LigneVente, Paiement, Cahiers
from decimal import Decimal
from django.core.paginator import Paginator
import json


def liste_ventes(request):
    """Liste des ventes avec filtres par école et année scolaire"""
    # Récupérer les filtres GET
    ecole_id = request.GET.get('ecole')
    annee_id = request.GET.get('annee')
    
    # Si aucun filtre d'année n'est spécifié, utiliser l'année active par défaut
    if not annee_id:
        annee_active = AnneeScolaire.get_annee_courante()
        if annee_active:
            annee_id = str(annee_active.id)

    # Préparer les queryset de base
    ventes_qs = Vente.objects.select_related('ecole', 'annee_scolaire')\
        .order_by('-created_at')

    if ecole_id:
        ventes_qs = ventes_qs.filter(ecole__id=ecole_id)
    if annee_id:
        ventes_qs = ventes_qs.filter(annee_scolaire__id=annee_id)

    # Calculs et sérialisation légère pour le template
    ventes = []
    for v in ventes_qs:
        # Calculs manuels pour éviter les doublons des annotations SQL
        total_lignes = v.lignes.aggregate(total=Sum('montant'))['total'] or Decimal('0')
        montant_paye = v.paiements.aggregate(total=Sum('montant'))['total'] or Decimal('0')
        dette = v.dette_precedente if getattr(v, 'dette_precedente', None) is not None else Decimal('0')
        montant_total = total_lignes + dette
        montant_restant = max(Decimal('0'), montant_total - montant_paye)  # Ne peut pas être négatif

        # Calculer les dettes des autres ventes de la même école (différentes années scolaires)
        autres_ventes = Vente.objects.filter(ecole=v.ecole)\
            .exclude(annee_scolaire=v.annee_scolaire)\
            .select_related('annee_scolaire')\
            .annotate(
                total_lignes_autre=Sum('lignes__montant'),
                total_paye_autre=Sum('paiements__montant')
            )
        
        dettes_autres_annees = []
        total_dettes_autres = Decimal('0')
        annees_dettes = {}  # Pour grouper par année
        
        for autre in autres_ventes:
            total_lignes_autre = autre.total_lignes_autre or Decimal('0')
            dette_precedente_autre = autre.dette_precedente or Decimal('0')
            total_autre = total_lignes_autre + dette_precedente_autre
            paye_autre = autre.total_paye_autre or Decimal('0')
            restant_autre = total_autre - paye_autre
            
            if restant_autre > 0:
                annee_str = str(autre.annee_scolaire)
                if annee_str in annees_dettes:
                    annees_dettes[annee_str] += restant_autre
                else:
                    annees_dettes[annee_str] = restant_autre
        
        # Convertir en liste pour le JSON
        for annee_str, montant in annees_dettes.items():
            dettes_autres_annees.append({
                'annee_scolaire': annee_str,
                'montant_restant': float(montant)
            })
            total_dettes_autres += montant

        ventes.append({
            'id': v.id,
            'short_id': str(v.id)[:8],
            'ecole': v.ecole,
            'annee_scolaire': v.annee_scolaire,
            'created_at': v.created_at,
            'montant_total': float(montant_total),
            'montant_paye': float(montant_paye),
            'montant_restant': float(montant_restant),
            'lignes_count': v.lignes.count(),
            'dettes_autres_annees': dettes_autres_annees,
            'dettes_autres_json': json.dumps(dettes_autres_annees),
            'total_dettes_autres': float(total_dettes_autres),
        })

    # Pagination
    paginator = Paginator(ventes, 10)  # 10 ventes par page
    page_number = request.GET.get('page')
    ventes_page = paginator.get_page(page_number)

    # Choix pour les filtres
    annees = AnneeScolaire.objects.all()
    ecoles = Ecoles.objects.all()
    cahiers = Cahiers.objects.all()

    context = {
        'ventes': ventes_page,
        'annees': annees,
        'ecoles': ecoles,
        'cahiers': cahiers,
        'selected_ecole': ecole_id,
        'selected_annee': annee_id,
    }
    return render(request, 'ventes.html', context)


def ventes_par_ecole(request):
    """Page historique: permet de choisir une école et voir son historique"""
    ecoles = Ecoles.objects.all()
    return render(request, 'historique.html', {'ecoles': ecoles})


@require_GET
def ventes_ajax(request, ecole_id):
    """Retourne JSON des ventes pour une école (utilisé en AJAX)"""
    ventes = Vente.objects.filter(ecole_id=ecole_id).prefetch_related('paiements', 'lignes')
    data = []
    for vente in ventes:
        montant_lignes = vente.lignes.aggregate(total=Sum('montant'))['total'] or Decimal('0')
        montant_paye = vente.paiements.aggregate(total=Sum('montant'))['total'] or Decimal('0')
        data.append({
            'id': str(vente.id),
            'date': vente.created_at.isoformat(),
            'montant_total': float(montant_lignes + (vente.dette_precedente or Decimal('0'))),
            'montant_paye': float(montant_paye),
            'montant_restant': float((montant_lignes + (vente.dette_precedente or Decimal('0'))) - montant_paye),
        })
    return JsonResponse({'ventes': data})


def vente_detail(request, vente_id):
    vente = get_object_or_404(Vente, id=vente_id)
    lignes = vente.lignes.select_related('cahier').all()
    paiements = vente.paiements.all()

    # Calculs
    montant_lignes = lignes.aggregate(total=Sum('montant'))['total'] or Decimal('0')
    montant_paye = paiements.aggregate(total=Sum('montant'))['total'] or Decimal('0')
    montant_total = montant_lignes + (vente.dette_precedente or Decimal('0'))
    montant_restant = montant_total - montant_paye

    # Obtenir les sessions d'ajout d'articles
    sessions = vente.get_articles_par_session()

    # Grouper les articles par type pour la vue classique
    from collections import defaultdict
    articles_groupes = defaultdict(lambda: {'quantite_totale': 0, 'montant_total': Decimal('0'), 'cahier': None})
    
    for ligne in lignes:
        key = ligne.cahier.id
        articles_groupes[key]['cahier'] = ligne.cahier
        articles_groupes[key]['quantite_totale'] += ligne.quantite
        articles_groupes[key]['montant_total'] += ligne.montant
    
    ligne_ventes = list(articles_groupes.values())

    # Related ventes for the same ecole & annee (grouped by date)
    related = Vente.objects.filter(ecole=vente.ecole, annee_scolaire=vente.annee_scolaire).exclude(id=vente.id).order_by('-created_at')
    groups = {}
    for rv in related:
        key = rv.created_at.date().isoformat()
        groups.setdefault(key, []).append(rv)

    context = {
        'vente': vente,
        'lignes': lignes,
        'ligne_ventes': ligne_ventes,  # Articles groupés par type
        'sessions': sessions,  # Articles groupés par session d'ajout
        'paiements': paiements,
        'montant_total': montant_total,
        'montant_paye': montant_paye,
        'montant_restant': montant_restant,
        'related_groups': groups,
    }
    return render(request, 'vente_detail.html', context)


def modifier_vente(request, vente_id):
    vente = get_object_or_404(Vente, id=vente_id)
    if request.method == 'POST':
        # Support multiple articles via JSON in 'articles' or fallback to single cahier_id/quantite
        import json as _json
        articles_json = request.POST.get('articles')
        if articles_json:
            try:
                articles = _json.loads(articles_json)
            except Exception:
                articles = []
        else:
            # fallback single
            cahier_id = request.POST.get('cahier_id')
            quantite = int(request.POST.get('quantite', 0)) if request.POST.get('quantite') else 0
            articles = []
            if cahier_id and quantite > 0:
                articles.append({'cahier_id': cahier_id, 'quantite': quantite})

        # Préparer les données pour la nouvelle méthode
        articles_data = []
        for art in articles:
            try:
                cahier = get_object_or_404(Cahiers, id=art.get('cahier_id'))
                quantite = int(art.get('quantite', 0))
                if quantite <= 0:
                    continue
                articles_data.append({
                    'cahier': cahier,
                    'quantite': quantite
                })
            except Exception:
                continue
        
        # Utiliser la nouvelle méthode avec traçabilité
        if articles_data:
            description = f"Ajout de {len(articles_data)} type(s) d'articles via interface web"
            vente.ajouter_articles(articles_data, description_session=description)
            
    return redirect('vente_detail', vente_id=vente.id)


def gerer_paiement(request, vente_id):
    vente = get_object_or_404(Vente, id=vente_id)
    if request.method == 'POST':
        montant_donne = Decimal(request.POST.get('montant', '0') or '0')
        
        # Calculer le montant restant de la vente courante
        montant_lignes = vente.lignes.aggregate(total=Sum('montant'))['total'] or Decimal('0')
        dette_precedente = vente.dette_precedente or Decimal('0')
        montant_total_vente = montant_lignes + dette_precedente
        montant_paye_actuel = vente.paiements.aggregate(total=Sum('montant'))['total'] or Decimal('0')
        montant_restant_vente = max(Decimal('0'), montant_total_vente - montant_paye_actuel)
        
        # Calculer le total des dettes des autres années
        autres_ventes = Vente.objects.filter(ecole=vente.ecole)\
            .exclude(annee_scolaire=vente.annee_scolaire)\
            .select_related('annee_scolaire')\
            .annotate(
                total_lignes_autre=Sum('lignes__montant'),
                total_paye_autre=Sum('paiements__montant')
            )\
            .order_by('-annee_scolaire__annee_debut')
        
        total_dettes_autres = Decimal('0')
        autres_ventes_avec_dettes = []
        
        for autre_vente in autres_ventes:
            total_lignes_autre = autre_vente.total_lignes_autre or Decimal('0')
            dette_precedente_autre = autre_vente.dette_precedente or Decimal('0')
            total_autre = total_lignes_autre + dette_precedente_autre
            paye_autre = autre_vente.total_paye_autre or Decimal('0')
            restant_autre = max(Decimal('0'), total_autre - paye_autre)
            
            if restant_autre > 0:
                total_dettes_autres += restant_autre
                autres_ventes_avec_dettes.append((autre_vente, restant_autre))
        
        # Montant total maximum qu'on peut accepter
        montant_total_acceptable = montant_restant_vente + total_dettes_autres
        
        # Limiter le montant du paiement au montant acceptable
        montant_paiement = min(montant_donne, montant_total_acceptable)
        montant_excedent = montant_donne - montant_paiement
        
        if montant_paiement > 0:
            # Enregistrer le paiement pour la vente courante
            last = vente.paiements.order_by('-numero_tranche').first()
            numero = (last.numero_tranche + 1) if last else 1
            
            # Montant à appliquer à cette vente
            montant_pour_vente_courante = min(montant_paiement, montant_restant_vente)
            
            if montant_pour_vente_courante > 0:
                Paiement.objects.create(
                    vente=vente, 
                    montant=montant_pour_vente_courante, 
                    numero_tranche=numero
                )
            
            # Calculer l'excédent pour les autres ventes
            excedent = montant_paiement - montant_pour_vente_courante
            
            # Appliquer l'excédent aux autres ventes
            for autre_vente, restant_autre in autres_ventes_avec_dettes:
                if excedent <= 0:
                    break
                
                # Montant à appliquer à cette autre vente
                montant_pour_autre_vente = min(excedent, restant_autre)
                
                # Trouver le dernier numéro de tranche pour cette vente
                last_autre = autre_vente.paiements.order_by('-numero_tranche').first()
                numero_autre = (last_autre.numero_tranche + 1) if last_autre else 1
                
                # Créer le paiement pour l'autre vente
                Paiement.objects.create(
                    vente=autre_vente,
                    montant=montant_pour_autre_vente,
                    numero_tranche=numero_autre
                )
                
                # Réduire l'excédent
                excedent -= montant_pour_autre_vente
        
        # Ajouter un message d'information si il y a eu un excédent refusé APRÈS avoir payé toutes les dettes
        if montant_excedent > 0:
            from django.contrib import messages
            messages.info(request, f"Paiement effectué avec succès. Montant rendu à l'utilisateur : {montant_excedent} F")
    
    return redirect('vente_detail', vente_id=vente.id)


def creer_vente(request):
    """Créer une nouvelle vente avec articles via modal ou ajouter articles à une vente existante"""
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            ecole_id = request.POST.get('ecole_id')
            annee_id = request.POST.get('annee_id')
            dette_precedente = request.POST.get('dette_precedente', '0')
            
            # Validation des champs obligatoires
            if not ecole_id or not annee_id:
                return JsonResponse({
                    'success': False, 
                    'error': 'École et année scolaire sont obligatoires'
                })
            
            # Récupérer les objets
            ecole = get_object_or_404(Ecoles, id=ecole_id)
            annee = get_object_or_404(AnneeScolaire, id=annee_id)
            
            # Vérifier si une vente existe déjà pour cette école et année
            vente_existante = Vente.objects.filter(ecole=ecole, annee_scolaire=annee).first()
            
            if vente_existante:
                # Utiliser la vente existante
                vente = vente_existante
                action_message = 'Articles ajoutés à la vente existante'
            else:
                # Créer une nouvelle vente
                vente = Vente.objects.create(
                    ecole=ecole,
                    annee_scolaire=annee,
                    dette_precedente=Decimal(dette_precedente) if dette_precedente else Decimal('0')
                )
                action_message = 'Nouvelle vente créée avec succès'
            
            # Traiter les articles (format JSON comme pour modifier_vente)
            import json as _json
            articles_json = request.POST.get('articles')
            articles_data = []
            
            if articles_json:
                try:
                    articles = _json.loads(articles_json)
                    for art in articles:
                        cahier_id = art.get('cahier_id')
                        quantite = int(art.get('quantite', 0))
                        
                        if cahier_id and quantite > 0:
                            try:
                                cahier = Cahiers.objects.get(id=cahier_id)
                                articles_data.append({
                                    'cahier': cahier,
                                    'quantite': quantite
                                })
                            except Cahiers.DoesNotExist:
                                pass  # Ignorer les cahiers inexistants
                except (ValueError, TypeError):
                    pass  # Ignorer les erreurs de parsing JSON
            
            if not articles_data:
                return JsonResponse({
                    'success': False,
                    'error': 'Veuillez ajouter au moins un article valide'
                })
            
            # Ajouter les articles à la vente
            if articles_data:
                vente.ajouter_articles(articles_data)
            
            return JsonResponse({
                'success': True,
                'message': action_message,
                'vente_id': vente.id,
                'redirect_url': f'/ventes/{vente.id}/'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Erreur lors de la création : {str(e)}'
            })
    
    return JsonResponse({
        'success': False, 
        'error': 'Méthode non autorisée'
    })
