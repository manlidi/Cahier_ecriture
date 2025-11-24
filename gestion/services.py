from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import Notification, EmailNotification, Cahiers, TypeNotification, Vente
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    """Service pour gérer les notifications"""
    
    @staticmethod
    def verifier_stock_faible():
        """Vérifie les stocks faibles et crée des notifications"""
        seuil_stock = getattr(settings, 'NOTIFICATION_SEUIL_STOCK', 100)
        cahiers_stock_faible = Cahiers.objects.filter(quantite_stock__lte=seuil_stock)
        
        notifications_creees = []
        
        for cahier in cahiers_stock_faible:
            # Vérifier si une notification existe déjà pour ce cahier
            notification_existante = Notification.objects.filter(
                type_notification=TypeNotification.STOCK_FAIBLE,
                cahier=cahier,
                est_lu=False
            ).exists()
            
            if not notification_existante:
                notification = Notification.objects.create(
                    type_notification=TypeNotification.STOCK_FAIBLE,
                    titre=f"Stock faible: {cahier.titre}",
                    message=f"Le cahier '{cahier.titre}' n'a plus que {cahier.quantite_stock} exemplaires en stock.",
                    cahier=cahier
                )
                notifications_creees.append(notification)
        
        return notifications_creees

    @staticmethod
    def verifier_echeances():
        """Vérifie les ventes dont la date_paiement (échéance) est dans les prochains jours
        et crée une notification si nécessaire."""
        jours = getattr(settings, 'NOTIFICATION_ECHEANCE_JOURS', 7)
        maintenant = timezone.now()
        limite = maintenant + timezone.timedelta(days=jours)

        ventes_echeance = Vente.objects.filter(
            date_paiement__isnull=False,
            date_paiement__gte=maintenant,
            date_paiement__lte=limite
        )

        notifications_creees = []

        for vente in ventes_echeance:
            # Si la vente est déjà réglée (montant_restant == 0), on ignore
            try:
                montant_restant = vente.montant_restant
            except Exception:
                montant_restant = None

            if montant_restant is not None and montant_restant <= 0:
                continue

            # Vérifier si une notification existe déjà pour cette vente
            notification_existante = Notification.objects.filter(
                type_notification=TypeNotification.ECHEANCE_PAIEMENT,
                vente=vente,
                est_lu=False
            ).exists()

            if not notification_existante:
                date_str = vente.date_paiement.strftime('%d/%m/%Y') if vente.date_paiement else ''
                titre = f"Échéance paiement: {vente.ecole.nom} le {date_str}"
                message = (
                    f"La vente pour l'école '{vente.ecole.nom}' a une échéance de paiement prévue le {date_str}. "
                    f"Montant restant: {montant_restant if montant_restant is not None else 'N/A'} F."
                )

                notification = Notification.objects.create(
                    type_notification=TypeNotification.ECHEANCE_PAIEMENT,
                    titre=titre,
                    message=message,
                    vente=vente
                )
                notifications_creees.append(notification)

        return notifications_creees
    
    @staticmethod
    def envoyer_notification_email(notification):
        """Envoie une notification par email"""
        if not getattr(settings, 'NOTIFICATION_EMAIL_ACTIF', True):
            return False
        
        if notification.email_envoye:
            return False
        
        # Récupérer tous les emails actifs
        emails_actifs = EmailNotification.objects.filter(est_actif=True)
        
        if not emails_actifs.exists():
            logger.warning("Aucun email configuré pour les notifications")
            return False
        
        destinataires = [email.email for email in emails_actifs]
        
        try:
            sujet = f"[Cahier Écriture] {notification.titre}"
            message = notification.message
            
            send_mail(
                sujet,
                message,
                settings.DEFAULT_FROM_EMAIL,
                destinataires,
                fail_silently=False,
            )
            
            # Marquer l'email comme envoyé
            notification.email_envoye = True
            notification.save()
            
            logger.info(f"Email envoyé pour la notification {notification.id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de l'email pour la notification {notification.id}: {str(e)}")
            return False
    
    @staticmethod
    def traiter_notifications_en_attente():
        """Traite toutes les notifications en attente d'envoi par email"""
        notifications_en_attente = Notification.objects.filter(email_envoye=False)
        
        resultats = []
        for notification in notifications_en_attente:
            succes = NotificationService.envoyer_notification_email(notification)
            resultats.append({
                'notification_id': notification.id,
                'succes': succes
            })
        
        return resultats
    
    def verifier_notifications(self):
        """Vérifie et crée les notifications nécessaires (wrapper pour compatibilité)"""
        self.verifier_stock_faible()
        self.verifier_echeances()
    
    def envoyer_notifications_en_attente(self):
        """Envoie les emails pour les notifications en attente (wrapper pour compatibilité)"""
        self.traiter_notifications_en_attente()
    
    @staticmethod
    def supprimer_notifications_stock_cahier(cahier_id):
        """Supprime toutes les notifications de stock faible pour un cahier donné si le stock est suffisant"""
        from django.conf import settings
        
        seuil_stock = getattr(settings, 'NOTIFICATION_SEUIL_STOCK', 100)
        
        try:
            cahier = Cahiers.objects.get(id=cahier_id)
            
            # Si le stock est maintenant supérieur au seuil, supprimer TOUTES les notifications (lues ou non)
            if cahier.quantite_stock > seuil_stock:
                notifications_supprimees = Notification.objects.filter(
                    type_notification=TypeNotification.STOCK_FAIBLE,
                    cahier=cahier
                ).delete()
                
                logger.info(f"Suppression de {notifications_supprimees[0]} notification(s) de stock faible pour le cahier {cahier.titre}")
                return notifications_supprimees[0]
            
            return 0
            
        except Cahiers.DoesNotExist:
            logger.warning(f"Cahier {cahier_id} introuvable pour suppression de notifications")
            return 0
    
    @staticmethod
    def executer_verification_periodique():
        """Exécute toutes les vérifications périodiques"""
        # Vérifier les stocks faibles
        nouvelles_notifications = NotificationService.verifier_stock_faible()
        # Vérifier les échéances de paiement
        nouvelles_notifications += NotificationService.verifier_echeances()
        
        # Envoyer les emails pour toutes les notifications en attente
        resultats_emails = NotificationService.traiter_notifications_en_attente()
        
        return {
            'nouvelles_notifications': len(nouvelles_notifications),
            'emails_traites': len(resultats_emails),
            'emails_reussis': sum(1 for r in resultats_emails if r['succes'])
        }
