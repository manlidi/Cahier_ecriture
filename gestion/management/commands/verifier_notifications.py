from django.core.management.base import BaseCommand
from gestion.services import NotificationService

class Command(BaseCommand):
    help = 'Vérifie les stocks et envoie les notifications'

    def handle(self, *args, **options):
        self.stdout.write('Début de la vérification des notifications...')
        
        resultats = NotificationService.executer_verification_periodique()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Vérification terminée:\n'
                f'- {resultats["nouvelles_notifications"]} nouvelles notifications créées\n'
                f'- {resultats["emails_traites"]} emails traités\n'
                f'- {resultats["emails_reussis"]} emails envoyés avec succès'
            )
        )