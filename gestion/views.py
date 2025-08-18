from django.shortcuts import *
from .models import *
from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.lib.units import cm
from io import BytesIO
from django.db.models import Sum, Count, Q, F
from django.contrib import messages
from decimal import Decimal
import json
from django.utils import timezone
from datetime import datetime, timedelta
from django.http import JsonResponse
import os
from django.conf import settings
from PyPDF2 import PdfReader, PdfWriter, PageObject
from django.core.paginator import Paginator
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
import calendar
from decimal import InvalidOperation



def home(request):
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    last_week = today - timedelta(days=7)
    last_month = today - timedelta(days=30)
    
    # Année scolaire courante
    annee_courante = AnneeScolaire.get_annee_courante()
    if not annee_courante:
        # Créer automatiquement l'année scolaire courante si elle n'existe pas
        annee_courante_num = today.year if today.month >= 7 else today.year - 1
        annee_courante = AnneeScolaire.creer_annee_scolaire(annee_courante_num)
        annee_courante.activer()
    
    # Filtrer les données par année scolaire courante
    ventes_annee = Vente.objects.filter(annee_scolaire=annee_courante)
    paiements_annee = Paiement.objects.filter(vente__annee_scolaire=annee_courante)
    
    # Revenus d'aujourd'hui (année courante)
    revenus_aujourd_hui = paiements_annee.filter(
        date_paiement=today
    ).aggregate(total=Sum('montant'))['total'] or 0
    
    # Revenus de la semaine dernière pour comparaison
    revenus_semaine_derniere = paiements_annee.filter(
        date_paiement__range=[last_week, yesterday]
    ).aggregate(total=Sum('montant'))['total'] or 0
    
    # Calcul du pourcentage d'augmentation
    if revenus_semaine_derniere > 0:
        pourcentage_revenus = ((revenus_aujourd_hui - revenus_semaine_derniere) / revenus_semaine_derniere) * 100
    else:
        pourcentage_revenus = 100 if revenus_aujourd_hui > 0 else 0
    
    # Nombre d'écoles actives aujourd'hui (année courante)
    ecoles_actives_aujourd_hui = ventes_annee.filter(
        created_at__date=today
    ).values('ecole').distinct().count()
    
    # Écoles actives le mois dernier
    ecoles_actives_mois_dernier = ventes_annee.filter(
        created_at__date__range=[last_month, yesterday]
    ).values('ecole').distinct().count()
    
    # Pourcentage d'écoles actives
    if ecoles_actives_mois_dernier > 0:
        pourcentage_ecoles = ((ecoles_actives_aujourd_hui - ecoles_actives_mois_dernier) / ecoles_actives_mois_dernier) * 100
    else:
        pourcentage_ecoles = 100 if ecoles_actives_aujourd_hui > 0 else 0
    
    # Nombre de ventes aujourd'hui (année courante)
    ventes_aujourd_hui = ventes_annee.filter(created_at__date=today).count()
    ventes_hier = ventes_annee.filter(created_at__date=yesterday).count()
    
    if ventes_hier > 0:
        pourcentage_ventes = ((ventes_aujourd_hui - ventes_hier) / ventes_hier) * 100
    else:
        pourcentage_ventes = 100 if ventes_aujourd_hui > 0 else 0
    
    # Chiffre d'affaires total (année courante)
    ca_total = paiements_annee.aggregate(total=Sum('montant'))['total'] or 0
    ca_hier = paiements_annee.filter(date_paiement=yesterday).aggregate(total=Sum('montant'))['total'] or 0
    
    if ca_hier > 0:
        pourcentage_ca = ((revenus_aujourd_hui - ca_hier) / ca_hier) * 100
    else:
        pourcentage_ca = 100 if revenus_aujourd_hui > 0 else 0
    
    # Données pour les graphiques (7 derniers jours, année courante)
    ventes_par_jour = []
    for i in range(7):
        date = today - timedelta(days=6-i)
        count = ventes_annee.filter(created_at__date=date).count()
        ventes_par_jour.append({
            'date': date.strftime('%d/%m'),
            'count': count
        })
    
    # Revenus par jour (7 derniers jours, année courante)
    revenus_par_jour = []
    for i in range(7):
        date = today - timedelta(days=6-i)
        revenus = paiements_annee.filter(date_paiement=date).aggregate(total=Sum('montant'))['total'] or 0
        revenus_par_jour.append({
            'date': date.strftime('%d/%m'),
            'revenus': float(revenus)
        })
    
    # Top 5 des écoles par chiffre d'affaires (année courante)
    top_ecoles = ventes_annee.values(
        'ecole__nom'
    ).annotate(
        total_ca=Sum('paiements__montant'),
        nb_ventes=Count('id', distinct=True)
    ).order_by('-total_ca')[:5]
    
    # Ventes en retard (année courante)
    ventes_en_retard = ventes_annee.filter(
        date_paiement__lt=today
    ).exclude(
        id__in=ventes_annee.filter(paiements__isnull=False).filter(
            paiements__montant__gte=models.F('lignes__montant')
        ).values('id')
    ).count()
    
    # Activités récentes (année courante)
    activites_recentes = []
    
    # Derniers paiements
    derniers_paiements = paiements_annee.select_related('vente__ecole').order_by('-date_paiement')[:3]
    for paiement in derniers_paiements:
        activites_recentes.append({
            'type': 'paiement',
            'description': f"{paiement.montant}F, Paiement reçu de {paiement.vente.ecole.nom}",
            'date': paiement.date_paiement,
            'icon': 'payments'
        })
    
    # Dernières ventes
    dernieres_ventes = ventes_annee.select_related('ecole').order_by('-created_at')[:3]
    for vente in dernieres_ventes:
        activites_recentes.append({
            'type': 'vente',
            'description': f"Nouvelle vente #{str(vente.id)[:8]}... à {vente.ecole.nom}",
            'date': vente.created_at.date(),
            'icon': 'shopping_cart'
        })
    
    # Trier les activités par date
    activites_recentes.sort(key=lambda x: x['date'], reverse=True)
    activites_recentes = activites_recentes[:3]  
    
    # Données sur les stocks
    stock_faible = Cahiers.objects.filter(quantite_stock__lt=10).count()
    total_cahiers = Cahiers.objects.count()
    
    context = {
        # Année scolaire
        'annee_courante': annee_courante,
        
        # Métriques principales
        'revenus_aujourd_hui': revenus_aujourd_hui,
        'pourcentage_revenus': round(pourcentage_revenus, 1),
        'ecoles_actives': ecoles_actives_aujourd_hui,
        'pourcentage_ecoles': round(pourcentage_ecoles, 1),
        'ventes_aujourd_hui': ventes_aujourd_hui,
        'pourcentage_ventes': round(pourcentage_ventes, 1),
        'ca_total': ca_total,
        'pourcentage_ca': round(pourcentage_ca, 1),
        
        # Données pour graphiques (JSON)
        'ventes_par_jour_json': json.dumps(ventes_par_jour),
        'revenus_par_jour_json': json.dumps(revenus_par_jour),
        
        # Tableaux et listes
        'top_ecoles': top_ecoles,
        'activites_recentes': activites_recentes,
        'ventes_en_retard': ventes_en_retard,
        'stock_faible': stock_faible,
        'total_cahiers': total_cahiers,
        
        # Données brutes pour graphiques
        'ventes_par_jour': ventes_par_jour,
        'revenus_par_jour': revenus_par_jour,
    }
    return render(request, 'index.html', context)


def allcahiers(request):
    cahiers = Cahiers.objects.all()
    return render(request, 'cahiers.html', {'cahiers': cahiers})


def ajouter_cahier(request):
    if request.method == "POST":
        titre = request.POST.get("titre")
        prix = int(request.POST.get("prix"))
        quantite_stock = int(request.POST.get("quantite_stock"))
        Cahiers.objects.create(titre=titre, prix=prix, quantite_stock=quantite_stock)
    return redirect('cahiers')


