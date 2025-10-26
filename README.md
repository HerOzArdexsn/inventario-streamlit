# inventario-streamlit

App de inventario en tiempo real con **Streamlit** + **Google Sheets**.

## 🚀 Despliegue rápido en Streamlit Cloud
1. Haz fork o sube estos archivos a tu repo.
2. Ve a https://share.streamlit.io → *New app* → elige `app.py`.
3. En **Settings → Secrets**, pega algo como:

```toml
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"

[inventory]
SHEET_ID = "TU_ID_DE_SHEET"
WORKSHEET = "Inventario"

[app]
BASE_URL = "https://tuusuario-inventario-streamlit.streamlit.app"  # opcional
```

> Comparte tu Google Sheet con el `client_email` del service account (rol **Editor**).

## ✨ Funciones
- Alta rápida de productos (Imagen, Descripción, Unidad, Cantidad, Ubicación)
- **ID Similar** para agrupar familias / SKUs
- Búsqueda y filtros
- **Edición en línea** con `st.data_editor`
- **Resumen por ID Similar** (totales + gráfico de barras)
- **Normalización** de ID Similar (mayúsc/minúsc + trim)
- **Control de duplicados** (Descripción + Ubicación)
- **Bloqueo de borrado** con filtros activos
- **QR por ID** (opcionalmente enlazado a `BASE_URL?id=...`)
- Exportación CSV

## 📦 Requisitos
```
streamlit
pandas
gspread
google-auth
```

¡Listo para usar desde PC o celular! 📱💻
