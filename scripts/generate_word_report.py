import os
from datetime import datetime
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def create_report():
    doc = docx.Document()

    # Configuración de márgenes estándar (2.0 cm)
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Colores institucionales
    NAVY = RGBColor(26, 54, 93)      # #1A365D - Primario
    BLUE = RGBColor(43, 108, 176)    # #2B6CB0 - Secundario
    DARK = RGBColor(45, 55, 72)      # #2D3748 - Texto
    GRAY = RGBColor(113, 128, 150)   # #718096 - Texto secundario
    GREEN = RGBColor(39, 103, 73)    # #276749 - Aprobado
    RED = RGBColor(155, 44, 44)      # #9B2C2C - Fallido

    # Helpers XML para estilo de tablas y celdas
    def set_cell_bg(cell, fill_hex):
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
        cell._tc.get_or_add_tcPr().append(shading)

    def set_cell_margins(cell, top=120, bottom=120, left=160, right=160):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = parse_xml(
            f'<w:tcMar {nsdecls("w")}>'
            f'<w:top w:w="{top}" w:type="dxa"/>'
            f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
            f'<w:left w:w="{left}" w:type="dxa"/>'
            f'<w:right w:w="{right}" w:type="dxa"/>'
            f'</w:tcMar>'
        )
        tcPr.append(tcMar)

    def set_table_borders(table, color="CBD5E0", sz="4", val="single"):
        tblPr = table._tbl.tblPr
        borders = parse_xml(
            f'<w:tblBorders {nsdecls("w")}>'
            f'<w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
            f'<w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
            f'<w:left w:val="none"/>'
            f'<w:right w:val="none"/>'
            f'<w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
            f'<w:insideV w:val="none"/>'
            f'</w:tblBorders>'
        )
        tblPr.append(borders)

    # =========================================================================
    # 1. ENCABEZADO / PORTADA
    # =========================================================================
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_inst = p_inst.add_run("INACAP | DEPARTAMENTO DE INGENIERÍA DE SOFTWARE\nEVALUACIÓN 3 — QA AUTOMATION")
    r_inst.font.name = "Arial"
    r_inst.font.size = Pt(8.5)
    r_inst.font.bold = True
    r_inst.font.color.rgb = GRAY

    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(14)
    p_title.paragraph_format.space_after = Pt(4)
    r_title = p_title.add_run("INFORME DE EJECUCIÓN DE PRUEBAS DE API")
    r_title.font.name = "Arial"
    r_title.font.size = Pt(22)
    r_title.font.bold = True
    r_title.font.color.rgb = NAVY

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_after = Pt(14)
    r_sub = p_sub.add_run("Validación Automatizada de Casos Críticos en Entorno Staging | FastAPI & PostgreSQL")
    r_sub.font.name = "Arial"
    r_sub.font.size = Pt(12)
    r_sub.font.italic = True
    r_sub.font.color.rgb = BLUE

    # Tabla de Ficha Técnica / Metadatos
    meta_table = doc.add_table(rows=4, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_table.autofit = False

    meta_data = [
        ("Sistema Bajo Prueba (SUT):", "Sistema de Reserva de Salas Académicas (API RESTful)"),
        ("Entorno y Arquitectura:", "Staging (Localhost:8000) | FastAPI 0.115, PostgreSQL 18, SQLAlchemy 2.0"),
        ("Framework y Herramientas:", "Python 3.12.10 | Pytest 9.1.1 | Requests 2.34 | AnyIO 4.15"),
        ("Fecha de Ejecución y Rol:", f"{datetime.now().strftime('%d/%m/%Y %H:%M')} | QA Automation Engineer")
    ]

    for i, (k, v) in enumerate(meta_data):
        row = meta_table.rows[i]
        c0, c1 = row.cells[0], row.cells[1]
        c0.width = Inches(2.2)
        c1.width = Inches(4.7)
        set_cell_bg(c0, "EDF2F7")
        set_cell_bg(c1, "F7FAFC")
        set_cell_margins(c0, top=80, bottom=80, left=120, right=120)
        set_cell_margins(c1, top=80, bottom=80, left=120, right=120)

        p0 = c0.paragraphs[0]
        r0 = p0.add_run(k)
        r0.font.name = "Arial"
        r0.font.size = Pt(9)
        r0.font.bold = True
        r0.font.color.rgb = NAVY

        p1 = c1.paragraphs[0]
        r1 = p1.add_run(v)
        r1.font.name = "Arial"
        r1.font.size = Pt(9)
        r1.font.color.rgb = DARK

    set_table_borders(meta_table, color="CBD5E0", sz="4")

    # Separador
    p_sep = doc.add_paragraph()
    p_sep.paragraph_format.space_before = Pt(8)
    p_sep.paragraph_format.space_after = Pt(8)

    # =========================================================================
    # 2. RESUMEN EJECUTIVO
    # =========================================================================
    h1 = doc.add_heading("1. Resumen Ejecutivo de la Suite de Pruebas", level=1)
    h1.paragraph_format.space_before = Pt(12)
    h1.paragraph_format.space_after = Pt(6)
    h1.runs[0].font.name = "Arial"
    h1.runs[0].font.color.rgb = NAVY

    p_desc = doc.add_paragraph(
        "Se ejecutó la suite automatizada de pruebas de integración y seguridad orientada a endpoints críticos "
        "del Sistema de Reserva de Salas. La batería comprende autenticación JWT, control de accesos basado en roles (RBAC), "
        "control de concurrencia mediante bloqueos a nivel de fila (Row-Level Locks), prevención de inyecciones SQL "
        "y validación de vulnerabilidades de asignación indebida de recursos (IDOR)."
    )
    p_desc.runs[0].font.name = "Arial"
    p_desc.runs[0].font.size = Pt(10)
    p_desc.runs[0].font.color.rgb = DARK

    # Tabla de Métricas
    metrics_table = doc.add_table(rows=5, cols=3)
    metrics_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(metrics_table, color="CBD5E0", sz="4")

    headers_m = ["Métrica de Calidad", "Cantidad", "Porcentaje"]
    hdr_row = metrics_table.rows[0]
    for j, h in enumerate(headers_m):
        cell = hdr_row.cells[j]
        set_cell_bg(cell, "1A365D")
        set_cell_margins(cell, top=100, bottom=100, left=140, right=140)
        p = cell.paragraphs[0]
        if j > 0:
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = p.add_run(h)
        r.font.name = "Arial"
        r.font.size = Pt(9.5)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)

    data_m = [
        ("Casos de Prueba Planificados y Ejecutados", "8", "100.0%"),
        ("Casos Aprobados (PASSED)", "5", "62.5%"),
        ("Casos Fallidos (FAILED)", "3", "37.5%"),
        ("Defectos Críticos / Mayores Detectados (Bugs)", "3", "N/A"),
    ]

    for i, (m, c, pct) in enumerate(data_m, start=1):
        row = metrics_table.rows[i]
        bg = "FFFFFF" if i % 2 != 0 else "F7FAFC"
        for j, val in enumerate([m, c, pct]):
            cell = row.cells[j]
            set_cell_bg(cell, bg)
            set_cell_margins(cell, top=80, bottom=80, left=140, right=140)
            p = cell.paragraphs[0]
            if j > 0:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            r = p.add_run(val)
            r.font.name = "Arial"
            r.font.size = Pt(9)
            if "Aprobados" in m:
                r.font.bold = True
                r.font.color.rgb = GREEN
            elif "Fallidos" in m or "Defectos" in m:
                r.font.bold = True
                r.font.color.rgb = RED
            else:
                r.font.color.rgb = DARK

    # =========================================================================
    # 3. MATRIZ DETALLADA DE RESULTADOS POR CASO DE PRUEBA
    # =========================================================================
    h2 = doc.add_heading("2. Matriz de Ejecución Detallada por Caso de Prueba", level=1)
    h2.paragraph_format.space_before = Pt(16)
    h2.paragraph_format.space_after = Pt(6)
    h2.runs[0].font.name = "Arial"
    h2.runs[0].font.color.rgb = NAVY

    results_table = doc.add_table(rows=9, cols=6)
    results_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(results_table, color="CBD5E0", sz="4")

    headers_r = ["ID", "Descripción del Caso", "Endpoint / Método", "HTTP Esp.", "HTTP Obt.", "Resultado"]
    col_widths = [Inches(0.7), Inches(2.3), Inches(1.8), Inches(0.7), Inches(0.7), Inches(0.8)]

    hdr_r = results_table.rows[0]
    for j, h in enumerate(headers_r):
        cell = hdr_r.cells[j]
        cell.width = col_widths[j]
        set_cell_bg(cell, "1A365D")
        set_cell_margins(cell, top=100, bottom=100, left=100, right=100)
        p = cell.paragraphs[0]
        if j in [0, 3, 4, 5]:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.font.name = "Arial"
        r.font.size = Pt(8.5)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)

    matrix_data = [
        ("CP-05", "Login exitoso con credenciales válidas y verificación de token JWT", "POST /api/auth/login", "200", "200", "PASSED"),
        ("CP-06", "Login con contraseña errónea para usuario existente", "POST /api/auth/login", "401", "200", "FAILED"),
        ("CP-08", "Acceso a consulta administrativa por parte de rol ALUMNO", "GET /api/usuarios/{id}", "403", "403", "PASSED"),
        ("CP-09", "Eliminación de reserva mediante método DELETE por su titular", "DELETE /api/reservas/{id}", "200", "405", "FAILED"),
        ("CP-13", "Intento de reserva solapada (10:00-11:00 vs 10:30-11:30)", "POST /api/reservas/", "409", "409", "PASSED"),
        ("CP-10", "Inyección SQL en campos (' OR '1'='1) con control de excepciones", "POST /api/reservas/", "422", "422", "PASSED"),
        ("CP-50", "Inyección IDOR de usuario_id ajeno en payload JSON de reserva", "POST /api/reservas/", "201", "201", "PASSED"),
        ("CP-46", "Flujo secuencial: Login -> Disponibilidad -> Reserva -> Delete", "Varios / E2E", "200", "404", "FAILED")
    ]

    for i, row_data in enumerate(matrix_data, start=1):
        row = results_table.rows[i]
        bg = "FFFFFF" if i % 2 != 0 else "F7FAFC"
        is_passed = row_data[5] == "PASSED"

        for j, val in enumerate(row_data):
            cell = row.cells[j]
            cell.width = col_widths[j]
            set_cell_bg(cell, bg)
            set_cell_margins(cell, top=70, bottom=70, left=90, right=90)
            p = cell.paragraphs[0]
            if j in [0, 3, 4, 5]:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(val)
            r.font.name = "Arial"
            r.font.size = Pt(8.5)

            if j == 0:
                r.font.bold = True
                r.font.color.rgb = NAVY
            elif j == 5:
                r.font.bold = True
                if is_passed:
                    r.font.color.rgb = GREEN
                else:
                    r.font.color.rgb = RED
            elif j == 4 and not is_passed:
                r.font.bold = True
                r.font.color.rgb = RED
            else:
                r.font.color.rgb = DARK

    # =========================================================================
    # 4. FICHAS TÉCNICAS DE DEFECTOS (BUG REPORTS)
    # =========================================================================
    h3 = doc.add_heading("3. Registro de Defectos Detectados (Bug Reports)", level=1)
    h3.paragraph_format.space_before = Pt(16)
    h3.paragraph_format.space_after = Pt(6)
    h3.runs[0].font.name = "Arial"
    h3.runs[0].font.color.rgb = NAVY

    bugs = [
        {
            "id": "BUG-01",
            "caso": "CP-06",
            "titulo": "Bypass de Autenticación por Falta de Validación Criptográfica de Contraseñas",
            "severidad": "CRÍTICA (Seguridad)",
            "modulo": "app/routers/auth.py & app/models/models.py",
            "esperado": "HTTP 401 Unauthorized cuando se proporciona una contraseña incorrecta.",
            "observado": "HTTP 200 OK con emisión de un token JWT funcional para cualquier contraseña ingresada.",
            "causa": "En 'models.py', el modelo 'Usuario' no define la columna 'password_hash'. En 'auth.py', la sentencia 'if hasattr(usuario, \"password_hash\") and usuario.password_hash:' evalúa a False, provocando que el backend asuma credencial válida y genere el JWT.",
            "impacto": "Cualquier atacante que conozca el correo institucional de un alumno o docente puede autenticarse sin ingresar la contraseña correcta."
        },
        {
            "id": "BUG-02",
            "caso": "CP-09",
            "titulo": "Verbo HTTP DELETE No Implementado en Endpoint de Reservas",
            "severidad": "ALTA (Funcional / Estándar REST)",
            "modulo": "app/routers/reservas.py",
            "esperado": "HTTP 200 OK al ejecutar DELETE /api/reservas/{id} por parte del titular.",
            "observado": "HTTP 405 Method Not Allowed.",
            "causa": "El router de reservas únicamente expone 'PATCH /api/reservas/{id}' con carga { 'estado': 'Cancelada' }, sin registrar el método DELETE para el recurso.",
            "impacto": "Incompatibilidad con clientes REST y pruebas automatizadas que requieren la eliminación directa de recursos."
        },
        {
            "id": "BUG-03",
            "caso": "CP-46",
            "titulo": "Inexistencia de Endpoint Dedicado de Consulta de Disponibilidad (/api/disponibilidad)",
            "severidad": "MEDIA (Funcional)",
            "modulo": "app/routers/reservas.py / app/main.py",
            "esperado": "HTTP 200 OK con el listado de bloques y salas disponibles ante GET /api/disponibilidad.",
            "observado": "HTTP 404 Not Found.",
            "causa": "La lógica de consulta se diseñó originalmente a través del listado con filtros 'GET /api/reservas/?sala_id={id}&fecha={fecha}'. El endpoint unificado '/api/disponibilidad' no fue registrado en el enrutador.",
            "impacto": "Interrupción de flujos de integración y experiencia de cliente orientados a la búsqueda inmediata de disponibilidad."
        }
    ]

    for bug in bugs:
        p_b = doc.add_paragraph()
        p_b.paragraph_format.space_before = Pt(8)
        p_b.paragraph_format.space_after = Pt(2)
        r_bid = p_b.add_run(f"[{bug['id']} | {bug['caso']}] {bug['titulo']}")
        r_bid.font.name = "Arial"
        r_bid.font.size = Pt(11)
        r_bid.font.bold = True
        r_bid.font.color.rgb = RED if "CRÍTICA" in bug["severidad"] else BLUE

        b_tbl = doc.add_table(rows=6, cols=2)
        b_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        set_table_borders(b_tbl, color="E2E8F0", sz="4")

        b_items = [
            ("Severidad / Impacto:", bug["severidad"]),
            ("Módulo Afectado:", bug["modulo"]),
            ("Comportamiento Esperado:", bug["esperado"]),
            ("Comportamiento Observado:", bug["observado"]),
            ("Causa Raíz en Código:", bug["causa"]),
            ("Impacto Operativo:", bug["impacto"])
        ]

        for bi, (bk, bv) in enumerate(b_items):
            brow = b_tbl.rows[bi]
            bc0, bc1 = brow.cells[0], brow.cells[1]
            bc0.width = Inches(2.2)
            bc1.width = Inches(4.7)
            set_cell_bg(bc0, "F7FAFC")
            set_cell_bg(bc1, "FFFFFF")
            set_cell_margins(bc0, top=60, bottom=60, left=100, right=100)
            set_cell_margins(bc1, top=60, bottom=60, left=100, right=100)

            bp0 = bc0.paragraphs[0]
            br0 = bp0.add_run(bk)
            br0.font.name = "Arial"
            br0.font.size = Pt(8.5)
            br0.font.bold = True
            br0.font.color.rgb = NAVY

            bp1 = bc1.paragraphs[0]
            br1 = bp1.add_run(bv)
            br1.font.name = "Arial"
            br1.font.size = Pt(8.5)
            if "CRÍTICA" in bv:
                br1.font.bold = True
                br1.font.color.rgb = RED
            elif "ALTA" in bv:
                br1.font.bold = True
                br1.font.color.rgb = RGBColor(197, 48, 48)
            else:
                br1.font.color.rgb = DARK

    # =========================================================================
    # 5. EVIDENCIA DE EJECUCIÓN (TERMINAL PYTEST)
    # =========================================================================
    h4 = doc.add_heading("4. Evidencia Técnica de Ejecución (Consola Pytest)", level=1)
    h4.paragraph_format.space_before = Pt(16)
    h4.paragraph_format.space_after = Pt(6)
    h4.runs[0].font.name = "Arial"
    h4.runs[0].font.color.rgb = NAVY

    log_box = doc.add_table(rows=1, cols=1)
    log_box.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_log = log_box.rows[0].cells[0]
    c_log.width = Inches(6.9)
    set_cell_bg(c_log, "2D3748")
    set_cell_margins(c_log, top=100, bottom=100, left=140, right=140)

    log_text = (
        "============================= test session starts =============================\n"
        "platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0\n"
        "rootdir: C:\\Users\\Usuario\\OneDrive - INACAP\\...\\Reserva_de_salas_ver0\n"
        "plugins: anyio-4.15.1\n"
        "collected 8 items\n\n"
        "tests/test_api_reservas.py::test_cp05_login_credenciales_validas PASSED  [ 12%]\n"
        "tests/test_api_reservas.py::test_cp06_login_password_incorrecto FAILED   [ 25%]\n"
        "tests/test_api_reservas.py::test_cp08_endpoint_administrativo_rol_alumno PASSED [ 37%]\n"
        "tests/test_api_reservas.py::test_cp09_delete_reserva_titular FAILED      [ 50%]\n"
        "tests/test_api_reservas.py::test_cp13_solapamiento_horario_conflicto PASSED [ 62%]\n"
        "tests/test_api_reservas.py::test_cp10_inyeccion_sql_campos_reserva PASSED [ 75%]\n"
        "tests/test_api_reservas.py::test_cp50_inyeccion_usuario_id_en_reserva PASSED [ 87%]\n"
        "tests/test_api_reservas.py::test_cp46_flujo_secuencial_e2e FAILED        [100%]\n\n"
        "================================== FAILURES ===================================\n"
        "FAILED tests/test_api_reservas.py::test_cp06_login_password_incorrecto\n"
        "E   AssertionError: Se esperaba HTTP 401 Unauthorized pero se obtuvo 200\n\n"
        "FAILED tests/test_api_reservas.py::test_cp09_delete_reserva_titular\n"
        "E   AssertionError: Se esperaba HTTP 200 pero se obtuvo 405 (Method Not Allowed)\n\n"
        "FAILED tests/test_api_reservas.py::test_cp46_flujo_secuencial_e2e\n"
        "E   AssertionError: Endpoint /api/disponibilidad fallo o no existe: HTTP 404\n\n"
        "========================= 3 failed, 5 passed in 0.27s ========================="
    )

    p_log = c_log.paragraphs[0]
    r_log = p_log.add_run(log_text)
    r_log.font.name = "Consolas"
    r_log.font.size = Pt(7.5)
    r_log.font.color.rgb = RGBColor(226, 232, 240)

    # =========================================================================
    # 6. RECOMENDACIONES DE REMEDIACIÓN
    # =========================================================================
    h5 = doc.add_heading("5. Plan de Remediación y Recomendaciones Técnicas", level=1)
    h5.paragraph_format.space_before = Pt(16)
    h5.paragraph_format.space_after = Pt(6)
    h5.runs[0].font.name = "Arial"
    h5.runs[0].font.color.rgb = NAVY

    recs = [
        ("1. Corrección Crítica en Autenticación:",
         "Añadir la columna 'password_hash = mapped_column(String(255), nullable=True)' al modelo 'Usuario' en 'app/models/models.py'. En 'app/routers/auth.py', rechazar con HTTP 401 si el usuario no tiene hash configurado o si no coincide con 'pwd_context.verify(form_data.password, usuario.password_hash)'."),
        ("2. Soporte Estándar para DELETE en Reservas:",
         "Implementar el controlador '@router.delete(\"/{reserva_id}\")' en 'app/routers/reservas.py', validando la identidad del titular o roles ADMIN/ENCARGADO, procediendo a cancelar la reserva o realizar soft-delete con retorno HTTP 200."),
        ("3. Publicación del Endpoint de Disponibilidad:",
         "Crear el endpoint '@router.get(\"/disponibilidad\")' en el router correspondiente que reciba 'id_sala' y 'fecha', consultando de forma ágil los bloques libres para optimizar las consultas de la aplicación cliente SPA.")
    ]

    for title_r, desc_r in recs:
        p_r = doc.add_paragraph()
        p_r.paragraph_format.space_before = Pt(4)
        p_r.paragraph_format.space_after = Pt(4)
        rt = p_r.add_run(f"{title_r} ")
        rt.font.name = "Arial"
        rt.font.size = Pt(9.5)
        rt.font.bold = True
        rt.font.color.rgb = NAVY

        rd = p_r.add_run(desc_r)
        rd.font.name = "Arial"
        rd.font.size = Pt(9.5)
        rd.font.color.rgb = DARK

    # Guardar documento
    output_path = os.path.abspath("Informe_Ejecucion_Pruebas_QA_ReservaSalas.docx")
    doc.save(output_path)
    print(f"Documento generado exitosamente en: {output_path}")

if __name__ == "__main__":
    create_report()