def modifier_cahier(request, cahier_id):
    cahier = get_object_or_404(Cahiers, id=cahier_id)
    if request.method == "POST":
        cahier.titre = request.POST.get("titre")
        cahier.prix = int(request.POST.get("prix"))
        cahier.quantite_stock = int(request.POST.get("quantite_stock"))
        cahier.save()
    return redirect('cahiers')


def supprimer_cahier(request, cahier_id):
    cahier = get_object_or_404(Cahiers, id=cahier_id)
    cahier.delete()
    return redirect('cahiers')


def allecoles(request):
    ecoles = Ecoles.objects.all()
    return render(request, 'ecoles.html', {'ecoles': ecoles})


def ajouter_ecole(request):
    if request.method == "POST":
        nom = request.POST.get("nom")
        adresse = request.POST.get("adresse")
        Ecoles.objects.create(nom=nom, adresse=adresse)
    return redirect('ecoles')


def modifier_ecole(request, ecole_id):
    ecole = get_object_or_404(Ecoles, id=ecole_id)
    if request.method == "POST":
        ecole.nom = request.POST.get("nom")
        ecole.adresse = request.POST.get("adresse")
        ecole.save()
    return redirect('ecoles')


def supprimer_ecole(request, ecole_id):
    ecole = get_object_or_404(Ecoles, id=ecole_id)
    ecole.delete()
    return redirect('ecoles')

def ventes(request):
    # Recherche des ventes en retard
    ventes_en_retard = Vente.objects.filter(
        date_paiement__lt=timezone.now()
    ).exclude(id__in=Vente.objects.filter(paiements__isnull=False).annotate(
        total_paye=models.Sum('paiements__montant')
    ).filter(total_paye__gte=models.F('lignes__montant')))

    if ventes_en_retard.exists():
        messages.warning(request, f"Attention : {ventes_en_retard.count()} vente(s) en retard de paiement !")

    # Filtrage par nom d'école (recherche)
    search_query = request.GET.get('search', '').strip()
    ventes_liste = Vente.objects.select_related('ecole').prefetch_related('lignes__cahier', 'paiements').order_by('-created_at')  # Ajouter order_by

    if search_query:
        ventes_liste = ventes_liste.filter(ecole__nom__icontains=search_query)

    # Pagination
    paginator = Paginator(ventes_liste, 5)  # 5 ventes par page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'cahiers': Cahiers.objects.all(),
        'ecoles': Ecoles.objects.all()
    }
    return render(request, 'ventes.html', context)

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


def bilans_annuels(request):
    annees = AnneeScolaire.objects.all()
    bilans = []
    
    for annee in annees:
        # Générer ou récupérer le bilan
        bilan = BilanAnneeScolaire.generer_bilan(annee)
        bilans.append({
            'annee': annee,
            'bilan': bilan,
            'pourcentage_paye': round((float(bilan.montant_total_paye) / float(bilan.montant_total_ventes) * 100) if bilan.montant_total_ventes > 0 else 0, 1)
        })
    
    context = {
        'bilans': bilans,
    }
    return render(request, 'bilans_annuels.html', context)


def detail_bilan_annuel(request, annee_id):
    annee = get_object_or_404(AnneeScolaire, id=annee_id)
    bilan = BilanAnneeScolaire.generer_bilan(annee)
    
    # Préparer les données pour les graphiques
    cahiers_data = []
    for cahier_id, data in bilan.ventes_par_cahier.items():
        if data['quantite_vendue'] > 0:
            cahiers_data.append({
                'titre': data['titre'],
                'quantite_vendue': data['quantite_vendue'],
                'ca_genere': data['ca_genere'],
                'prix_unitaire': data['prix_unitaire'],
                'stock_actuel': data['stock_actuel']
            })
    
    # Trier par CA généré
    cahiers_data.sort(key=lambda x: x['ca_genere'], reverse=True)
    
    # Top 5 des écoles pour cette année
    top_ecoles = Vente.objects.filter(annee_scolaire=annee).values(
        'ecole__nom'
    ).annotate(
        total_ca=Sum('lignes__montant'),
        nb_ventes=Count('id', distinct=True),
        total_paye=Sum('paiements__montant')
    ).order_by('-total_ca')[:5]
    
    context = {
        'annee': annee,
        'bilan': bilan,
        'cahiers_data': cahiers_data,
        'top_ecoles': top_ecoles,
        'pourcentage_paye': round((float(bilan.montant_total_paye) / float(bilan.montant_total_ventes) * 100) if bilan.montant_total_ventes > 0 else 0, 1),
        'cahiers_json': json.dumps([{
            'titre': item['titre'],
            'quantite': item['quantite_vendue'],
            'ca': float(item['ca_genere'])
        } for item in cahiers_data[:10]]) 
    }
    return render(request, 'detail_bilan_annuel.html', context)


def bilans_mensuels(request, annee_id):
    annee = get_object_or_404(AnneeScolaire, id=annee_id)

    # Générer tous les bilans mensuels
    bilans_mensuels = BilanMensuel.generer_tous_bilans_mensuels(annee)

    for bilan in bilans_mensuels:
        bilan.montant_impaye = float(bilan.montant_ventes) - float(bilan.montant_paye)
        if bilan.montant_ventes > 0:
            bilan.taux_recouvrement = round((bilan.montant_paye / bilan.montant_ventes) * 100, 1)
        else:
            bilan.taux_recouvrement = 0

    # Préparer les données pour les graphiques
    graphique_data = []
    for bilan in bilans_mensuels:
        graphique_data.append({
            'mois': f"{bilan.nom_mois} {bilan.annee}",
            'mois_court': f"{bilan.mois:02d}/{str(bilan.annee)[2:]}",
            'ventes': float(bilan.montant_ventes),
            'paiements': float(bilan.montant_paye),
            'nombre_ventes': bilan.nombre_ventes
        })

    # Calculs des totaux
    total_ventes = sum(float(b.montant_ventes) for b in bilans_mensuels)
    total_paiements = sum(float(b.montant_paye) for b in bilans_mensuels)
    total_nombre_ventes = sum(b.nombre_ventes for b in bilans_mensuels)

    # NOUVEAU : Statistiques des cahiers pour toute l'année
    from django.db.models import Sum
    from collections import defaultdict
    
    # Récupérer toutes les lignes de vente pour cette année scolaire
    lignes_ventes = LigneVente.objects.filter(
        vente__annee_scolaire=annee
    ).select_related('cahier')
    
    # Grouper par cahier
    cahiers_stats_dict = defaultdict(lambda: {
        'quantite_vendue': 0,
        'ca_genere': 0,
        'titre': '',
        'prix_unitaire': 0,
        'stock_actuel': 0
    })
    
    for ligne in lignes_ventes:
        cahier_id = ligne.cahier.id
        cahiers_stats_dict[cahier_id]['titre'] = ligne.cahier.titre
        cahiers_stats_dict[cahier_id]['prix_unitaire'] = ligne.cahier.prix
        cahiers_stats_dict[cahier_id]['stock_actuel'] = ligne.cahier.quantite_stock
        cahiers_stats_dict[cahier_id]['quantite_vendue'] += ligne.quantite
        cahiers_stats_dict[cahier_id]['ca_genere'] += float(ligne.montant)
    
    # Convertir en liste et trier par CA généré
    cahiers_stats = list(cahiers_stats_dict.values())
    cahiers_stats.sort(key=lambda x: x['ca_genere'], reverse=True)
    
    # Calculer les pourcentages du CA total
    total_ca_cahiers = sum(item['ca_genere'] for item in cahiers_stats)
    for cahier_stat in cahiers_stats:
        if total_ca_cahiers > 0:
            cahier_stat['pourcentage_ca'] = (cahier_stat['ca_genere'] / total_ca_cahiers) * 100
        else:
            cahier_stat['pourcentage_ca'] = 0
    
    # Total des cahiers vendus
    total_cahiers_vendus = sum(item['quantite_vendue'] for item in cahiers_stats)
    
    # Top 5 pour le graphique
    top5_cahiers = cahiers_stats[:5]
    cahiers_top5_json = json.dumps([{
        'titre': item['titre'],
        'quantite': item['quantite_vendue'],
        'ca': item['ca_genere']
    } for item in top5_cahiers])

    context = {
        'annee': annee,
        'bilans_mensuels': bilans_mensuels,
        'total_ventes': total_ventes,
        'total_paiements': total_paiements,
        'total_nombre_ventes': total_nombre_ventes,
        'pourcentage_paye': round((total_paiements / total_ventes * 100) if total_ventes > 0 else 0, 1),
        'graphique_data_json': json.dumps(graphique_data),
        
        # Nouvelles données pour les cahiers
        'cahiers_stats': cahiers_stats,
        'total_cahiers_vendus': total_cahiers_vendus,
        'total_ca_cahiers': total_ca_cahiers,
        'cahiers_top5_json': cahiers_top5_json,
    }
    return render(request, 'bilans_mensuels.html', context)


