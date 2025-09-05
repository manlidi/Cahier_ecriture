from django.apps import AppConfig
from django.utils import timezone
from datetime import timedelta

class GestionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gestion'

    
    def ready(self):
            from .models import Vente
            try:
                ventes_sans_date = Vente.objects.filter(date_paiement__isnull=True)
                for v in ventes_sans_date:
                    base_date = v.created_at or timezone.now()
                    v.date_paiement = base_date + timedelta(days=30)
                    v.save(update_fields=['date_paiement'])
            except Exception as e:
                # Éviter que l'app plante au lancement (ex: migrations pas encore appliquées)
                print(f"[WARN] Impossible de mettre à jour les ventes sans date_paiement : {e}")
