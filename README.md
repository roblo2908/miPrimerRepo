# miPrimerRepo

## 📰 Agente de Noticias Diario

Un workflow de GitHub Actions que cada día obtiene noticias desde RSS, las filtra por temas prioritarios y te envía un correo electrónico con el digest.

### ¿Cómo funciona?

1. **Scheduler** – El workflow corre automáticamente todos los días a las **6:30 AM hora de Costa Rica** (`12:30 UTC`). Puedes ajustar el horario en `.github/workflows/daily-news.yml`.
2. **Fetch** – El script `scripts/news_agent.py` descarga artículos de fuentes RSS de **Costa Rica** y del **resto del mundo**.
3. **Filtrado y prioridad** – Solo incluye noticias de **Tecnología**, **Ciencia** y **Política**, en ese orden de importancia.
4. **Email** – Envía un correo HTML bien formateado usando Gmail SMTP.

### Orden del digest

El correo se organiza así:

1. **Costa Rica**
2. **Resto del mundo**

Y dentro de cada región, las noticias se muestran en este orden:

1. **Tecnología**
2. **Ciencia**
3. **Política**

### Configuración de Secrets y Variables

Ve a **Settings → Secrets and variables → Actions** en tu repositorio y agrega:

| Nombre | Tipo | Descripción |
|---|---|---|
| `EMAIL_SENDER` | Secret | Dirección Gmail desde la que se envía (ej. `tucuenta@gmail.com`) |
| `EMAIL_PASSWORD` | Secret | [App Password de Gmail](https://support.google.com/accounts/answer/185833) (NO tu contraseña normal) |
| `EMAIL_RECIPIENT` | Secret | Dirección de correo que recibirá el digest |
| `NEWS_LANGUAGE` | Variable | `es` (español, default) o `en` (inglés) |
| `MAX_ARTICLES` | Variable | Cantidad máxima de artículos a inspeccionar por fuente antes de filtrar (default `20`) |
| `MAX_TECHNOLOGY` | Variable | Máximo de noticias de Tecnología por región (default `10`) |
| `MAX_SCIENCE` | Variable | Máximo de noticias de Ciencia por región (default `6`) |
| `MAX_POLITICS` | Variable | Máximo de noticias de Política por región (default `4`) |

> **Nota sobre la App Password de Gmail:** Activa la verificación en 2 pasos en tu cuenta Google, luego ve a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) y genera una contraseña de aplicación para usar como `EMAIL_PASSWORD`.

### Ejecución manual

Puedes lanzar el agente en cualquier momento desde **Actions → Daily News Digest → Run workflow**.

### Fuentes de noticias

**Español (`es`)**

**Costa Rica:**
- Delfino.cr
- Despertar.cr
- Diario Extra

**Resto del mundo:**
- BBC Mundo
- El País
- CNN en Español

**Inglés (`en`)**

**Resto del mundo:**
- BBC News
- Reuters
- AP News

Para agregar o cambiar fuentes, edita el diccionario `NEWS_SOURCES` en `scripts/news_agent.py`.