def detail_bilan_mensuel(request, annee_id, mois, annee):
    annee_scolaire = get_object_or_404(AnneeScolaire, id=annee_id)
    bilan = BilanMensuel.generer_bilan_mois(annee_scolaire, mois, annee)

    # Calcul du taux de recouvrement
    if bilan.montant_ventes > 0:
        bilan.taux_recouvrement = round((bilan.montant_paye / bilan.montant_ventes) * 100, 1)
    else:
        bilan.taux_recouvrement = 0

    # Déterminer début et fin de mois
    debut_mois = date(annee, mois, 1)
    if mois == 12:
        fin_mois = date(annee + 1, 1, 1) - timezone.timedelta(days=1)
    else:
        fin_mois = date(annee, mois + 1, 1) - timezone.timedelta(days=1)

    # Récupérer les ventes
    ventes_mois = Vente.objects.filter(
        annee_scolaire=annee_scolaire,
        created_at__date__range=[debut_mois, fin_mois]
    ).select_related('ecole').prefetch_related('lignes__cahier', 'paiements')

    # Paiements du mois
    paiements_mois = Paiement.objects.filter(
        vente__annee_scolaire=annee_scolaire,
        date_paiement__range=[debut_mois, fin_mois]
    ).select_related('vente__ecole')

    # Données des cahiers
    cahiers_data = list(bilan.ventes_par_cahier.values())

    context = {
        'annee_scolaire': annee_scolaire,
        'bilan': bilan,
        'ventes_mois': ventes_mois,
        'paiements_mois': paiements_mois,
        'cahiers_data': cahiers_data,
        'mois_nom': calendar.month_name[mois],
        'debut_mois': debut_mois,
        'fin_mois': fin_mois,
    }
    return render(request, 'detail_bilan_mensuel.html', context)


def generer_rapport_annuel_pdf(request, annee_id):
    annee = get_object_or_404(AnneeScolaire, id=annee_id)
    bilan = BilanAnneeScolaire.generer_bilan(annee)
    
    # Créer le PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    story = []
    styles = getSampleStyleSheet()
    
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        wordWrap='CJK',
        alignment=0, 
        spaceBefore=2,
        spaceAfter=2
    )
    
    cell_style_center = ParagraphStyle(
        'CellStyleCenter',
        parent=cell_style,
        alignment=1 
    )
    
    # Titre
    story.append(Spacer(1, 0.5 * cm))
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1  
    )
    story.append(Paragraph(f"RAPPORT ANNUEL - {annee.libelle.upper()}", title_style))
    
    # Résumé exécutif
    story.append(Paragraph("<b>RÉSUMÉ EXÉCUTIF</b>", styles['Heading2']))
    story.append(Spacer(1, 0.3 * cm))
    
    resume_data = [
        [Paragraph("Nombre total de ventes", cell_style), Paragraph(str(bilan.nombre_ventes_total), cell_style_center)],
        [Paragraph("Montant total des ventes", cell_style), Paragraph(f"{bilan.montant_total_ventes:.0f} F CFA", cell_style_center)],
        [Paragraph("Montant total payé", cell_style), Paragraph(f"{bilan.montant_total_paye:.0f} F CFA", cell_style_center)],
        [Paragraph("Montant impayé", cell_style), Paragraph(f"{bilan.montant_total_impaye:.0f} F CFA", cell_style_center)],
        [Paragraph("Taux de recouvrement", cell_style), Paragraph(f"{(float(bilan.montant_total_paye) / float(bilan.montant_total_ventes) * 100):.1f}%" if bilan.montant_total_ventes > 0 else "0%", cell_style_center)],
        [Paragraph("Nombre d'écoles actives", cell_style), Paragraph(str(bilan.nombre_ecoles_actives), cell_style_center)],
    ]
    
    resume_table = Table(resume_data, colWidths=[10*cm, 6*cm])
    resume_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),  
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(resume_table)
    story.append(Spacer(1, 0.5 * cm))
    
    # Analyse par cahier
    story.append(Paragraph("<b>ANALYSE PAR CAHIER</b>", styles['Heading2']))
    story.append(Spacer(1, 0.3 * cm))
    
    # En-têtes du tableau cahiers avec Paragraph pour gérer le retour à la ligne
    cahiers_data = [
        [
            Paragraph("Titre du cahier", cell_style_center),
            Paragraph("Quantité vendue", cell_style_center),
            Paragraph("CA généré (F CFA)", cell_style_center),
            Paragraph("Prix unitaire", cell_style_center),
            Paragraph("Stock actuel", cell_style_center)
        ]
    ]
    
    # Trier les cahiers par CA généré
    cahiers_tries = sorted(
        [(data['titre'], data) for data in bilan.ventes_par_cahier.values()],
        key=lambda x: x[1]['ca_genere'],
        reverse=True
    )
    
    total_ca_cahiers = 0
    for titre, data in cahiers_tries:
        if data['quantite_vendue'] > 0:  
            cahiers_data.append([
                Paragraph(data['titre'], cell_style), 
                Paragraph(str(data['quantite_vendue']), cell_style_center),
                Paragraph(f"{data['ca_genere']:.0f}", cell_style_center),
                Paragraph(f"{data['prix_unitaire']} F", cell_style_center),
                Paragraph(str(data['stock_actuel']), cell_style_center)
            ])
            total_ca_cahiers += data['ca_genere']
    
    # Ligne de total
    cahiers_data.append([
        Paragraph("<b>TOTAL</b>", cell_style_center),
        Paragraph(f"<b>{sum(data['quantite_vendue'] for _, data in cahiers_tries if data['quantite_vendue'] > 0)}</b>", cell_style_center),
        Paragraph(f"<b>{total_ca_cahiers:.0f}</b>", cell_style_center),
        Paragraph("<b>-</b>", cell_style_center),
        Paragraph("<b>-</b>", cell_style_center)
    ])
    
    # Ajuster les largeurs de colonnes pour une meilleure répartition
    cahiers_table = Table(cahiers_data, colWidths=[5*cm, 2.5*cm, 3*cm, 2.5*cm, 3*cm])
    cahiers_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.wheat),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, -2), 'LEFT'),  
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.beige, colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(cahiers_table)
    
    # Générer les bilans mensuels pour le graphique
    bilans_mensuels = BilanMensuel.generer_tous_bilans_mensuels(annee)
    story.append(Spacer(1, 0.5 * cm))
    
    # Évolution mensuelle
    story.append(Paragraph("<b>ÉVOLUTION MENSUELLE</b>", styles['Heading2']))
    story.append(Spacer(1, 0.3 * cm))
    
    # En-têtes avec retour à la ligne
    evolution_data = [
        [
            Paragraph("Mois", cell_style_center),
            Paragraph("Nb Ventes", cell_style_center),
            Paragraph("Montant Ventes (F)", cell_style_center),
            Paragraph("Montant Payé (F)", cell_style_center),
            Paragraph("Taux recouvrement", cell_style_center)
        ]
    ]
    
    for bilan_mensuel in bilans_mensuels:
        taux_recouvrement = (float(bilan_mensuel.montant_paye) / float(bilan_mensuel.montant_ventes) * 100) if bilan_mensuel.montant_ventes > 0 else 0
        evolution_data.append([
            Paragraph(f"{bilan_mensuel.nom_mois} {bilan_mensuel.annee}", cell_style_center),
            Paragraph(str(bilan_mensuel.nombre_ventes), cell_style_center),
            Paragraph(f"{bilan_mensuel.montant_ventes:.0f}", cell_style_center),
            Paragraph(f"{bilan_mensuel.montant_paye:.0f}", cell_style_center),
            Paragraph(f"{taux_recouvrement:.1f}%", cell_style_center)
        ])  
    
    evolution_table = Table(evolution_data, colWidths=[3.5*cm, 2.5*cm, 4*cm, 3*cm, 3*cm])
    evolution_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.greenyellow),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.lightgreen, colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(evolution_table)
    
    # Construire le PDF
    doc.build(story)
    buffer.seek(0)
    
    # Retourner le PDF
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rapport_annuel_{annee.annee_debut}_{annee.annee_fin}.pdf"'
    return response

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



