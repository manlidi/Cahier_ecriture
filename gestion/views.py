from django.shortcuts import *
from gestion.models import AnneeScolaire, BilanMensuel, BilanAnneeScolaire, Cahiers, Vente, LigneVente, Paiement
from .services import NotificationService
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.lib.units import cm
from io import BytesIO
from django.db.models import Sum, Count
import json
from django.utils import timezone
from datetime import timedelta
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.styles import ParagraphStyle
import calendar
from collections import defaultdict
from datetime import date
from django.db import models

def home(request):
    # Vérification automatique des notifications à chaque chargement de la page d'accueil
    notification_service = NotificationService()
    try:
        notification_service.verifier_notifications()
        notification_service.envoyer_notifications_en_attente()
    except Exception as e:
        # Log l'erreur mais ne pas interrompre le chargement de la page
        print(f"Erreur lors de la vérification automatique des notifications: {e}")
    
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
