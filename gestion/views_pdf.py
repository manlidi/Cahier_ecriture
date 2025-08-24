from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import get_template
from django.utils import timezone
from django.conf import settings
from gestion.models import Vente
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from decimal import Decimal


def generer_facture_pdf(request, vente_id):
    """Génère une facture PDF pour une vente avec les différentes sessions d'articles"""
    
    # Récupérer la vente
    vente = get_object_or_404(Vente, id=vente_id)
    
    # Créer la réponse HTTP
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="facture_{vente.ecole.nom.replace(" ", "_")}_{vente.id}.pdf"'
    
    # Créer le document PDF
    doc = SimpleDocTemplate(response, pagesize=A4, 
                          rightMargin=2*cm, leftMargin=2*cm,
                          topMargin=2*cm, bottomMargin=2*cm)
    
    # Créer les styles
    styles = getSampleStyleSheet()
    
    # Style personnalisé pour le titre
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    # Style pour les sous-titres
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=12,
        textColor=colors.darkblue
    )
    
    # Style pour le contenu
    content_style = ParagraphStyle(
        'CustomContent',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6
    )
    
    # Style pour les totaux
    total_style = ParagraphStyle(
        'CustomTotal',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6,
        alignment=TA_RIGHT,
        textColor=colors.darkgreen
    )
    
    # Contenu du PDF
    story = []
    
    # Titre principal
    story.append(Paragraph("FACTURE", title_style))
    story.append(Spacer(1, 20))
    
    # Informations de l'entreprise (à personnaliser selon vos besoins)
    story.append(Paragraph("ENTREPRISE DE CAHIERS D'ÉCRITURE", subtitle_style))
    story.append(Paragraph("Adresse de l'entreprise", content_style))
    story.append(Paragraph("Téléphone: +XXX XX XX XX XX", content_style))
    story.append(Paragraph("Email: contact@entreprise.com", content_style))
    story.append(Spacer(1, 20))
    
    # Informations de facturation
    data_facture = [
        ['FACTURE N°:', str(vente.id)[:8].upper()],
        ['DATE:', vente.created_at.strftime('%d/%m/%Y')],
        ['ÉCOLE:', vente.ecole.nom],
        ['ANNÉE SCOLAIRE:', str(vente.annee_scolaire)],
        ['ADRESSE:', vente.ecole.adresse if vente.ecole.adresse else 'Non renseignée']
    ]
    
    table_facture = Table(data_facture, colWidths=[4*cm, 8*cm])
    table_facture.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(table_facture)
    story.append(Spacer(1, 30))
    
    # Récupérer toutes les dettes de l'école par année
    dettes_par_annee = vente.get_dettes_par_annee_ecole()
    total_dettes_ecole = vente.get_total_dettes_ecole()
    
    # Affichage des dettes par année (si il y en a)
    if dettes_par_annee:
        story.append(Paragraph("HISTORIQUE DES DETTES PAR ANNÉE SCOLAIRE", subtitle_style))
        
        # Tableau des dettes par année
        data_dettes = [['Année scolaire', 'Montant articles', 'Dette précédente', 'Sous-total', 'Payé', 'Restant dû']]
        
        for annee_str, dette_info in dettes_par_annee.items():
            data_dettes.append([
                str(dette_info['annee_scolaire']),
                f"{dette_info['montant_articles']:,.0f} F",
                f"{dette_info['dette_precedente']:,.0f} F",
                f"{dette_info['montant_total']:,.0f} F",
                f"{dette_info['montant_paye']:,.0f} F",
                f"{dette_info['montant_restant']:,.0f} F"
            ])
        
        # Ligne de total des dettes
        data_dettes.append([
            'TOTAL DETTES ÉCOLE',
            '', '', '', '',
            f"{total_dettes_ecole:,.0f} F"
        ])
        
        table_dettes = Table(data_dettes, colWidths=[3*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm])
        table_dettes.setStyle(TableStyle([
            # En-tête
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkred),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),  # Montants à droite
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            # Ligne de total
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightcoral),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 10),
        ]))
        
        story.append(table_dettes)
        story.append(Spacer(1, 20))
    
    # Dette précédente de la facture courante (si applicable)
    if vente.dette_precedente and vente.dette_precedente > 0:
        story.append(Paragraph("DETTE PRÉCÉDENTE INCLUSE DANS CETTE FACTURE", subtitle_style))
        if vente.description_dette:
            story.append(Paragraph(f"Description: {vente.description_dette}", content_style))
        story.append(Paragraph(f"Montant: {vente.dette_precedente:,.0f} F", content_style))
        story.append(Spacer(1, 20))
    
    # Sessions d'articles
    sessions = vente.get_articles_par_session()
    
    if sessions:
        story.append(Paragraph("DÉTAIL DES ARTICLES PAR SESSION D'AJOUT", subtitle_style))
        story.append(Spacer(1, 10))
        
        for i, session in enumerate(sessions, 1):
            # Titre de la session
            story.append(Paragraph(f"Session #{i} - {session['date_session'].strftime('%d/%m/%Y à %H:%M')}", 
                                 ParagraphStyle('SessionTitle', parent=styles['Heading3'], fontSize=12, 
                                              textColor=colors.darkred, spaceAfter=8)))
            
            # Tableau des articles de cette session
            data_session = [['Article', 'Quantité', 'Prix unitaire', 'Montant']]
            
            for ligne in session['lignes']:
                data_session.append([
                    ligne.cahier.titre,
                    str(ligne.quantite),
                    f"{ligne.cahier.prix:,.0f} F",
                    f"{ligne.montant:,.0f} F"
                ])
            
            # Ligne de total pour cette session
            data_session.append([
                'TOTAL SESSION', 
                f"{session['nombre_articles']} articles", 
                '', 
                f"{session['montant_total']:,.0f} F"
            ])
            
            table_session = Table(data_session, colWidths=[8*cm, 2*cm, 3*cm, 3*cm])
            table_session.setStyle(TableStyle([
                # En-tête
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 1), (-1, -1), 'CENTER'),  # Quantité centrée
                ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),   # Prix et montant à droite
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                # Ligne de total de session
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('TEXTCOLOR', (0, -1), (-1, -1), colors.darkred),
            ]))
            
            story.append(table_session)
            story.append(Spacer(1, 15))
    
    # Résumé financier
    story.append(Paragraph("RÉSUMÉ FINANCIER", subtitle_style))
    
    # Calculs
    montant_articles = sum(session['montant_total'] for session in sessions)
    dette_precedente = vente.dette_precedente or Decimal('0')
    montant_total_facture = montant_articles + dette_precedente
    montant_paye = vente.montant_paye
    montant_restant_facture = vente.montant_restant
    
    # Tableau du résumé financier de cette facture
    data_resume = [
        ['CETTE FACTURE:', ''],
        ['Montant des articles:', f"{montant_articles:,.0f} F"],
        ['Dette précédente incluse:', f"{dette_precedente:,.0f} F"],
        ['Total de cette facture:', f"{montant_total_facture:,.0f} F"],
        ['Montant payé:', f"{montant_paye:,.0f} F"],
        ['Restant sur cette facture:', f"{montant_restant_facture:,.0f} F"],
        ['', ''],
    ]
    
    # Ajouter le récapitulatif global de l'école si il y a d'autres dettes
    if dettes_par_annee and len(dettes_par_annee) > 1:
        data_resume.extend([
            ['RÉCAPITULATIF GLOBAL ÉCOLE:', ''],
            ['Total dettes toutes années:', f"{total_dettes_ecole:,.0f} F"],
        ])
    
    table_resume = Table(data_resume, colWidths=[8*cm, 4*cm])
    
    # Styles de base
    base_styles = [
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        # En-têtes de section en gras
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),  # CETTE FACTURE
        ('BACKGROUND', (0, 0), (1, 0), colors.lightblue),
        # Total de cette facture en gras
        ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),  
        ('BACKGROUND', (0, 3), (-1, 3), colors.lightblue),
        # Restant de cette facture
        ('FONTNAME', (0, 5), (-1, 5), 'Helvetica-Bold'),  
        ('BACKGROUND', (0, 5), (-1, 5), colors.lightcoral if montant_restant_facture > 0 else colors.lightgreen),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]
    
    table_resume.setStyle(TableStyle(base_styles))
    
    # Ajouter des styles conditionnels pour le récapitulatif global si présent
    if dettes_par_annee and len(dettes_par_annee) > 1:
        # Position de la ligne "RÉCAPITULATIF GLOBAL ÉCOLE"
        recap_row = len(data_resume) - 2
        additional_styles = [
            ('FONTNAME', (0, recap_row), (1, recap_row), 'Helvetica-Bold'),
            ('BACKGROUND', (0, recap_row), (1, recap_row), colors.lightyellow),
            ('FONTNAME', (0, recap_row + 1), (-1, recap_row + 1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, recap_row + 1), (-1, recap_row + 1), colors.lightyellow),
        ]
        table_resume.setStyle(TableStyle(base_styles + additional_styles))
    story.append(table_resume)
    story.append(Spacer(1, 30))
    
    # Pied de page avec informations légales
    story.append(Spacer(1, 30))
    story.append(Paragraph("Merci pour votre confiance !", 
                          ParagraphStyle('Thanks', parent=styles['Normal'], 
                                       alignment=TA_CENTER, fontSize=12, 
                                       textColor=colors.darkblue)))
    
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Facture générée le {timezone.now().strftime('%d/%m/%Y à %H:%M')}", 
                          ParagraphStyle('Generated', parent=styles['Normal'], 
                                       alignment=TA_CENTER, fontSize=8, 
                                       textColor=colors.grey)))
    
    # Construire le PDF
    doc.build(story)
    
    return response