def modifier_dette_vente(request, vente_id):
    vente = get_object_or_404(Vente, id=vente_id)

    # Calculer la dette en excluant cette vente
    ventes_impayees = Vente.objects.filter(
        ecole=vente.ecole
    ).exclude(id=vente.id)
    
    dette_totale = Decimal('0')
    
    for v in ventes_impayees:
        montant_restant_v = v.montant_restant()
        if montant_restant_v > 0:
            dette_totale += montant_restant_v
    
    # Mise à jour de la dette
    vente.dette_precedente = dette_totale
    vente.description_dette = "Dette de l'année passé"
    vente.modified_at = timezone.now()
    vente.derniere_modification_type = 'modification_dette'
    vente.save()

    # Régénération de la facture PDF
    try:
        final_buffer = generer_facture_pdf(vente)
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"facture_{vente.id}_{timestamp}.pdf"

        if vente.facture_pdf:
            vente.facture_pdf.delete(save=False)

        vente.facture_pdf.save(filename, ContentFile(final_buffer.read()), save=True)
        messages.success(request, f"Dette recalculée : {dette_totale} F. Facture mise à jour.")
    except Exception as pdf_error:
        print(f"Erreur PDF lors de la modification de la dette : {pdf_error}")
        messages.warning(request, "Dette recalculée mais erreur lors de la mise à jour de la facture PDF.")

    return redirect('ventes')  


