from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from ..models import Notification, EmailNotification, TypeNotification
from ..services import NotificationService
import json

def notifications_list(request):
    """Vue pour afficher la liste des notifications"""
    # Vérification automatique et envoi des notifications à chaque chargement
    notification_service = NotificationService()
    try:
        notification_service.verifier_notifications()
        notification_service.envoyer_notifications_en_attente()
    except Exception as e:
        # Log l'erreur mais ne pas interrompre le chargement de la page
        print(f"Erreur lors de la vérification automatique des notifications: {e}")
    
    # Filtres
    type_filtre = request.GET.get('type', '')
    statut_filtre = request.GET.get('statut', '')
    recherche = request.GET.get('q', '')
    
    # Query de base
    notifications = Notification.objects.all()
    
    # Application des filtres
    if type_filtre:
        notifications = notifications.filter(type_notification=type_filtre)
    
    if statut_filtre == 'lu':
        notifications = notifications.filter(est_lu=True)
    elif statut_filtre == 'non_lu':
        notifications = notifications.filter(est_lu=False)
    
    if recherche:
        notifications = notifications.filter(
            Q(titre__icontains=recherche) | Q(message__icontains=recherche)
        )
    
    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistiques
    stats = {
        'total': Notification.objects.count(),
        'non_lues': Notification.objects.filter(est_lu=False).count(),
        'stock_faible': Notification.objects.filter(type_notification=TypeNotification.STOCK_FAIBLE).count(),
        'echeances': Notification.objects.filter(type_notification=TypeNotification.ECHEANCE_PAIEMENT).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'type_filtre': type_filtre,
        'statut_filtre': statut_filtre,
        'recherche': recherche,
        'types_notification': TypeNotification.choices,
    }
    
    return render(request, 'notifications/list.html', context)

def notification_detail(request, notification_id):
    """Vue pour afficher le détail d'une notification"""
    notification = get_object_or_404(Notification, id=notification_id)
    
    # Marquer comme lue (sans message car c'est automatique)
    if not notification.est_lu:
        notification.marquer_comme_lu()
    
    return render(request, 'notifications/detail.html', {
        'notification': notification
    })

@require_http_methods(["POST"])
def marquer_comme_lu(request, notification_id):
    """Marque une notification comme lue via AJAX"""
    notification = get_object_or_404(Notification, id=notification_id)
    notification.marquer_comme_lu()
    
    return JsonResponse({
        'success': True,
        'message': 'Notification marquée comme lue'
    })

@require_http_methods(["POST"])
def supprimer_notification(request, notification_id):
    """Supprime une notification"""
    notification = get_object_or_404(Notification, id=notification_id)
    notification.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': 'Notification supprimée'
        })
    
    messages.success(request, 'Notification supprimée.')
    return redirect('notifications_list')

def gestion_emails(request):
    """Vue pour gérer les emails de notification"""
    emails = EmailNotification.objects.all().order_by('nom', 'email')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'ajouter':
            email = request.POST.get('email', '').strip()
            nom = request.POST.get('nom', '').strip()
            
            if email:
                email_obj, created = EmailNotification.objects.get_or_create(
                    email=email,
                    defaults={'nom': nom}
                )
                
                if created:
                    messages.success(request, f'Email {email} ajouté avec succès.')
                else:
                    messages.warning(request, f'Email {email} existe déjà.')
            else:
                messages.error(request, 'Veuillez saisir une adresse email.')
        
        elif action == 'supprimer':
            email_id = request.POST.get('email_id')
            if email_id:
                try:
                    email_obj = EmailNotification.objects.get(id=email_id)
                    email_obj.delete()
                    messages.success(request, 'Email supprimé.')
                except EmailNotification.DoesNotExist:
                    messages.error(request, 'Email introuvable.')
        
        elif action == 'toggle_actif':
            email_id = request.POST.get('email_id')
            if email_id:
                try:
                    email_obj = EmailNotification.objects.get(id=email_id)
                    email_obj.est_actif = not email_obj.est_actif
                    email_obj.save()
                    statut = 'activé' if email_obj.est_actif else 'désactivé'
                    messages.success(request, f'Email {statut}.')
                except EmailNotification.DoesNotExist:
                    messages.error(request, 'Email introuvable.')
        
        return redirect('gestion_emails')
    
    return render(request, 'notifications/emails.html', {
        'emails': emails
    })

def test_notifications(request):
    """Vue pour tester le système de notifications (dev uniquement)"""
    if request.method == 'POST':
        resultats = NotificationService.executer_verification_periodique()
        
        messages.info(request, 
            f"Test terminé: {resultats['nouvelles_notifications']} nouvelles notifications, "
            f"{resultats['emails_reussis']}/{resultats['emails_traites']} emails envoyés."
        )
    
    return render(request, 'notifications/test.html')

def get_notification_count(request):
    """API pour récupérer le nombre de notifications non lues"""
    count = Notification.objects.filter(est_lu=False).count()
    return JsonResponse({'count': count})