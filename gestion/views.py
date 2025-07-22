from django.shortcuts import *
from .models import *
from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.lib.units import cm
from io import BytesIO
from django.db.models import Sum, Count, Q
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


def home(request):
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    last_week = today - timedelta(days=7)
    last_month = today - timedelta(days=30)
    
    # Revenus d'aujourd'hui
    revenus_aujourd_hui = Paiement.objects.filter(
        date_paiement=today
    ).aggregate(total=Sum('montant'))['total'] or 0
    
    # Revenus de la semaine dernière pour comparaison
    revenus_semaine_derniere = Paiement.objects.filter(
        date_paiement__range=[last_week, yesterday]
    ).aggregate(total=Sum('montant'))['total'] or 0
    
    # Calcul du pourcentage d'augmentation
    if revenus_semaine_derniere > 0:
        pourcentage_revenus = ((revenus_aujourd_hui - revenus_semaine_derniere) / revenus_semaine_derniere) * 100
    else:
        pourcentage_revenus = 100 if revenus_aujourd_hui > 0 else 0
    
    # Nombre d'écoles actives aujourd'hui
    ecoles_actives_aujourd_hui = Vente.objects.filter(
        created_at__date=today
    ).values('ecole').distinct().count()
    
    # Écoles actives le mois dernier
    ecoles_actives_mois_dernier = Vente.objects.filter(
        created_at__date__range=[last_month, yesterday]
    ).values('ecole').distinct().count()
    
    # Pourcentage d'écoles actives
    if ecoles_actives_mois_dernier > 0:
        pourcentage_ecoles = ((ecoles_actives_aujourd_hui - ecoles_actives_mois_dernier) / ecoles_actives_mois_dernier) * 100
    else:
        pourcentage_ecoles = 100 if ecoles_actives_aujourd_hui > 0 else 0
    
    # Nombre de ventes aujourd'hui
    ventes_aujourd_hui = Vente.objects.filter(created_at__date=today).count()
    ventes_hier = Vente.objects.filter(created_at__date=yesterday).count()
    
    if ventes_hier > 0:
        pourcentage_ventes = ((ventes_aujourd_hui - ventes_hier) / ventes_hier) * 100
    else:
        pourcentage_ventes = 100 if ventes_aujourd_hui > 0 else 0
    
    # Chiffre d'affaires total
    ca_total = Paiement.objects.aggregate(total=Sum('montant'))['total'] or 0
    ca_hier = Paiement.objects.filter(date_paiement=yesterday).aggregate(total=Sum('montant'))['total'] or 0
    
    if ca_hier > 0:
        pourcentage_ca = ((revenus_aujourd_hui - ca_hier) / ca_hier) * 100
    else:
        pourcentage_ca = 100 if revenus_aujourd_hui > 0 else 0
    
    # Données pour les graphiques
    ventes_par_jour = []
    for i in range(7):
        date = today - timedelta(days=6-i)
        count = Vente.objects.filter(created_at__date=date).count()
        ventes_par_jour.append({
            'date': date.strftime('%d/%m'),
            'count': count
        })
    
    # Revenus par jour (7 derniers jours)
    revenus_par_jour = []
    for i in range(7):
        date = today - timedelta(days=6-i)
        revenus = Paiement.objects.filter(date_paiement=date).aggregate(total=Sum('montant'))['total'] or 0
        revenus_par_jour.append({
            'date': date.strftime('%d/%m'),
            'revenus': float(revenus)
        })
    
    # Top 5 des écoles par chiffre d'affaires
    top_ecoles = Vente.objects.values(
        'ecole__nom'
    ).annotate(
        total_ca=Sum('paiements__montant'),
        nb_ventes=Count('id')
    ).order_by('-total_ca')[:5]
    
    # Ventes en retard
    ventes_en_retard = Vente.objects.filter(
        date_paiement__lt=today
    ).exclude(
        id__in=Vente.objects.filter(paiements__isnull=False).filter(
            paiements__montant__gte=models.F('lignes__montant')
        ).values('id')
    ).count()
    
    # Activités récentes (dernières ventes et paiements)
    activites_recentes = []
    
    # Derniers paiements
    derniers_paiements = Paiement.objects.select_related('vente__ecole').order_by('-date_paiement')[:3]
    for paiement in derniers_paiements:
        activites_recentes.append({
            'type': 'paiement',
            'description': f"{paiement.montant}F, Paiement reçu de {paiement.vente.ecole.nom}",
            'date': paiement.date_paiement,
            'icon': 'payments'
        })
    
    # Dernières ventes
    dernieres_ventes = Vente.objects.select_related('ecole').order_by('-created_at')[:3]
    for vente in dernieres_ventes:
        activites_recentes.append({
            'type': 'vente',
            'description': f"Nouvelle vente #{str(vente.id)[:8]}... à {vente.ecole.nom}",
            'date': vente.created_at.date(),
            'icon': 'shopping_cart'
        })
    
    # Trier les activités par date
    activites_recentes.sort(key=lambda x: x['date'], reverse=True)
    activites_recentes = activites_recentes[:3]  # Garder seulement les 6 plus récentes
    
    # Données sur les stocks
    stock_faible = Cahiers.objects.filter(quantite_stock__lt=10).count()
    total_cahiers = Cahiers.objects.count()
    
    context = {
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
    ventes_en_retard = Vente.objects.filter(
        date_paiement__lt=timezone.now()
    ).exclude(id__in=Vente.objects.filter(paiements__isnull=False).annotate(
        total_paye=models.Sum('paiements__montant')
    ).filter(total_paye__gte=models.F('lignes__montant')))

    if ventes_en_retard.exists():
        messages.warning(request, f"Attention : {ventes_en_retard.count()} vente(s) en retard de paiement !")

    ventes_liste = Vente.objects.prefetch_related('lignes__cahier', 'ecole', 'paiements').all()
    
    # Ajout de la pagination
    paginator = Paginator(ventes_liste, 5)  
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'cahiers': Cahiers.objects.all(),
        'ecoles': Ecoles.objects.all()
    }
    return render(request, 'ventes.html', context)