def generer_facture_pdf(vente):
    styles_paragraph = getSampleStyleSheet()
    style_cellule = styles_paragraph['BodyText']
    style_cellule.wordWrap = 'CJK'
    style_cellule.leading = 11
    style_cellule.fontSize = 9

    # S'assurer que nous avons les dernières données
    vente.refresh_from_db()
    
    # Séparer les lignes originales et les ajouts récents
    lignes_originales = vente.get_lignes_originales()
    lignes_ajoutees = vente.get_lignes_ajoutees_recemment()
    
    if not lignes_originales and not lignes_ajoutees:
        raise ValueError("Impossible de générer une facture sans articles")

    # CORRECTION: Calculer avec des Decimal uniquement
    montant_total_articles = sum(Decimal(str(ligne.montant)) for ligne in vente.lignes.all())
    dette_precedente = Decimal(str(vente.dette_precedente)) if vente.dette_precedente else Decimal('0')
    montant_total = montant_total_articles + dette_precedente

    # Création du PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=6*cm, bottomMargin=4*cm)
    story = []
    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]
    style_bold = styles["Heading4"]
    style_important = styles["Heading3"]

    story.append(Spacer(1, 0.5 * cm))

    # Style pour le nom de l'école
    style_ecole = ParagraphStyle(
        'EcoleStyle',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica',
        wordWrap='CJK',
        alignment=1,
        leading=10,
        spaceBefore=0,
        spaceAfter=0
    )

    est_modifiee = vente.modified_at is not None
    a_des_ajouts = len(lignes_ajoutees) > 0
    
    # Déterminer le type de modification
    type_modification = getattr(vente, 'derniere_modification_type', None)
    
    numero_facture = f"F-{datetime.now().year}-{str(vente.id)[:8]}"
    date_modif_str = vente.modified_at.strftime('%d-%m-%Y %H:%M') if vente.modified_at else "—"

    info_data = [
        ["ÉCOLE", "FACTURE", "DATE ÉDITION", "DATE MODIFICATION", "LIMITE PAIEMENT"],
        [Paragraph(vente.ecole.nom, style_ecole), 
        Paragraph(numero_facture), 
        datetime.now().strftime('%d-%m-%Y %H:%M'),
        date_modif_str,
        vente.date_paiement.strftime('%d-%m-%Y') if vente.date_paiement else "—"]
    ]

    info_table = Table(info_data, colWidths=[2.5*cm, 3.5*cm, 3*cm, 4*cm, 3*cm])
    info_table_style = TableStyle([
        ('GRID', (0,0), (-1,-1), 1.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,1), 8),
        ('ALIGN', (0,1), (-1,1), 'CENTER'),
        ('VALIGN', (0,1), (-1,1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ])
    
    if est_modifiee:
        info_table_style.add('BACKGROUND', (1,1), (1,1), colors.lightyellow)

    info_table.setStyle(info_table_style)   
    story.append(info_table)
    story.append(Spacer(0.1, 0.1 * cm))

    story.append(Paragraph("<b>ARTICLES COMMANDÉS</b>", style_bold))
    story.append(Spacer(0.1, 0.1*cm))
    
    lignes_facture_principal = [["Cahier", "Quantité", "Prix Unitaire", "Total"]]
    montant_original = Decimal('0')  # CORRECTION: Utiliser Decimal

    for ligne in lignes_originales:
        lignes_facture_principal.append([
            Paragraph(ligne.cahier.titre, style_cellule),
            str(ligne.quantite),
            f"{ligne.cahier.prix:.2f} F",
            f"{ligne.montant:.2f} F"
        ])
        montant_original += Decimal(str(ligne.montant))  # CORRECTION: Conversion en Decimal

    table_principal = Table(lignes_facture_principal, colWidths=[8*cm, 2.5*cm, 3*cm, 3*cm])
    table_style_principal = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.blue),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 3),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 10),
        ('TOPPADDING', (0,1), (-1,-1), 3),
        ('BOTTOMPADDING', (0,1), (-1,-1), 3),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ])
    
    for i in range(1, len(lignes_facture_principal), 2):
        if i < len(lignes_facture_principal):
            table_style_principal.add('BACKGROUND', (0,i), (-1,i), colors.lightgrey)
        
    table_principal.setStyle(table_style_principal)
    story.append(table_principal)
    
    # Sous-total des articles originaux
    story.append(Spacer(0.1, 0.2*cm))
    story.append(Paragraph(f"<b>Sous-total articles commandés : {montant_original:.2f} F</b>", style_normal))

    # Section des articles ajoutés
    if a_des_ajouts and lignes_ajoutees:
        story.append(Spacer(0.2, 0.3*cm))
        story.append(Paragraph(f"<b>ARTICLES AJOUTÉS LE {date_modif_str}</b>", style_bold))
        story.append(Spacer(0.1, 0.1*cm))
        
        lignes_facture_ajouts = [["Cahier", "Quantité", "Prix Unitaire", "Total"]]
        montant_ajouts = Decimal('0')  # CORRECTION: Utiliser Decimal
        
        for ligne in lignes_ajoutees:
            lignes_facture_ajouts.append([
                Paragraph(ligne.cahier.titre, style_cellule),
                str(ligne.quantite),
                f"{ligne.cahier.prix:.2f} F",
                f"{ligne.montant:.2f} F"
            ])
            montant_ajouts += Decimal(str(ligne.montant))  # CORRECTION: Conversion en Decimal

        table_ajouts = Table(lignes_facture_ajouts, colWidths=[8*cm, 2.5*cm, 3*cm, 3*cm])
        table_style_ajouts = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.orange),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('TOPPADDING', (0,0), (-1,0), 3),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 10),
            ('TOPPADDING', (0,1), (-1,-1), 3),
            ('BOTTOMPADDING', (0,1), (-1,-1), 3),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ])
        
        for i in range(1, len(lignes_facture_ajouts), 2):
            if i < len(lignes_facture_ajouts):
                table_style_ajouts.add('BACKGROUND', (0,i), (-1,i), colors.lightyellow)
            
        table_ajouts.setStyle(table_style_ajouts)
        story.append(table_ajouts)
        
        # Sous-total des ajouts
        story.append(Spacer(0.1, 0.2*cm))
        story.append(Paragraph(f"<b>Sous-total articles ajoutés : {montant_ajouts:.2f} F</b>", style_normal))

    story.append(Spacer(1, 0.3*cm))

    # Récapitulatif financier
    paiements_vente = vente.paiements.all().order_by('date_paiement')
    montant_paye = sum(Decimal(str(p.montant)) for p in paiements_vente)  # CORRECTION: Conversion en Decimal
    montant_restant = montant_total - montant_paye

    # Préparation des données du récapitulatif
    recap_data = []
    
    # Ligne articles
    recap_data.append([
        "Montant articles :",
        f"{montant_total_articles:.2f} F"
    ])
    
    # Ligne dette précédente (si elle existe)
    if dette_precedente > 0:  
        dette_description = vente.description_dette or "Dette année précédente"
        recap_data.append([
            f"{dette_description} :",
            f"{dette_precedente:.2f} F"  
        ])
    
    # Ligne total
    recap_data.append([
        "MONTANT TOTAL :",
        f"{montant_total:.2f} F"
    ])
    
    # Ligne montant payé
    recap_data.append([
        "Montant payé :",
        f"{montant_paye:.2f} F" if montant_paye > 0 else "Aucun paiement"
    ])
    
    # Ligne montant restant
    recap_data.append([
        "MONTANT RESTANT :",
        f"{montant_restant:.2f} F" if montant_restant > 0 else "ENTIÈREMENT RÉGLÉE"
    ])

    recap_table = Table(recap_data, colWidths=[10*cm, 6.5*cm])
    recap_table_style = TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),     
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),    
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ])
    
    # Mise en forme spéciale pour certaines lignes
    if dette_precedente > 0:  # CORRECTION: Utiliser dette_precedente
        # Ligne dette en orange
        recap_table_style.add('BACKGROUND', (0,1), (-1,1), colors.lightyellow)
        # Ligne total en gris
        recap_table_style.add('BACKGROUND', (0,2), (-1,2), colors.lightgrey)
        recap_table_style.add('FONTNAME', (0,2), (-1,2), 'Helvetica-Bold')
        # Ligne restant
        ligne_restant = 4
    else:
        # Ligne total en gris
        recap_table_style.add('BACKGROUND', (0,1), (-1,1), colors.lightgrey)
        recap_table_style.add('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold')
        # Ligne restant
        ligne_restant = 3
    
    # Colorer la ligne "montant restant" selon l'état
    if montant_restant <= 0:
        recap_table_style.add('BACKGROUND', (0,ligne_restant), (-1,ligne_restant), colors.lightgreen)
        recap_table_style.add('TEXTCOLOR', (0,ligne_restant), (-1,ligne_restant), colors.darkgreen)
        recap_table_style.add('FONTNAME', (0,ligne_restant), (-1,ligne_restant), 'Helvetica-Bold')
    else:
        recap_table_style.add('BACKGROUND', (0,ligne_restant), (-1,ligne_restant), colors.lightcoral)
        recap_table_style.add('TEXTCOLOR', (0,ligne_restant), (-1,ligne_restant), colors.darkred)
        recap_table_style.add('FONTNAME', (0,ligne_restant), (-1,ligne_restant), 'Helvetica-Bold')
        
        # Vérifier si en retard
        try:
            if vente.date_paiement and vente.date_paiement.date() < timezone.now().date():
                story.append(Spacer(0.1, 0.1*cm))
                story.append(Paragraph(
                    f"<b><font color='red'>PAIEMENT EN RETARD</font></b>", 
                    style_important
                ))
        except AttributeError:
            # Si date_paiement est None
            pass
    
    recap_table.setStyle(recap_table_style)
    story.append(recap_table)

    # Construire le PDF
    doc.build(story)
    buffer.seek(0)

    # Fusion avec le papier en-tête
    papier_en_tete_path = os.path.join(settings.BASE_DIR, 'static/admin/papier1.pdf')
    final_buffer = BytesIO()

    if os.path.exists(papier_en_tete_path):
        try:
            modele_pdf = PdfReader(papier_en_tete_path)
            tableau_pdf = PdfReader(buffer)
            writer = PdfWriter()

            for page_tableau in tableau_pdf.pages:
                fond = modele_pdf.pages[0]
                page_fusionnee = PageObject.create_blank_page(
                    width=fond.mediabox.width,
                    height=fond.mediabox.height
                )
                page_fusionnee.merge_page(fond)
                page_fusionnee.merge_page(page_tableau)
                writer.add_page(page_fusionnee)

            writer.write(final_buffer)
            final_buffer.seek(0)

        except Exception as pdf_error:
            print(f"Erreur lors de la fusion PDF : {pdf_error}")
            final_buffer = buffer
    else:
        print(f"Fichier papier en-tête introuvable : {papier_en_tete_path}")
        final_buffer = buffer

    return final_buffer

