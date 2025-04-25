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
from services.utils import user_data
from reportlab.pdfbase.pdfmetrics import stringWidth

def wrapped_draw_string(c, text, x, y, fontName, fontSize, max_width, leading=12):
    words = text.split()
    line = ""
    y_offset = 0

    for word in words:
        test_line = f"{line} {word}".strip()
        if stringWidth(test_line, fontName, fontSize) <= max_width:
            line = test_line
        else:
            c.drawString(x, y - y_offset, line)
            y_offset += leading
            line = word

    if line:
        c.drawString(x, y - y_offset, line)

    return y_offset

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
    MAX_WIDTH = 200

    init_y = 570

    c.setFont("OpenSauceBold", 10)
    used_offset = wrapped_draw_string(
        c,
        data.get('client', '').upper(),
        x=118,
        y=init_y,
        fontName="OpenSauceBold",
        fontSize=10,
        max_width=MAX_WIDTH,
        leading=12
    )

    next_y = init_y - used_offset - 12 
    
    c.setFont("OpenSauceBold", 10)
    c.drawString(118, next_y, data.get('customer_name', '').upper())

    c.setFont("OpenSauce", 10)
    c.drawString(118, next_y - 12, data.get('customer_phone', '').upper())
    c.drawString(118, next_y - 24, data.get('customer_email', ''))

    transport_type = data.get('transport_type', '')
    
    if isinstance(transport_type, list):
        transport_type = ", ".join(transport_type)

    c.drawString(350, 570, transport_type)
    c.drawString(350, 558, f"Tipo de Operación: {data.get('operation_type')}")

    reference = data.get("reference", "")

    if reference.strip():
        c.drawString(300, 546, f"Referencia de cliente: {reference}")

    table_data = []
    total_cost_by_currency = {}

    # Procesar los additional_surcharges por tipo de contenedor
    for container, surcharges in data.get("additional_surcharges", {}).items():
        for additional in surcharges:
            cost = additional.get("cost", 0)
            currency = additional.get("currency", "USD")

            total_cost_by_currency[currency] = total_cost_by_currency.get(currency, 0) + cost

            row = [
                additional.get("concept", ""),  # Concepto
                currency,                       # Moneda
                container,                      # Contenedor
                f"${cost:.2f}",                 # Costo con formato
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

    totales_str = f"{data.get('total_cop_trm')}"

    c.setFont("OpenSauceBold", 9)
    c.drawString(395, 240, totales_str)

    c.setFont("OpenSauce", 8)
    y_position = 190

    y_position_offset = 0

    trm = str(data.get('trm', '')).strip()

    fields = [
        ("", "* Precios no incluyen IVA y están sujetos al mismo."),
        ("", "* Los pagos en dólares se realizan a la TRM del día del pago a la línea +2%."),
        ("", "* (El día de la facturación se coloca la TRM a la que se realiza el pago)."),
    ]


    raw_trm = data.get('trm', None)
    if raw_trm not in (None, "", "None"):
        fields.append(("", f"* TRM: ${str(raw_trm).strip()}"))

    y_position_offset = 0
    for label, value in fields:
        c.drawString(
            115,
            y_position - y_position_offset,
            f"{label + ': ' if label else ''}{value}"
        )
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

def generate_pdf(data, template_path="resources/archives/Solicitud Anticipo-2.pdf", output_path="resources/archives/Solicitud.pdf", overlay_path="overlay.pdf"):
    create_overlay(data, overlay_path)
    merge_pdfs(template_path, overlay_path, output_path)
    return output_path