def generer_facture_pdf(vente):
    
    # Préparer le style pour les cellules
    styles_paragraph = getSampleStyleSheet()
    style_cellule = styles_paragraph['BodyText']
    style_cellule.wordWrap = 'CJK'
    style_cellule.leading = 11
    style_cellule.fontSize = 9

    # Préparer le tableau de la facture
    lignes_facture = [["Cahier", "Quantité", "Prix Unitaire", "Total"]]
    montant_total = 0

    for ligne in vente.lignes.all():
        montant_total += ligne.montant
        lignes_facture.append([
            Paragraph(ligne.cahier.titre, style_cellule),
            str(ligne.quantite),
            f"{ligne.cahier.prix:.2f} F",
            f"{ligne.montant:.2f} F"
        ])

    # Calculs des paiements - Gestion des méthodes et propriétés
    try:
        # Si montant_paye est une méthode
        montant_paye = vente.montant_paye() if callable(getattr(vente, 'montant_paye', None)) else getattr(vente, 'montant_paye', 0)
        montant_restant = vente.montant_restant() if callable(getattr(vente, 'montant_restant', None)) else getattr(vente, 'montant_restant', montant_total)
    except:
        # Fallback : calcul manuel
        montant_paye = sum(p.montant for p in vente.paiements.all()) if hasattr(vente, 'paiements') else 0
        montant_restant = montant_total - montant_paye

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

    info_data = [
        ["ÉCOLE", "FACTURE", "DATE", "DATE LIMITE PAIEMENT"],
        [vente.ecole.nom, f"F-{datetime.now().year}-{str(vente.id)[:8]}", 
        datetime.now().strftime('%d-%m-%Y'), 
        vente.date_paiement.strftime('%d-%m-%Y')]
    ]

    
    info_table = Table(info_data, colWidths=[4*cm, 3*cm, 4*cm, 5*cm])
    info_table_style = TableStyle([
        ('GRID', (0,0), (-1,-1), 1.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),

        # Contenu de la 2e ligne
        ('FONTNAME', (0,1), (-1,1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,1), 9), 
        ('ALIGN', (0,1), (-1,1), 'CENTER'),
        ('VALIGN', (0,1), (-1,1), 'MIDDLE'),

        # Réduction du padding vertical
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ])

    info_table.setStyle(info_table_style)
    story.append(info_table)
    story.append(Spacer(1, 0.5 * cm))

    # Construction du tableau
    table = Table(lignes_facture, colWidths=[8*cm, 2.5*cm, 3*cm, 3*cm])
    table_style = TableStyle([
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
    for i in range(1, len(lignes_facture), 2):
        table_style.add('BACKGROUND', (0,i), (-1,i), colors.lightgrey)
    table.setStyle(table_style)
    story.append(table)
    story.append(Spacer(1, 0.5*cm))

    # Section des totaux et paiements
    story.append(Paragraph(f"<b>Montant total : {montant_total:.2f} F CFA</b>", style_bold))
    story.append(Spacer(1, 0.3*cm))
    
    # Affichage des informations de paiement
    if montant_paye > 0:
        story.append(Paragraph(f"<b>Montant déjà payé : {montant_paye:.2f} F CFA</b>", style_bold))
        
        # Détail des paiements par tranche
        if hasattr(vente, 'paiements') and vente.paiements.exists():
            story.append(Spacer(1, 0.2*cm))
            story.append(Paragraph("<b>Détail des paiements :</b>", style_normal))
            for paiement in vente.paiements.all().order_by('date_paiement'):
                story.append(Paragraph(
                    f"• Tranche {paiement.numero_tranche} : {paiement.montant:.2f} F CFA "
                    f"(le {paiement.date_paiement.strftime('%d/%m/%Y')})", 
                    style_normal
                ))
    
    # Montant restant
    if montant_restant > 0:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(f"<b><font color='red'>Montant restant à payer : {montant_restant:.2f} F CFA</font></b>", style_important))
        
        # Message selon le statut - Vérification de la méthode est_en_retard
        try:
            if callable(getattr(vente, 'est_en_retard', None)) and vente.est_en_retard():
                story.append(Paragraph(
                    f"<b><font color='red'>⚠️ PAIEMENT EN RETARD ⚠️</font></b>", 
                    style_important
                ))
            elif hasattr(vente, 'date_paiement') and vente.date_paiement < tz.now():
                story.append(Paragraph(
                    f"<b><font color='red'>⚠️ PAIEMENT EN RETARD ⚠️</font></b>", 
                    style_important
                ))
        except:
            pass  # Ignore les erreurs de vérification du retard
    else:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(f"<b><font color='green'>✓ FACTURE ENTIÈREMENT RÉGLÉE</font></b>", style_important))

    doc.build(story)
    buffer.seek(0)

    # Fusion avec papier en-tête
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
            final_buffer = buffer  # fallback sans fusion
    else:
        print(f"Fichier papier en-tête introuvable : {papier_en_tete_path}")
        final_buffer = buffer  # fallback sans fusion

    return final_buffer