def ajouter_vente(request): 
    if request.method == "POST":
        try:
            ecole = Ecoles.objects.get(id=request.POST['ecole'])
            cahier_ids = request.POST.getlist('cahiers[]')
            quantites = request.POST.getlist('quantites[]')
            montant_verse_str = request.POST.get('montant_verse', '0')
            
            # Gestion de la dette précédente - CALCUL AUTOMATIQUE
            dette_precedente = calculer_dette_ecole(ecole, vente_exclue=None)

            if len(cahier_ids) != len(quantites):
                messages.error(request, "Erreur : correspondance cahiers/quantités incorrecte.")
                return redirect('ventes')

            # Année scolaire courante
            annee_courante = AnneeScolaire.get_annee_courante()
            if not annee_courante:
                today = timezone.now().date()
                annee_courante_num = today.year if today.month >= 7 else today.year - 1
                annee_courante = AnneeScolaire.creer_annee_scolaire(annee_courante_num)
                annee_courante.activer()

            now = timezone.now()
            date_paiement = now + timedelta(days=30)

            # Création de la vente avec dette calculée automatiquement
            vente = Vente.objects.create(
                ecole=ecole,
                date_paiement=date_paiement,
                annee_scolaire=annee_courante,
                dette_precedente=dette_precedente,
                description_dette="Dette de l'année passé" if dette_precedente > 0 else ""
            )

            # Vérification stock et création des lignes
            for cahier_id, qte in zip(cahier_ids, quantites):
                cahier = Cahiers.objects.get(id=cahier_id)
                qte = int(qte)
                if qte <= 0:
                    messages.error(request, f"Quantité invalide pour {cahier.titre}")
                    vente.delete()
                    return redirect('ventes')
                if cahier.quantite_stock < qte:
                    messages.error(request, f"Stock insuffisant pour {cahier.titre}")
                    vente.delete()
                    return redirect('ventes')

            # Créer les lignes et décrémenter le stock
            for cahier_id, qte in zip(cahier_ids, quantites):
                cahier = Cahiers.objects.get(id=cahier_id)
                qte = int(qte)
                ligne = LigneVente.objects.create(vente=vente, cahier=cahier, quantite=qte)
                cahier.quantite_stock -= qte
                cahier.save()

            # Calcul du montant total
            montant_total = vente.montant_total

            # Gestion du paiement initial
            if montant_verse_str and montant_verse_str.strip():
                try:
                    montant_verse = Decimal(montant_verse_str.replace(',', '.'))
                    if montant_verse > 0:
                        if montant_verse > montant_total:
                            messages.warning(request, "Le montant versé dépasse le total. Il a été ajusté.")
                            montant_verse = montant_total
                        
                        Paiement.objects.create(
                            vente=vente,
                            montant=montant_verse,
                            numero_tranche=1,
                            date_paiement=timezone.now().date()
                        )
                except (ValueError, InvalidOperation) as e:
                    messages.warning(request, f"Montant versé invalide : {montant_verse_str}. Ignoré.")

            # Génération PDF
            try:
                final_buffer = generer_facture_pdf(vente)
                filename = f"facture_{vente.id}.pdf"
                vente.facture_pdf.save(filename, ContentFile(final_buffer.read()), save=True)
            except Exception as pdf_error:
                print(f"Erreur lors de la génération du PDF : {pdf_error}")

            message_dette = f" (incluant dette de {dette_precedente} F)" if dette_precedente > 0 else ""
            messages.success(request, f"Vente enregistrée avec succès (Montant total: {montant_total} F{message_dette}).")
            
        except Exception as e:
            messages.error(request, f"Erreur lors de l'enregistrement : {str(e)}")
            if 'vente' in locals():
                vente.delete()
        
        return redirect('ventes')


def ajouter_paiement(request, vente_id):
    vente = get_object_or_404(Vente, id=vente_id)
    
    # Vérifications
    if vente.est_reglee():
        messages.error(request, "Cette vente est déjà entièrement réglée.")
        return redirect('ventes')
    
    if not vente.peut_ajouter_tranche():
        messages.error(request, "Le nombre maximum de tranches (3) est atteint.")
        return redirect('ventes')
    
    if vente.est_en_retard():
        messages.warning(request, f"Attention : La date limite de paiement est dépassée !")

    if request.method == 'POST':
        try:
            montant = Decimal(request.POST.get('montant').replace(',', '.'))
            
            montant_restant = vente.montant_restant()
            
            if montant <= 0:
                messages.error(request, "Le montant doit être supérieur à 0.")
            elif montant > montant_restant:
                messages.error(request, f"Le montant ({montant} F) dépasse le montant restant ({montant_restant} F).")
            else:
                numero_tranche = vente.paiements.count() + 1
                
                Paiement.objects.create(
                    vente=vente, 
                    montant=montant,
                    numero_tranche=numero_tranche
                )
                
                # Régénération PDF
                try:
                    final_buffer = generer_facture_pdf(vente)
                    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"facture_{vente.id}_{timestamp}.pdf"
                    
                    if vente.facture_pdf:
                        vente.facture_pdf.delete(save=False)
                    
                    vente.facture_pdf.save(filename, ContentFile(final_buffer.read()), save=True)
                    
                except Exception as pdf_error:
                    print(f"Erreur lors de la régénération du PDF : {pdf_error}")
                
                # Message de confirmation
                nouveau_montant_restant = vente.montant_restant()
                
                if vente.est_reglee():
                    messages.success(request, f"Paiement de {montant} F enregistré. La vente est maintenant entièrement réglée !")
                else:
                    messages.success(request, f"Paiement de {montant} F enregistré. Montant restant : {nouveau_montant_restant} F.")
                    
        except Exception as e:
            messages.error(request, f"Erreur lors de l'enregistrement du paiement : {str(e)}")
    
    return redirect('ventes')


def calculer_dette_ecole(ecole, vente_exclue=None):
    """Calcule la dette totale d'une école en excluant optionnellement une vente"""
    ventes_query = Vente.objects.filter(ecole=ecole)
    
    if vente_exclue:
        ventes_query = ventes_query.exclude(id=vente_exclue.id)
    
    dette_totale = Decimal('0')
    for vente in ventes_query:
        montant_restant = vente.montant_restant()
        if montant_restant > 0:
            dette_totale += montant_restant
    
    return dette_totale


def supprimer_vente(request, id):
    Vente.objects.filter(id=id).delete()
    return redirect('ventes')


def detail_vente(request, vente_id):
    vente = get_object_or_404(Vente, pk=vente_id)
    paiements = vente.paiements.all()
    lignes = vente.lignes.all()
    montant_restant = vente.montant_restant()
    montant_paye = vente.montant_total - montant_restant

    if vente.montant_total > 0:
        pourcentage_paye = round((montant_paye / vente.montant_total) * 100)
    else:
        pourcentage_paye = 0


    return render(request, 'detailsvente.html', {
        'vente': vente,
        'paiements': paiements,
        'lignes': lignes,
        'montant_restant': montant_restant,
        'montant_paye': montant_paye,
        'pourcentage_paye': pourcentage_paye,
    })


def ventes_par_ecole(request):
    ecoles = Ecoles.objects.all()
    return render(request, 'historique.html', {'ecoles': ecoles})


def ventes_ajax(request, ecole_id):
    ventes = Vente.objects.filter(ecole_id=ecole_id).prefetch_related('paiements', 'lignes')

    data = []
    for vente in ventes:
        paiements = vente.paiements.all()
        data.append({
            'id': str(vente.id),
            'date': vente.date_paiement.strftime('%d/%m/%Y') if vente.date_paiement else 'N/A',
            'montant_total': float(vente.montant_total),
            'montant_paye': float(vente.montant_paye),
            'montant_restant': float(vente.montant_restant()),
            'statut': vente.statut_paiement(),
            'paiement_dates': [p.date_paiement.strftime('%d/%m/%Y') for p in paiements],
        })
    return JsonResponse({'ventes': data})


def ajouter_stock(request):
    if request.method == 'POST':
        cahier_id = request.POST.get('cahier_id')
        quantite = int(request.POST.get('quantite', 0))

        cahier = get_object_or_404(Cahiers, id=cahier_id)
        cahier.quantite_stock += quantite
        cahier.save()

        messages.success(request, f'Stock ajouté pour le cahier "{cahier.titre}".')
    return redirect('cahiers')


