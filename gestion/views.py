from django.shortcuts import *
from .models import *
from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
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
    # Ventes par jour (7 derniers jours)
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
    # Vérifier les ventes en retard et afficher une alerte
    ventes_en_retard = Vente.objects.filter(
        date_paiement__lt=timezone.now()
    ).exclude(id__in=Vente.objects.filter(paiements__isnull=False).annotate(
        total_paye=models.Sum('paiements__montant')
    ).filter(total_paye__gte=models.F('lignes__montant')))
    
    if ventes_en_retard.exists():
        messages.warning(request, f"Attention : {ventes_en_retard.count()} vente(s) en retard de paiement !")
    
    context = {
        'ventes': Vente.objects.prefetch_related('lignes__cahier', 'ecole', 'paiements'),
        'cahiers': Cahiers.objects.all(),
        'ecoles': Ecoles.objects.all()
    }
    return render(request, 'ventes.html', context)


def ajouter_vente(request):
    if request.method == "POST":
        try:
            ecole = Ecoles.objects.get(id=request.POST['ecole'])
            date_paiement = request.POST['date_paiement']
            cahier_ids = request.POST.getlist('cahiers[]')
            quantites = request.POST.getlist('quantites[]')

            if len(cahier_ids) != len(quantites):
                messages.error(request, "Erreur : correspondance cahiers/quantités incorrecte.")
                return redirect('ventes')

            vente = Vente.objects.create(
                ecole=ecole,
                date_paiement=date_paiement,
            )

            lignes_facture = [["Cahier", "Quantité", "Prix Unitaire", "Total"]]
            montant_total = 0

            for cahier_id, qte in zip(cahier_ids, quantites):
                cahier = Cahiers.objects.get(id=cahier_id)
                qte = int(qte)

                if cahier.quantite_stock < qte:
                    messages.error(request, f"Stock insuffisant pour {cahier.titre} (stock : {cahier.quantite_stock})")
                    vente.delete()
                    return redirect('ventes')

                ligne = LigneVente.objects.create(
                    vente=vente,
                    cahier=cahier,
                    quantite=qte,
                )

                montant_total += ligne.montant
                lignes_facture.append([
                    cahier.titre,
                    str(qte),
                    f"{cahier.prix:.2f} F",
                    f"{ligne.montant:.2f} F"
                ])

                cahier.quantite_stock -= qte
                cahier.save()

            # Génération du PDF
            buffer = BytesIO()
            p = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4

            p.setFont("Helvetica-Bold", 14)
            p.drawString(2 * cm, height - 2 * cm, "Facture de Vente")
            p.setFont("Helvetica", 11)
            p.drawString(2 * cm, height - 2.8 * cm, f"École : {ecole.nom}")
            p.drawString(2 * cm, height - 3.5 * cm, f"Date limite de paiement : {date_paiement}")

            table = Table(lignes_facture, colWidths=[7*cm, 3*cm, 3*cm, 3*cm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ]))
            table.wrapOn(p, width, height)
            table.drawOn(p, 2 * cm, height - 12 * cm)

            p.setFont("Helvetica-Bold", 12)
            p.drawString(2 * cm, height - 13.5 * cm, f"Montant total : {montant_total:.2f} F")
            p.setFont("Helvetica", 10)
            p.drawString(2 * cm, height - 14.5 * cm, "Paiement possible en 3 tranches maximum")
            p.drawString(2 * cm, height - 16 * cm, "Signature du vendeur :")
            p.drawString(10 * cm, height - 16 * cm, "Signature de l'école :")

            p.line(2 * cm, height - 16.3 * cm, 7 * cm, height - 16.3 * cm)
            p.line(10 * cm, height - 16.3 * cm, 16 * cm, height - 16.3 * cm)

            p.showPage()
            p.save()

            pdf_content = buffer.getvalue()
            vente.facture_pdf.save(f"facture_{vente.id}.pdf", ContentFile(pdf_content))
            vente.save()

            messages.success(request, "Vente enregistrée avec succès.")
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
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
            montant_restant = vente.montant_restant()
            
            if montant <= 0:
                messages.error(request, "Le montant doit être supérieur à 0.")
            elif montant > montant_restant:
                messages.error(request, f"Le montant ({montant} F) dépasse le montant restant à payer ({montant_restant} F).")
            else:
                numero_tranche = vente.nombre_tranches_payees() + 1
                Paiement.objects.create(
                    vente=vente, 
                    montant=montant,
                    numero_tranche=numero_tranche
                )
                
                if vente.est_reglee():
                    messages.success(request, f"Paiement de {montant} F enregistré. La vente est maintenant entièrement réglée !")
                else:
                    messages.success(request, f"Paiement de {montant} F enregistré (Tranche {numero_tranche}/3). Montant restant : {vente.montant_restant()} F")
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