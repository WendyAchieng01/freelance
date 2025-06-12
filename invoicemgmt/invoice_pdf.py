import os
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
from reportlab.lib.pagesizes import letter
from django.contrib.staticfiles import finders
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from freelance.settings import BASE_DIR


def load_custom_font():
    font_paths = {
        'Roxborough': 'static/webfonts/roxborough-cf-medium.ttf',
        'CorporateS': 'static/webfonts/CorporateS-Bold.ttf',
        'Neuzeit-Office': 'static/webfonts/Neuzeit-Office-Regular.ttf'
    }
    for font_name, font_path in font_paths.items():
        pdfmetrics.registerFont(
            TTFont(font_name, os.path.join(BASE_DIR, font_path)))


def generate_invoice_pdf(invoice):
    load_custom_font()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    # Define custom styles
    custom_styles = {
        'Heading': ParagraphStyle('Heading', fontName='Roxborough', fontSize=34, leading=40, spaceAfter=10),
        'BodyText': ParagraphStyle('BodyText', parent=styles['BodyText'], fontName='Neuzeit-Office', fontSize=12, leading=10, spaceAfter=3),
        'InvoiceNumber': ParagraphStyle('InvoiceNumber', fontName='Roxborough', fontSize=16, leading=20, spaceAfter=12),
        'ThankYou': ParagraphStyle('ThankYou', fontName='Helvetica-Bold', fontSize=16, leading=20, spaceBefore=12, spaceAfter=6),
        'TermsText': ParagraphStyle('TermsText', fontName='Helvetica', fontSize=10, leading=12, spaceAfter=6)
    }

    # Define table styles
    table_styles = {
        'billed_to': TableStyle([('FONTNAME', (0, 0), (-1, -1), 'Helvetica'), ('FONTSIZE', (0, 0), (-1, -1), 10), ('VALIGN', (0, 0), (-1, -1), 'TOP')]),
        'total_amount': TableStyle([('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 12), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6), ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black)]),
        'line_items': TableStyle([('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'), ('FONTSIZE', (0, 0), (-1, -1), 10), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEABOVE', (0, 0), (-1, 0), 1, colors.black), ('LINEBELOW', (0, 0), (-1, -1), 1, colors.black), ('TOPPADDING', (0, 1), (-1, -1), 6), ('BOTTOMPADDING', (0, 1), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, 0), 6), ('BOTTOMPADDING', (0, 0), (-1, 0), 6)])
    }

    elements = []

    # Add company logo and invoice text with spacing
    logo_path = finders.find('images/logo/logo.jpg')
    logo = Image(logo_path, width=1.0 * inch, height=0.6 * inch)
    invoice_text = Paragraph("INVOICE", custom_styles['Heading'])
    table = Table([[Spacer(1, 0.4 * inch), logo, Spacer(1, 0.4 * inch), Spacer(1, 0.4 * inch),
                  invoice_text]], colWidths=[0.5 * inch, 1 * inch, 1 * inch, 2 * inch, 3 * inch])
    elements.append(table)
    elements.append(Spacer(1, 0.1 * inch))

    # Add invoice number, invoice date, and "Billed To:" in a table
    client = invoice.client.profile
    billed_to_data = [
        [Paragraph("Billed To:", custom_styles['InvoiceNumber'])],
        [Paragraph(f"{invoice.client.username}", custom_styles['BodyText'])],
        [Paragraph(f"{client.phone}", custom_styles['BodyText'])],
        [Paragraph(f"{client.location}", custom_styles['BodyText'])]
    ]
    billed_to_table = Table(billed_to_data, colWidths=[
                            2 * inch], style=table_styles['billed_to'])

    invoice_info_data = [
        [Paragraph(f"Invoice # {invoice.invoice_number}",
                   custom_styles['BodyText'])],
        [Paragraph(
            f"Invoice Date: {invoice.invoice_date.strftime('%Y-%m-%d')}", custom_styles['BodyText'])]
    ]
    invoice_info_table = Table(invoice_info_data, colWidths=[5.5 * inch])

    table = Table([[billed_to_table, Spacer(1, 0.4 * inch), Spacer(1, 0.4 * inch), invoice_info_table]],
                  colWidths=[2 * inch, 0.5 * inch, 2 * inch, 2 * inch], style=table_styles['billed_to'])
    elements.append(table)
    elements.append(Spacer(1, 0.5 * inch))

    # Add line items table
    line_items_data = [["Description", "Quantity", "Rate", "Amount"]]
    for line_item in invoice.line_items.all():
        line_items_data.append([
            line_item.description,
            str(line_item.quantity),
            f"${line_item.rate}",
            f"${line_item.amount}",
        ])

    total_width = doc.width
    col_widths = [
        total_width * 0.5,  # Description (50% of total width)
        total_width * 0.15,  # Quantity (15% of total width)
        total_width * 0.15,  # Rate (15% of total width)
        total_width * 0.2,  # Amount (20% of total width)
    ]

    line_items_table = Table(
        line_items_data, colWidths=col_widths, style=table_styles['line_items'])
    elements.append(line_items_table)

    total_amount = sum(
        line_item.amount for line_item in invoice.line_items.all())
    total_amount_data = [
        ["Total", Spacer(1, 0.1 * inch), f"${total_amount:.2f}"]]
    total_amount_table = Table(total_amount_data, colWidths=[
                               1.5 * inch, 3.6 * inch, 1 * inch], style=table_styles['total_amount'])
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(total_amount_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Add company logo at the bottom
    logo_bottom_path = finders.find('images/logo/sign.png')
    logo_bottom = Image(logo_bottom_path, width=2.5 * inch, height=1 * inch)
    logo_table = Table(
        [[Spacer(5 * inch, 1 * inch), logo_bottom]], colWidths=[3 * inch, 1.5 * inch])
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(logo_table)

    # Add "Thank You!" text
    elements.append(Paragraph("Thank You!", custom_styles['ThankYou']))

    # Add terms and conditions
    terms_data = [
        [Paragraph("TERMS & CONDITIONS", custom_styles['InvoiceNumber']), None],
        [Paragraph("Payment is due within 30 days",
                   custom_styles['TermsText']), None],
        [Paragraph("Send Payment To:", custom_styles['InvoiceNumber']), Paragraph(
            "Nill Tech Solutions", custom_styles['InvoiceNumber'])],
        [Paragraph("M-Pesa No.:", custom_styles['TermsText']),
         Paragraph("Nairobi, Kenya", custom_styles['TermsText'])],
        [Paragraph("Binance ID:", custom_styles['TermsText']), Paragraph(
            "+254 712 345 678", custom_styles['TermsText'])],
        [Paragraph(f"Due Date: {invoice.due_date.strftime('%Y-%m-%d')}", custom_styles['TermsText']),
         Paragraph("info@wendymudenyo.com", custom_styles['TermsText'])],
    ]
    terms_table = Table(terms_data, colWidths=[
                        4 * inch, 3 * inch], style=table_styles['billed_to'])
    table_with_spacer = Table(
        [[terms_table, Spacer(0.5 * inch, 0.1 * inch)]], colWidths=[6 * inch, 0.65 * inch])
    elements.append(table_with_spacer)

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()

    return pdf
