from django.shortcuts import *
from gestion.models import Ecoles, AnneeScolaire, Vente, LigneVente, Paiement, Cahiers
from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.lib.units import cm
from io import BytesIO
from django.contrib import messages
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
import os
from django.conf import settings
from PyPDF2 import PdfReader, PdfWriter
from django.core.paginator import Paginator
from decimal import InvalidOperation
from gestion.Views.general import calculer_dette_ecole
from django.db import models
from gestion.Views.general import generer_facture_pdf

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
