from django.contrib import admin
from .models import (
    Cahiers, Ecoles, AnneeScolaire, Vente, LigneVente, 
    Paiement, BilanAnneeScolaire, BilanMensuel,
    Notification, EmailNotification
)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['titre', 'type_notification', 'est_lu', 'email_envoye', 'date_creation']
    list_filter = ['type_notification', 'est_lu', 'email_envoye', 'date_creation']
    search_fields = ['titre', 'message']
    readonly_fields = ['date_creation', 'date_lecture']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('cahier', 'vente')

@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    list_display = ['email', 'nom', 'est_actif', 'date_ajout']
    list_filter = ['est_actif', 'date_ajout']
    search_fields = ['email', 'nom']

# Gardez vos autres registrations existantes si il y en a