def generer_pdf_ventes_ecole(request, ecole_id):
    ecole = get_object_or_404(Ecoles, id=ecole_id)
    ventes = Vente.objects.filter(ecole=ecole).prefetch_related('paiements', 'lignes')

    if not ventes.exists():
        return HttpResponse("Aucune vente trouvée pour cette école.", status=404)

    donnees_tableau = [["Limite paiement", "Montant Total", "Montant Payé", "Montant Restant", "Statut", "Dates Paiements"]]
    montant_total_general = 0
    montant_paye_general = 0

    def formater_dates_avec_retour_ligne(dates_str, max_chars_par_ligne=25):
        """Formate les dates pour qu'elles s'affichent sur plusieurs lignes si nécessaire"""
        if not dates_str or dates_str == "Aucun paiement":
            return dates_str
        
        # Divise les dates par la virgule et l'espace
        dates_list = dates_str.split(", ")
        lignes = []
        ligne_courante = ""
        
        for date in dates_list:
            # Si ajouter cette date dépasse la limite, commencer une nouvelle ligne
            if ligne_courante and len(ligne_courante + ", " + date) > max_chars_par_ligne:
                lignes.append(ligne_courante)
                ligne_courante = date
            else:
                if ligne_courante:
                    ligne_courante += ", " + date
                else:
                    ligne_courante = date
        
        # Ajouter la dernière ligne
        if ligne_courante:
            lignes.append(ligne_courante)
        
        return "\n".join(lignes)

    for vente in ventes:
        paiements = vente.paiements.all()
        dates_paiements = ", ".join([p.date_paiement.strftime('%d/%m/%Y') for p in paiements]) or "Aucun paiement"
        dates_formatees = formater_dates_avec_retour_ligne(dates_paiements)
        
        montant_total_general += vente.montant_total
        montant_paye_general += vente.montant_paye

        donnees_tableau.append([
            vente.date_paiement.strftime('%d/%m/%Y') if vente.date_paiement else "N/A",
            f"{vente.montant_total:.0f} F",
            f"{vente.montant_paye:.0f} F",
            f"{vente.montant_restant():.0f} F",
            vente.statut_paiement(),
            dates_formatees
        ])

    # Ligne de total
    donnees_tableau.append([
        "TOTAL",
        f"{montant_total_general:.0f} F",
        f"{montant_paye_general:.0f} F",
        f"{montant_total_general - montant_paye_general:.0f} F",
        "", ""
    ])

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y_start = 22.5 * cm  # descend sous le logo

    p.setFont("Helvetica-Bold", 14)
    p.drawString(2 * cm, y_start, "RÉCAPITULATIF DES VENTES")

    p.setFont("Helvetica", 11)
    p.drawString(2 * cm, y_start - 0.8 * cm, f"École: {ecole.nom}")
    p.drawString(2 * cm, y_start - 1.4 * cm, f"Adresse: {ecole.adresse}")
    p.drawString(2 * cm, y_start - 2 * cm, f"Date d'édition: {timezone.now().strftime('%d/%m/%Y à %H:%M')}")

    # Tableau des ventes avec hauteur de ligne adaptative
    table = Table(donnees_tableau, colWidths=[3*cm]*4 + [2.5*cm, 4*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),  
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('WORDWRAP', (0, 0), (-1, -1), True),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.beige, colors.white] * len(donnees_tableau)),
    ]))

    table.wrapOn(p, width, height)
    table.drawOn(p, 1.2 * cm, 12.5 * cm) 

    # Statistiques
    y_stat = 11 * cm
    p.setFont("Helvetica-Bold", 11)
    p.drawString(2 * cm, y_stat, "STATISTIQUES:")

    p.setFont("Helvetica", 10)
    p.drawString(2 * cm, y_stat - 0.6 * cm, f"• Nombre total de ventes: {ventes.count()}")
    p.drawString(2 * cm, y_stat - 1.2 * cm, f"• Montant total des ventes: {montant_total_general:.0f} F")
    p.drawString(2 * cm, y_stat - 1.8 * cm, f"• Montant total payé: {montant_paye_general:.0f} F")
    p.drawString(2 * cm, y_stat - 2.4 * cm, f"• Montant restant: {montant_total_general - montant_paye_general:.0f} F")
    if montant_total_general > 0:
        p.drawString(2 * cm, y_stat - 3 * cm, f"• Pourcentage payé: {(montant_paye_general / montant_total_general) * 100:.1f}%")

    ventes_en_retard = ventes.filter(date_paiement__lt=timezone.now().date()).exclude(id__in=[v.id for v in ventes if v.est_reglee()])
    if ventes_en_retard.exists():
        p.setFont("Helvetica-Bold", 10)
        p.setFillColor(colors.red)
        p.drawString(2 * cm, y_stat - 4 * cm, f"⚠ {ventes_en_retard.count()} vente(s) en retard de paiement")
        p.setFillColor(colors.black)

    p.save()
    buffer.seek(0)

    # 3. Superposition avec le modèle papier en-tête
    papier_path = os.path.join(settings.BASE_DIR, 'static/admin/papier1.pdf')
    template_pdf = PdfReader(papier_path)
    content_pdf = PdfReader(buffer)

    writer = PdfWriter()
    page_template = template_pdf.pages[0]
    page_content = content_pdf.pages[0]
    page_template.merge_page(page_content)
    writer.add_page(page_template)

    final_buffer = BytesIO()
    writer.write(final_buffer)
    final_buffer.seek(0)

    # 4. Retour du PDF
    response = HttpResponse(final_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="ventes_{ecole.nom.replace(" ", "_")}_{timezone.now().strftime("%Y%m%d")}.pdf"'
    return response



def modifier_vente(request, vente_id):
    vente = get_object_or_404(Vente, id=vente_id)
    
    if vente.paiements.exists():
        messages.warning(request, "Cette vente a déjà des paiements enregistrés. Soyez prudent lors de la modification.")
    
    if request.method == 'POST':
        try:
            cahier_ids = request.POST.getlist('cahiers[]')
            quantites = request.POST.getlist('quantites[]')
            action = request.POST.get('action', 'remplacer')
            
            if len(cahier_ids) != len(quantites):
                messages.error(request, "Erreur : correspondance cahiers/quantités incorrecte.")
                return redirect('detail_vente', vente_id=vente.id)
            
            # Valider les données
            nouveaux_articles = []
            for cahier_id, qte_str in zip(cahier_ids, quantites):
                if not cahier_id or not qte_str:
                    continue
                    
                try:
                    cahier = Cahiers.objects.get(id=cahier_id)
                    qte = int(qte_str)
                    if qte <= 0:
                        messages.error(request, f"Quantité invalide pour {cahier.titre}")
                        return redirect('detail_vente', vente_id=vente.id)
                    nouveaux_articles.append({'cahier': cahier, 'quantite': qte})
                except (Cahiers.DoesNotExist, ValueError):
                    messages.error(request, "Erreur dans la sélection des cahiers ou quantités.")
                    return redirect('detail_vente', vente_id=vente.id)
            
            if not nouveaux_articles:
                messages.error(request, "Aucun article valide sélectionné.")
                return redirect('detail_vente', vente_id=vente.id)
            
            # Sauvegarder l'état actuel pour rollback si nécessaire
            anciennes_lignes = list(vente.lignes.all())
            ancien_stock = {ligne.cahier.id: ligne.cahier.quantite_stock for ligne in anciennes_lignes}
            
            if action == 'remplacer':
                # Remettre le stock des anciennes lignes
                for ligne in anciennes_lignes:
                    ligne.cahier.quantite_stock += ligne.quantite
                    ligne.cahier.save()
                
                # Supprimer toutes les lignes actuelles
                vente.lignes.all().delete()
                
                # Vérifier le stock et créer les nouvelles lignes
                for article in nouveaux_articles:
                    cahier = article['cahier']
                    quantite = article['quantite']
                    
                    if cahier.quantite_stock < quantite:
                        _rollback_modification(vente, anciennes_lignes, ancien_stock)
                        messages.error(request, f"Stock insuffisant pour {cahier.titre} (disponible: {cahier.quantite_stock}, demandé: {quantite})")
                        return redirect('detail_vente', vente_id=vente.id)
                    
                    LigneVente.objects.create(vente=vente, cahier=cahier, quantite=quantite)
                    cahier.quantite_stock -= quantite
                    cahier.save()
                
                vente.modified_at = timezone.now()
                vente.derniere_modification_type = 'remplacement'
                vente.articles_ajoutes_session = None  # Reset des ajouts
                vente.save()
                
                messages.success(request, "Vente modifiée avec succès (remplacement complet).")
                
            elif action == 'ajouter':
                # Vérifier le stock avant d'ajouter
                for article in nouveaux_articles:
                    cahier = article['cahier']
                    quantite = article['quantite']
                    
                    if cahier.quantite_stock < quantite:
                        messages.error(request, f"Stock insuffisant pour {cahier.titre} (disponible: {cahier.quantite_stock}, demandé: {quantite})")
                        return redirect('detail_vente', vente_id=vente.id)
                
                # Ajouter les articles
                for article in nouveaux_articles:
                    cahier = article['cahier']
                    quantite = article['quantite']
                    
                    ligne_existante = vente.lignes.filter(cahier=cahier).first()
                    if ligne_existante:
                        # Augmenter la quantité si l'article existe déjà
                        ligne_existante.quantite += quantite
                        ligne_existante.save()  # Le save() recalculera le montant
                    else:
                        # Créer une nouvelle ligne
                        LigneVente.objects.create(vente=vente, cahier=cahier, quantite=quantite)
                    
                    cahier.quantite_stock -= quantite
                    cahier.save()
                
                # Enregistrer l'ajout pour la facture
                vente.enregistrer_ajout_articles(nouveaux_articles)
                vente.modified_at = timezone.now()
                vente.derniere_modification_type = 'ajout'
                vente.save()
                
                messages.success(request, "Cahiers ajoutés à la vente avec succès.")
            
            # Régénération de la facture PDF
            try:
                vente.refresh_from_db()
                
                if not vente.lignes.exists():
                    raise Exception("Aucune ligne de vente trouvée après modification")
                
                final_buffer = generer_facture_pdf(vente)
                
                timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
                filename = f"facture_{vente.id}_{timestamp}.pdf"
                
                # Supprimer l'ancien fichier PDF
                if vente.facture_pdf:
                    old_path = vente.facture_pdf.path
                    vente.facture_pdf.delete(save=False)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except OSError:
                            pass
                
                vente.facture_pdf.save(filename, ContentFile(final_buffer.read()), save=True)
                
                if vente.facture_pdf and os.path.exists(vente.facture_pdf.path):
                    messages.success(request, "Facture PDF mise à jour avec succès.")
                else:
                    messages.warning(request, "Vente modifiée mais problème lors de la sauvegarde de la facture PDF.")
                
            except Exception as pdf_error:
                print(f"Erreur lors de la génération du PDF : {pdf_error}")
                import traceback
                traceback.print_exc()
                messages.warning(request, f"Vente modifiée mais erreur lors de la génération de la facture PDF: {str(pdf_error)}")
            
            return redirect('ventes')
            
        except Exception as e:
            print(f"Erreur lors de la modification : {e}")
            import traceback
            traceback.print_exc()
            messages.error(request, f"Erreur lors de la modification : {str(e)}")
            return redirect('ventes')
    
    context = {
        'vente': vente,
        'cahiers': Cahiers.objects.all(),
        'lignes_actuelles': vente.lignes.select_related('cahier').all()
    }
    return render(request, 'modifier_vente.html', context)


def modifier_quantite_ligne(request, vente_id, ligne_id):
    if request.method == 'POST':
        ligne = get_object_or_404(LigneVente, id=ligne_id, vente_id=vente_id)
        
        try:
            nouvelle_quantite = int(request.POST.get('nouvelle_quantite', 0))
            
            if nouvelle_quantite <= 0:
                messages.error(request, "La quantité doit être supérieure à 0.")
                return redirect('detail_vente', vente_id=vente_id)
            
            ancienne_quantite = ligne.quantite
            difference = nouvelle_quantite - ancienne_quantite
            
            # Si on augmente la quantité, vérifier le stock
            if difference > 0:
                if ligne.cahier.quantite_stock < difference:
                    messages.error(request, f"Stock insuffisant pour {ligne.cahier.titre}. Stock disponible: {ligne.cahier.quantite_stock}")
                    return redirect('detail_vente', vente_id=vente_id)
                
                # Décrémenter le stock
                ligne.cahier.quantite_stock -= difference
            else:
                # Si on diminue la quantité, remettre le stock
                ligne.cahier.quantite_stock += abs(difference)
            
            # Sauvegarder les changements
            ligne.quantite = nouvelle_quantite
            ligne.save()  # Le save() recalculera automatiquement le montant
            ligne.cahier.save()
            
            # Marquer la vente comme modifiée
            vente = ligne.vente
            vente.modified_at = timezone.now()
            vente.derniere_modification_type = 'modification_quantite'
            vente.save()
            
            # Régénérer la facture PDF avec timestamp unique
            try:
                vente.refresh_from_db()
                
                final_buffer = generer_facture_pdf(vente)
                timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
                filename = f"facture_{vente.id}_{timestamp}.pdf"
                
                # Supprimer l'ancien fichier
                if vente.facture_pdf:
                    vente.facture_pdf.delete(save=False)
                
                # Sauvegarder le nouveau fichier
                vente.facture_pdf.save(filename, ContentFile(final_buffer.read()), save=True)
                
                messages.success(request, f"Quantité modifiée pour {ligne.cahier.titre}: {ancienne_quantite} → {nouvelle_quantite}. Facture mise à jour.")
                
            except Exception as pdf_error:
                print(f"Erreur PDF lors de la modification : {pdf_error}")
                import traceback
                traceback.print_exc()
                messages.warning(request, f"Quantité modifiée pour {ligne.cahier.titre}: {ancienne_quantite} → {nouvelle_quantite}. Erreur lors de la mise à jour de la facture.")
            
        except (ValueError, TypeError):
            messages.error(request, "Quantité invalide.")
        except Exception as e:
            print(f"Erreur lors de la modification de quantité : {e}")
            messages.error(request, f"Erreur lors de la modification : {str(e)}")
    
    return redirect('detail_vente', vente_id=vente_id)


def supprimer_ligne_vente(request, vente_id, ligne_id):
    if request.method == 'POST':
        ligne = get_object_or_404(LigneVente, id=ligne_id, vente_id=vente_id)
        
        # Vérifier qu'il reste au moins une ligne
        if ligne.vente.lignes.count() <= 1:
            messages.error(request, "Impossible de supprimer la dernière ligne d'une vente.")
            return redirect('ventes')
        
        try:
            # Remettre le stock
            ligne.cahier.quantite_stock += ligne.quantite
            ligne.cahier.save()
            
            titre_cahier = ligne.cahier.titre
            vente = ligne.vente
            
            ligne.delete()
            
            vente.modified_at = timezone.now()
            vente.derniere_modification_type = 'suppression_ligne'
            vente.save()
            
            # Régénération de la facture PDF
            try:
                vente.refresh_from_db()
                
                final_buffer = generer_facture_pdf(vente)
                timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
                filename = f"facture_{vente.id}_{timestamp}.pdf"
                
                if vente.facture_pdf:
                    vente.facture_pdf.delete(save=False)
                
                vente.facture_pdf.save(filename, ContentFile(final_buffer.read()), save=True)
                messages.success(request, f"Article '{titre_cahier}' supprimé de la vente. Facture mise à jour.")
                
            except Exception as pdf_error:
                print(f"Erreur PDF lors de la suppression : {pdf_error}")
                messages.warning(request, f"Article '{titre_cahier}' supprimé de la vente. Erreur lors de la mise à jour de la facture.")
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression : {str(e)}")
    
    return redirect('ventes')


def _rollback_modification(vente, anciennes_lignes, ancien_stock):
    """Fonction utilitaire pour annuler une modification en cas d'erreur"""
    try:
        # Supprimer toutes les lignes actuelles
        vente.lignes.all().delete()
        
        # Recréer les anciennes lignes
        for ligne in anciennes_lignes:
            LigneVente.objects.create(
                vente=vente,
                cahier=ligne.cahier,
                quantite=ligne.quantite
                # Le montant sera recalculé automatiquement par le save()
            )
            # Restaurer l'ancien stock
            ligne.cahier.quantite_stock = ancien_stock[ligne.cahier.id]
            ligne.cahier.save()
    except Exception as rollback_error:
        print(f"Erreur lors du rollback : {rollback_error}")
        # En cas d'erreur de rollback, au moins logger l'erreur
        import traceback
        traceback.print_exc()