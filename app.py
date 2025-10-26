import streamlit as st
import pandas as pd
from typing import Optional

# --- Opcional: Google Sheets backend ---
# Para usarlo, agrega a .streamlit/secrets.toml:
# [gcp_service_account]
# type = "service_account"
# project_id = "..."
# private_key_id = "..."
# private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
# client_email = "...@...gserviceaccount.com"
# client_id = "..."
# auth_uri = "https://accounts.google.com/o/oauth2/auth"
# token_uri = "https://oauth2.googleapis.com/token"
# auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
# client_x509_cert_url = "..."
# universe_domain = "googleapis.com"
#
# [inventory]
# SHEET_ID = "<TU_GOOGLE_SHEET_ID>"
# WORKSHEET = "Inventario"
#
# [app]
# BASE_URL = "https://tuusuario-inventario-streamlit.streamlit.app"  # opcional: para que los QRs apunten a tu app pública

st.set_page_config(page_title="Inventario en tiempo real", page_icon="📦", layout="wide")

APP_COLUMNS = [
    "ID",
    "ID Similar",
    "Imagen",
    "Descripción",
    "Unidad",
    "Cantidad",
    "Ubicación Física",
]

@st.cache_data(show_spinner=False)
def _connect_gsheets():
    """Devuelve worksheet si hay Secrets válidos; si no, None (modo CSV local)."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        info = st.secrets["gcp_service_account"]
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        sheet_id = st.secrets["inventory"]["SHEET_ID"]
        sh = client.open_by_key(sheet_id)
        ws_name = st.secrets["inventory"].get("WORKSHEET", "Inventario")
        try:
            ws = sh.worksheet(ws_name)
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title=ws_name, rows=100, cols=len(APP_COLUMNS))
            ws.append_row(APP_COLUMNS)
        return ws
    except Exception:
        return None

def _read_from_gsheets(ws) -> pd.DataFrame:
    try:
        raw = ws.get_all_records()
        df = pd.DataFrame(raw)
        if df.empty:
            df = pd.DataFrame(columns=APP_COLUMNS)
        for col in APP_COLUMNS:
            if col not in df.columns:
                df[col] = []
        df = df[APP_COLUMNS]
        if not df.empty:
            df["Cantidad"] = pd.to_numeric(df["Cantidad"], errors="coerce").fillna(0).astype(int)
            df["ID"] = df["ID"].astype(str)
        return df
    except Exception as e:
        st.warning(f"No se pudo leer Google Sheets: {e}")
        return pd.DataFrame(columns=APP_COLUMNS)

def _write_to_gsheets(ws, df: pd.DataFrame):
    try:
        ws.clear()
        ws.append_row(APP_COLUMNS)
        values = df.fillna("").astype(str).values.tolist()
        if values:
            ws.append_rows(values)
    except Exception as e:
        st.error(f"No se pudo escribir en Google Sheets: {e}")

@st.cache_data(show_spinner=False)
def _load_local() -> pd.DataFrame:
    try:
        df = pd.read_csv("inventario.csv")
        for col in APP_COLUMNS:
            if col not in df.columns:
                df[col] = []
        df = df[APP_COLUMNS]
        if not df.empty:
            df["Cantidad"] = pd.to_numeric(df["Cantidad"], errors="coerce").fillna(0).astype(int)
            df["ID"] = df["ID"].astype(str)
        return df
    except FileNotFoundError:
        return pd.DataFrame(columns=APP_COLUMNS)

def _save_local(df: pd.DataFrame):
    df.to_csv("inventario.csv", index=False)

# --- Backend selector (GSheets si está configurado; si no, CSV local) ---
ws = _connect_gsheets()
BACKEND = "Google Sheets" if ws is not None else "Archivo CSV local"

def load_data() -> pd.DataFrame:
    if ws is not None:
        return _read_from_gsheets(ws)
    return _load_local()

def save_data(df: pd.DataFrame):
    if ws is not None:
        _write_to_gsheets(ws, df)
    else:
        _save_local(df)

# --- Utilidades ---
def _new_id(df: pd.DataFrame) -> str:
    # ID incremental simple (I-0001)
    if df.empty:
        return "I-0001"
    try:
        nums = (
            df["ID"].str.extract(r"I-(\d+)")[0].dropna().astype(int).tolist()
            if "ID" in df.columns else []
        )
        nxt = (max(nums) + 1) if nums else 1
        return f"I-{nxt:04d}"
    except Exception:
        return f"I-{len(df)+1:04d}"

def _normalize_idsim(val: Optional[str], norm_case: str, strip_spaces: bool) -> str:
    if val is None:
        return ""
    s = str(val)
    if strip_spaces:
        s = s.strip()
    if norm_case == "Mayúsculas":
        s = s.upper()
    elif norm_case == "Minúsculas":
        s = s.lower()
    return s

def _norm_text(s: Optional[str]) -> str:
    if s is None:
        return ""
    return str(s).strip().lower()

def _has_dup_desc_ubic(df: pd.DataFrame) -> bool:
    if df.empty:
        return False
    tmp = df.copy()
    tmp["_desc"] = tmp["Descripción"].apply(_norm_text)
    tmp["_ubi"] = tmp["Ubicación Física"].apply(_norm_text)
    return tmp.duplicated(["_desc", "_ubi"], keep=False).any()

# --- Sidebar ---
st.sidebar.header("⚙️ Configuración")
st.sidebar.markdown(
    f"**Backend:** {BACKEND} " + ("(colaboración en tiempo casi real)" if ws is not None else "(modo local)")
)
refresh_secs = st.sidebar.slider("Auto-actualizar cada (seg)", 0, 30, 5, help="0 desactiva el auto-refresh")
if refresh_secs > 0:
    st.sidebar.caption("El auto-refresh vuelve a leer el backend para ver cambios de otros usuarios.")

# Normalización de ID Similar
st.sidebar.subheader("🧹 Normalización de 'ID Similar'")
norm_case = st.sidebar.selectbox("Formato de texto", ["Sin cambio", "Mayúsculas", "Minúsculas"], index=0, help="Estandariza el ID para evitar duplicados por may/min")
strip_spaces = st.sidebar.checkbox("Quitar espacios al principio/fin", value=True)

# Protección contra borrado con filtros activos
st.sidebar.subheader("🛡️ Seguridad de borrado")
allow_delete_filtered = st.sidebar.checkbox(
    "Permitir borrar filas cuando hay filtros activos",
    value=False,
    help="Recomendado: dejar desactivado para evitar eliminar por error al estar filtrando.",
)

if st.sidebar.button("🔄 Forzar recarga ahora"):
    st.cache_data.clear()

# --- Título ---
st.title("📦 Inventario en tiempo real")
st.caption("ID Similar • Imagen • Descripción • Unidad • Cantidad • Ubicación Física")

# Auto-refresh
if refresh_secs > 0:
    # Usa el componente oficial `streamlit-autorefresh` si está disponible
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=refresh_secs * 1000, key="auto_refresh")
except Exception:
    st.caption("Autorefresh no disponible: instala 'streamlit-autorefresh' o ajusta el slider a 0.")

# --- Cargar datos ---
df = load_data().copy()
if df.empty:
    df = pd.DataFrame(columns=APP_COLUMNS)

# Opciones existentes para ID Similar (autocompletado)
existing_idsim = sorted([v for v in df.get("ID Similar", pd.Series(dtype=str)).dropna().unique().tolist() if str(v).strip() != ""])
idsim_options = ["(sin ID)"] + existing_idsim + ["Nuevo…"]

# --- Filtros ---
# Prefill desde parámetro de URL (?id=I-0001)
try:
    params = st.query_params
except Exception:
    params = st.experimental_get_query_params()
initial_q = ""
if params:
    if isinstance(params, dict):
        initial_q = params.get("id", "") if isinstance(params.get("id", ""), str) else (params.get("id", [""]) or [""])[0]

with st.expander("🔍 Filtros", expanded=False):
    colf1, colf2 = st.columns([2,1])
    with colf1:
        q = st.text_input("Buscar por texto (Descripción / Ubicación / ID)", value=initial_q)
    with colf2:
        ubicaciones = sorted([u for u in df["Ubicación Física"].dropna().unique().tolist() if u != ""]) if not df.empty else []
        ub_sel = st.multiselect("Ubicación Física", options=ubicaciones)

# Aplicar filtros en copia visual
view_df = df.copy()
if q:
    ql = q.lower()
    view_df = view_df[view_df.apply(lambda r: any(
        ql in str(r[c]).lower() for c in ["Descripción", "Ubicación Física", "ID", "ID Similar"]
    ), axis=1)]
if ub_sel:
    view_df = view_df[view_df["Ubicación Física"].isin(ub_sel)]

# --- Alta rápida ---
st.subheader("➕ Alta rápida")
with st.form("alta_form", clear_on_submit=True):
    c1, c2, c3, c4, c5, c6 = st.columns([2,3,1.2,1.2,2,1.6])
    with c1:
        imagen = st.text_input("URL de imagen", placeholder="https://...")
    with c2:
        descripcion = st.text_input("Descripción", placeholder="Shampoo hidratante 500ml")
    with c3:
        unidad = st.text_input("Unidad", placeholder="pz / caja / kg")
    with c4:
        cantidad = st.number_input("Cantidad", min_value=0, step=1, value=0)
    with c5:
        ubicacion = st.text_input("Ubicación Física", placeholder="Almacén A / Estante 3")
    with c6:
        sel = st.selectbox("ID Similar", options=idsim_options, index=0, help="Usa un ID existente para agrupar productos similares o crea uno nuevo")
        if sel == "Nuevo…":
            id_similar = st.text_input("Nuevo ID Similar", placeholder="Ej. SKU-123 o Familia-A")
        elif sel == "(sin ID)":
            id_similar = ""
        else:
            id_similar = sel
    submitted = st.form_submit_button("Agregar al inventario")
    if submitted:
        # Validación de duplicados antes de agregar
        probe = df.copy()
        probe = pd.concat([probe, pd.DataFrame([{ "ID":"tmp", "Imagen": imagen, "Descripción": descripcion, "Unidad": unidad, "Cantidad": int(cantidad), "Ubicación Física": ubicacion, "ID Similar": id_similar }])], ignore_index=True)
        if _has_dup_desc_ubic(probe):
            st.error("Ya existe un artículo con la misma **Descripción** y **Ubicación Física**. Ajusta alguno para evitar duplicados.")
        else:
            new_row = {
                "ID": _new_id(df),
                "ID Similar": _normalize_idsim(id_similar, norm_case, strip_spaces),
                "Imagen": imagen.strip(),
                "Descripción": descripcion.strip(),
                "Unidad": unidad.strip(),
                "Cantidad": int(cantidad),
                "Ubicación Física": ubicacion.strip(),
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_data(df)
            st.success(f"Artículo agregado: {new_row['ID']}")
            st.cache_data.clear()
            st.experimental_rerun()

# --- Editor de datos (edición en línea) ---
st.subheader("🗃️ Inventario")

col_config = {
    "Imagen": st.column_config.ImageColumn("Imagen", help="URL de imagen (https://...)"),
    "Descripción": st.column_config.TextColumn("Descripción"),
    "Unidad": st.column_config.TextColumn("Unidad"),
    "Cantidad": st.column_config.NumberColumn("Cantidad", min_value=0, step=1),
    "Ubicación Física": st.column_config.TextColumn("Ubicación Física"),
    # Mantengo TextColumn para permitir escribir valores nuevos libremente en el editor
    "ID Similar": st.column_config.TextColumn("ID Similar", help="Escribe o pega un ID existente (ver sugerencias arriba)"),
    "ID": st.column_config.TextColumn("ID", disabled=True),
}

edited = st.data_editor(
    view_df,
    column_config=col_config,
    use_container_width=True,
    num_rows="dynamic",
    height=480,
    key="editor",
)

# Determinar si hubo cambios en la vista y aplicarlos al DF original por ID
if not edited.equals(view_df):
    base = df.set_index("ID")
    ed = edited.set_index("ID")
    for idx in ed.index:
        if idx in base.index:
            # Aplicamos normalización
            updated_row = ed.loc[idx, ["Imagen", "Descripción", "Unidad", "Cantidad", "Ubicación Física", "ID Similar"]].copy()
            updated_row["ID Similar"] = _normalize_idsim(updated_row["ID Similar"], norm_case, strip_spaces)
            base.loc[idx, ["Imagen", "Descripción", "Unidad", "Cantidad", "Ubicación Física", "ID Similar"]] = updated_row

    # Detectar filas eliminadas desde la vista (protegido por configuración de filtros)
    can_delete = (not q and not ub_sel) or allow_delete_filtered
    if can_delete:
        ids_view = set(ed.index.tolist())
        ids_all = set(base.index.tolist())
        removed = ids_all - ids_view
        if removed:
            base = base.drop(list(removed))
            st.info(f"Se eliminaron {len(removed)} fila(s) desde la vista.")

    df = base.reset_index()
    # Normalización total
    if "ID Similar" in df.columns:
        df["ID Similar"] = df["ID Similar"].apply(lambda x: _normalize_idsim(x, norm_case, strip_spaces))
    # Validación de duplicados global antes de guardar
    if _has_dup_desc_ubic(df):
        st.error("Se detectaron **duplicados** (misma Descripción + Ubicación). No se guardaron los cambios.")
    else:
        save_data(df)
        st.success("Cambios guardados.")
        st.cache_data.clear()

# --- QRs por ID ---
st.subheader("🔗 QR por ID")
if df.empty:
    st.info("No hay datos para generar QRs.")
else:
    id_options = df["ID"].dropna().astype(str).tolist()
    sel_qr = st.selectbox("Selecciona un ID", options=id_options)
    # Si está configurado BASE_URL en secrets, el QR apunta a la URL pública con ?id=...
    base_url = None
    try:
        base_url = st.secrets.get("app", {}).get("BASE_URL")
    except Exception:
        base_url = None
    if base_url:
        if "?" in base_url:
            qr_payload = f"{base_url}&id={sel_qr}"
        else:
            qr_payload = f"{base_url}?id={sel_qr}"
    else:
        qr_payload = sel_qr  # fallback al ID puro

    st.write("Contenido del QR:")
    st.code(qr_payload, language="text")

    # Usamos Google Chart API (no requiere dependencias)
    import urllib.parse
    qr_url = f"https://chart.googleapis.com/chart?cht=qr&chs=220x220&chld=L|0&chl={urllib.parse.quote(qr_payload)}"
    st.image(qr_url, caption=f"QR del ID {sel_qr}")

# --- Resumen por ID Similar ---
st.subheader("📊 Resumen por ID Similar")
if df.empty:
    st.info("No hay datos aún para resumir.")
else:
    tmp = df.copy()
    # Asegurar normalización también en esta vista
    tmp["ID Similar"] = tmp["ID Similar"].apply(lambda x: _normalize_idsim(x, norm_case, strip_spaces))
    tmp["_key"] = tmp["ID Similar"].fillna("").replace("", "(sin ID)")
    resumen = tmp.groupby("_key", as_index=False).agg(
        Total_Cantidad=("Cantidad", "sum"),
        Num_Items=("ID", "count"),
    ).rename(columns={"_key": "ID Similar"}).sort_values(["ID Similar"]).reset_index(drop=True)

    colr1, colr2 = st.columns([2,1])
    with colr1:
        st.dataframe(resumen, use_container_width=True, hide_index=True)
    with colr2:
        # Selector para ver el detalle de un ID Similar específico
        sel_id = st.selectbox("Ver detalle de:", options=["Todos"] + resumen["ID Similar"].tolist())
        if sel_id != "Todos":
            det = tmp[tmp["ID Similar"].fillna("").replace("", "(sin ID)") == sel_id][["ID", "Imagen", "Descripción", "Unidad", "Cantidad", "Ubicación Física", "ID Similar"]]
            st.dataframe(det, use_container_width=True, hide_index=True, height=300)

    # Gráfico barras de stock por ID Similar
    st.markdown("**Gráfico:** Total de Cantidad por ID Similar")
    if len(resumen) > 0:
        top_n = st.slider("Mostrar top N grupos", min_value=3, max_value=min(25, len(resumen)), value=min(10, len(resumen)))
        chart_df = resumen.sort_values("Total_Cantidad", ascending=False).head(top_n).set_index("ID Similar")["Total_Cantidad"]
        st.bar_chart(chart_df)

    # Descarga del reporte
    rep_csv = resumen.to_csv(index=False).encode("utf-8")
    st.download_button("Descargar Resumen por ID Similar (CSV)", rep_csv, file_name="resumen_por_id_similar.csv", mime="text/csv")

# --- Bajar/Exportar ---
st.subheader("⬇️ Exportar / Respaldo")
exp_cols = st.multiselect("Columnas a exportar", options=APP_COLUMNS, default=APP_COLUMNS)
if st.button("Exportar CSV"):
    csv = df[exp_cols].to_csv(index=False).encode("utf-8")
    st.download_button("Descargar inventario.csv", csv, file_name="inventario.csv", mime="text/csv")

# --- Ayuda ---
with st.expander("ℹ️ Cómo activar Google Sheets (colaboración en tiempo real)", expanded=False):
    st.markdown(
        """
        1. Crea un Google Sheet y copia su **ID** (la parte entre `/d/` y `/edit`).
        2. Crea un **Service Account** en Google Cloud y descarga el JSON.
        3. Comparte el Sheet con el **client_email** del Service Account con rol *Editor*.
        4. Pega el contenido del JSON en `.streamlit/secrets.toml` bajo `[gcp_service_account]`.
        5. En el mismo archivo agrega:
           
           ```toml
           [inventory]
           SHEET_ID = "TU_ID"
           WORKSHEET = "Inventario"
           ```
        6. (Opcional) agrega `[app].BASE_URL` con la URL pública de tu app para que los QRs apunten a `?id=...`.
        7. Despliega en Streamlit Community Cloud y agrega los mismos *Secrets*.
        
        **Nota:** Si no configuras Sheets, la app usa un CSV local (`inventario.csv`).
        """
    )

st.caption("Hecho con ❤️ en Streamlit • Soporta edición en línea, filtros, resumen por ID Similar y exportación a CSV.")
