from django.shortcuts import *
from gestion.models import Vente, Paiement
from django.core.files.base import ContentFile
from django.contrib import messages
from decimal import Decimal
from django.utils import timezone
from gestion.Views.general import generer_facture_pdf

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