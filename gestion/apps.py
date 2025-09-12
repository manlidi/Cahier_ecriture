from django.apps import AppConfig
from django.utils import timezone
from datetime import timedelta

class GestionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gestion'