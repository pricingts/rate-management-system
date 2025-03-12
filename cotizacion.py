import xlwings as xw
import datetime
from auth import user_data
import streamlit as st

def generate_quotation(data):
    ruta_plantilla = "plantilla.xlsx"
    app = xw.App(visible=False) 
    wb = app.books.open(ruta_plantilla)
    hoja = wb.sheets["Hoja1"]

    def escribir_en_celda(celda, valor, bold=False):
        rng = hoja.range(celda)  
        if rng.merge_cells:
            rng = hoja.range(rng.merge_area.address)
        rng.value = valor

        try:
            if bold:
                rng.api.FontObject.Bold = True  # 🔹 Solución: Usar FontObject en lugar de Font
        except AttributeError:
            pass


    commercial_data = user_data()
    escribir_en_celda("F4", commercial_data.get("name", "N/A")) 
    escribir_en_celda("F5", commercial_data.get("position", "N/A"))  
    escribir_en_celda("F6", commercial_data.get("tel", "N/A"))  
    escribir_en_celda("F7", commercial_data.get("email", "N/A"))  

    escribir_en_celda("C10", datetime.datetime.today().strftime("%d/%m/%Y"))  
    escribir_en_celda("G10", (datetime.datetime.today() + datetime.timedelta(days=30)).strftime("%d/%m/%Y"))  

    escribir_en_celda("B13", data.get("client", "N/A"))  
    #escribir_en_celda("B16", data.get("reference", "N/A"))  preguntar por la referencia

    escribir_en_celda("C19", data.get("incoterm", "N/A"))  
    details = data.get("Details", {})
    escribir_en_celda("C20", details.get("Commodities", "N/A"))  
    escribir_en_celda("C22", ", ".join(data.get("cargo_type", [])))  

    escribir_en_celda("C21", f"{data.get('POL', 'N/A')} - {data.get('POD', 'N/A')}")  
    escribir_en_celda("C22", data.get("cargo_type", "N/A"))  

    rate_table = data.get("surcharges", {})
    fila_inicio = 25
    total_costos = {}

    for concepto, valores in rate_table.items():
        for container_type, amount in valores.items():
            if isinstance(amount, (int, float)) and amount > 0:
                hoja.range(f"B{fila_inicio}").value = concepto.upper()  
                hoja.range(f"D{fila_inicio}").value = container_type  
                hoja.range(f"F{fila_inicio}").value = amount  
                total_costos[container_type] = total_costos.get(container_type, 0) + amount  
                fila_inicio += 1  

    escribir_en_celda(f"B{fila_inicio}", "Total", bold=True)
    for idx, (container_type, total) in enumerate(total_costos.items()):
        escribir_en_celda(f"D{fila_inicio + idx}", container_type, bold=True)
        escribir_en_celda(f"F{fila_inicio + idx}", total, bold=True)


    # NOTAS
    transit_time_info = ( 
        f"Transit Time: {data.get("Details", {}).get("Transit Time", "N/A")} days \n"
        f"Route: {data.get("Details", {}).get("Route", "N/A")} \n"
        f"Free Days in Origin: {data.get("Details", {}).get("Free Days in Origin", "N/A")} \n"
        f"Free Days in Destination: {data.get("Details", {}).get("Free Days in Destination", "N/A")} \n"
        f"Notes: {data.get("Details", {}).get("Notes", " ")}"
    )

    escribir_en_celda("B33", transit_time_info)  
    hoja.range("B33").api.WrapText = True

    output = BytesIO()
    temp_file = os.path.expanduser("~/Documents/forms upgraded/cotizacion_temp.xlsx")

    try:
        wb.save(temp_file) 
        wb.close()
        app.quit()

        with open(temp_file, "rb") as f:
            output.write(f.read())

        output.seek(0) 

    except Exception as e:
        print(f"Error al guardar el archivo: {e}")
        wb.close()
        app.quit()
        return None

    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    return output