def ajouter_vente(request): 
    if request.method == "POST":
        try:
            ecole = Ecoles.objects.get(id=request.POST['ecole'])
            cahier_ids = request.POST.getlist('cahiers[]')
            quantites = request.POST.getlist('quantites[]')
            montant_verse_str = request.POST.get('montant_verse')

            if len(cahier_ids) != len(quantites):
                messages.error(request, "Erreur : correspondance cahiers/quantités incorrecte.")
                return redirect('ventes')

            now = timezone.now()
            date_paiement = now + timedelta(days=30)  

            vente = Vente.objects.create(
                ecole=ecole,
                date_paiement=date_paiement,
            )

            montant_total = 0
            for cahier_id, qte in zip(cahier_ids, quantites):
                cahier = Cahiers.objects.get(id=cahier_id)
                qte = int(qte)
                if cahier.quantite_stock < qte:
                    messages.error(request, f"Stock insuffisant pour {cahier.titre} (stock : {cahier.quantite_stock})")
                    vente.delete()
                    return redirect('ventes')
                ligne = LigneVente.objects.create(vente=vente, cahier=cahier, quantite=qte)
                montant_total += ligne.montant
                cahier.quantite_stock -= qte
                cahier.save()

            # Si un montant versé est renseigné
            if montant_verse_str:
                montant_verse = Decimal(montant_verse_str)
                if montant_verse > 0:
                    if montant_verse > montant_total:
                        messages.warning(request, "Le montant versé dépasse le total. Il a été ajusté.")
                        montant_verse = montant_total
                    Paiement.objects.create(
                        vente=vente,
                        montant=montant_verse,
                        numero_tranche=1
                    )

            final_buffer = generer_facture_pdf(vente)
            filename = f"facture_{vente.id}.pdf"
            vente.facture_pdf.save(filename, ContentFile(final_buffer.read()), save=True)

            messages.success(request, "Vente enregistrée avec succès.")
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
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
    
    # Vérifier si la date limite est dépassée
    if vente.est_en_retard():
        messages.warning(request, f"Attention : La date limite de paiement ({vente.date_paiement.strftime('%d/%m/%Y')}) est dépassée !")

    if request.method == 'POST':
        try:
            montant = Decimal(request.POST.get('montant'))
            
            # Calcul du montant restant avec gestion des méthodes/propriétés
            try:
                montant_restant = vente.montant_restant() if callable(getattr(vente, 'montant_restant', None)) else getattr(vente, 'montant_restant', 0)
            except:
                # Calcul manuel si la méthode n'existe pas
                montant_total = sum(ligne.montant for ligne in vente.lignes.all())
                montant_paye = sum(p.montant for p in vente.paiements.all())
                montant_restant = montant_total - montant_paye
            
            if montant <= 0:
                messages.error(request, "Le montant doit être supérieur à 0.")
            elif montant > montant_restant:
                messages.error(request, f"Le montant ({montant} F) dépasse le montant restant à payer ({montant_restant} F).")
            else:
                # Calcul du numéro de tranche
                try:
                    numero_tranche = vente.nombre_tranches_payees() + 1 if callable(getattr(vente, 'nombre_tranches_payees', None)) else vente.paiements.count() + 1
                except:
                    numero_tranche = vente.paiements.count() + 1
                
                Paiement.objects.create(
                    vente=vente, 
                    montant=montant,
                    numero_tranche=numero_tranche
                )
                
                # Régénération de la facture PDF avec les nouvelles informations de paiement
                try:
                    final_buffer = generer_facture_pdf(vente)
                    filename = f"facture_{vente.id}.pdf"
                    
                    # Supprimer l'ancien fichier s'il existe
                    if vente.facture_pdf:
                        vente.facture_pdf.delete(save=False)
                    
                    # Sauvegarder le nouveau fichier
                    vente.facture_pdf.save(filename, ContentFile(final_buffer.read()), save=True)
                    
                except Exception as pdf_error:
                    print(f"Erreur lors de la régénération du PDF : {pdf_error}")
                    # Le paiement est enregistré même si la génération PDF échoue
                
                # Vérification si la vente est réglée avec gestion des méthodes
                try:
                    est_reglee = vente.est_reglee() if callable(getattr(vente, 'est_reglee', None)) else False
                    if not est_reglee:
                        # Calcul manuel
                        montant_total = sum(ligne.montant for ligne in vente.lignes.all())
                        montant_paye_total = sum(p.montant for p in vente.paiements.all())
                        est_reglee = montant_paye_total >= montant_total
                except:
                    est_reglee = False
                
                # Recalcul du montant restant pour le message
                try:
                    nouveau_montant_restant = vente.montant_restant() if callable(getattr(vente, 'montant_restant', None)) else 0
                except:
                    montant_total = sum(ligne.montant for ligne in vente.lignes.all())
                    montant_paye_total = sum(p.montant for p in vente.paiements.all())
                    nouveau_montant_restant = montant_total - montant_paye_total
                
                if est_reglee:
                    messages.success(request, f"Paiement de {montant} F enregistré. La vente est maintenant entièrement réglée ! La facture a été mise à jour.")
                else:
                    messages.success(request, f"Paiement de {montant} F enregistré (Tranche {numero_tranche}/3). Montant restant : {nouveau_montant_restant} F. La facture a été mise à jour.")
                    
        except Exception as e:
            messages.error(request, f"Erreur lors de l'enregistrement du paiement : {str(e)}")
    
    return redirect('ventes')


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

    for vente in ventes:
        paiements = vente.paiements.all()
        dates_paiements = ", ".join([p.date_paiement.strftime('%d/%m/%Y') for p in paiements]) or "Aucun paiement"
        montant_total_general += vente.montant_total
        montant_paye_general += vente.montant_paye

        donnees_tableau.append([
            vente.date_paiement.strftime('%d/%m/%Y') if vente.date_paiement else "N/A",
            f"{vente.montant_total:.0f} F",
            f"{vente.montant_paye:.0f} F",
            f"{vente.montant_restant():.0f} F",
            vente.statut_paiement(),
            dates_paiements[:30] + "..." if len(dates_paiements) > 30 else dates_paiements
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

    # Tableau des ventes
    table = Table(donnees_tableau, colWidths=[3*cm]*4 + [2.5*cm, 4*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
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