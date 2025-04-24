import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import PyPDF2
from reportlab.platypus import Table, TableStyle
import streamlit as st
from reportlab.pdfbase.ttfonts import TTFont
import os
from reportlab.pdfbase import pdfmetrics
from datetime import datetime
from src.services.utils_payment import user_data

font_path = "resources/fonts/OpenSauceSans-Regular.ttf"
font_bold = "resources/fonts/OpenSauceSans-Bold.ttf"

if os.path.exists(font_path):
    pdfmetrics.registerFont(TTFont("OpenSauce", font_path))
else:
    print("⚠️ Advertencia: La fuente 'Open Sauce' no se encontró. Se usará 'Helvetica' como alternativa.")

if os.path.exists(font_bold):
    pdfmetrics.registerFont(TTFont("OpenSauceBold", font_bold))
else:
    print("⚠️ Advertencia: La fuente 'Open Sauce Bold' no se encontró. Se usará 'Helvetica' como alternativa.")


def create_overlay(data, overlay_path):

    commercial_data = user_data(data.get('commercial'))

    c = canvas.Canvas(overlay_path, pagesize=letter)
    current_date = datetime.today().strftime("%d/%m/%Y")

    c.setFont("OpenSauceBold", 7)

    c.drawString(525, 669, f"{data.get('no_solicitud', '').upper()}")
    c.drawString(510, 660, current_date)

    c.setFont("OpenSauce", 9)
    name = f"{commercial_data.get('name', '').upper()}.  "
    position = commercial_data.get('position', '').upper()

    x = 300
    y = 130

    font_bold = "OpenSauceBold"
    font_regular = "OpenSauce"
    font_size = 8

    c.setFont(font_bold, font_size)
    c.drawString(x, y, name)
    name_width = c.stringWidth(name, font_bold, font_size)

    c.setFont(font_regular, font_size)
    c.drawString(x + name_width, y, f"{position}")

    c.setFont("OpenSauce", 8)
    c.drawString(300, 120, f"{commercial_data.get('tel', '').upper()}")
    c.drawString(300, 110, f"{commercial_data.get('email', '').upper()}")

    c.setFont("OpenSauceBold", 10) 
    c.drawString(118, 570, f"{data.get('client', '').upper()}")
    c.drawString(118, 558, f"{data.get('customer_name', '').upper()}")

    c.setFont("OpenSauce", 10) 
    c.drawString(118, 546, f"{data.get('customer_phone', '').upper()}")
    c.drawString(118, 534, f"{data.get('customer_email', '')}")

    transport_type = data.get('transport_type', '')
    if isinstance(transport_type, list):
        transport_type = ", ".join(transport_type)

    c.drawString(300, 570, transport_type)
    c.drawString(300, 558, f"Tipo de Operación: {data.get('operation_type')}")
    c.drawString(300, 546, f"Referencia: {data.get('reference')}")

    table_data = []
    total_cost_by_currency = {}

    for container, surcharges in data.get("additional_surcharges", {}).items():
        for additional in surcharges:
            cost = additional.get("cost", 0)
            currency = additional.get("currency", "USD")

            total_cost_by_currency[currency] = total_cost_by_currency.get(currency, 0) + cost

            row = [
                additional.get("concept", ""), 
                currency,                      
                container,                      
                f"${cost:.2f}",                 
            ]
            table_data.append(row)

    col_widths = [80, 200, 5, 160]

    table = Table(table_data, colWidths=col_widths)

    style = TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'OpenSauce'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ])
    table.setStyle(style)

    x = 100
    y = 460
    table_width, table_height = table.wrapOn(c, 0, 0)
    table.drawOn(c, x, y - table_height)

    totales_str = "  ".join([f"${total:.2f} {currency}" for currency, total in total_cost_by_currency.items()])

    c.setFont("OpenSauceBold", 9)
    c.drawString(395, 240, totales_str)

    c.setFont("OpenSauce", 8)
    y_position = 190

    y_position_offset = 0
    fields = [
        ("", "* Precios no incluyen IVA y están sujetos al mismo."),
        ("", "* Los pagos en dólares se realizan a la TRM del día del pago a la línea +2%"),
        ("", "* (El día de la facturación se coloca la TRM a la que se realiza el pago)."),
    ]

    notes = data.get('Notes', '').strip()
    if notes:
        fields.append(("Notes", notes))  

    for label, value in fields:
        if str(value).strip() and str(value) != "N/A":
            if label == "Notes": 
                for line in value.splitlines():
                    c.drawString(115, y_position - y_position_offset, line)
                    y_position_offset += 10
            else:
                c.drawString(115, y_position - y_position_offset, f"{label}{': ' if label else ''}{value}")
                y_position_offset += 10

    c.save()

def merge_pdfs(template_path, overlay_path, output_path):
    template_pdf = PyPDF2.PdfReader(template_path)
    overlay_pdf = PyPDF2.PdfReader(overlay_path)
    output = PyPDF2.PdfWriter()

    for page_number in range(len(template_pdf.pages)):
        template_page = template_pdf.pages[page_number]
        if page_number < len(overlay_pdf.pages):
            overlay_page = overlay_pdf.pages[page_number]
            template_page.merge_page(overlay_page)
        output.add_page(template_page)

    with open(output_path, "wb") as f_out:
        output.write(f_out)

def generate_pdf(data, template_path="resources/documents/Solicitud Anticipo-2.pdf", output_path="resources/documents/Solicitud.pdf", overlay_path="resources/documents/overlay.pdf"):
    create_overlay(data, overlay_path)
    merge_pdfs(template_path, overlay_path, output_path)
    return output_path