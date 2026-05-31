# miPrimerRepo

## 📰 Agente de Noticias Diario

Un workflow de GitHub Actions que cada día obtiene las principales noticias de fuentes RSS, las resume y te envía un correo electrónico con el digest.

### ¿Cómo funciona?

1. **Scheduler** – El workflow corre automáticamente todos los días a las 08:00 UTC (puedes ajustar el horario en `.github/workflows/daily-news.yml`).
2. **Fetch** – El script `scripts/news_agent.py` descarga artículos de fuentes RSS (BBC Mundo, El País, CNN en Español por defecto).
3. **Resumen** – Toma el título y la descripción de cada artículo directamente del RSS.
4. **Email** – Envía un correo HTML bien formateado usando Gmail SMTP.

### Configuración de Secrets y Variables

Ve a **Settings → Secrets and variables → Actions** en tu repositorio y agrega:

| Nombre | Tipo | Descripción |
|---|---|---|
| `EMAIL_SENDER` | Secret | Dirección Gmail desde la que se envía (ej. `tucuenta@gmail.com`) |
| `EMAIL_PASSWORD` | Secret | [App Password de Gmail](https://support.google.com/accounts/answer/185833) (NO tu contraseña normal) |
| `EMAIL_RECIPIENT` | Secret | Dirección de correo que recibirá el digest |
| `NEWS_LANGUAGE` | Variable | `es` (español, default) o `en` (inglés) |
| `MAX_ARTICLES` | Variable | Número máximo de artículos por fuente (default `5`) |

> **Nota sobre la App Password de Gmail:** Activa la verificación en 2 pasos en tu cuenta Google, luego ve a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) y genera una contraseña de aplicación para usar como `EMAIL_PASSWORD`.

### Ejecución manual

Puedes lanzar el agente en cualquier momento desde **Actions → Daily News Digest → Run workflow**.

### Fuentes de noticias

**Español (`es`):**
- BBC Mundo
- El País
- CNN en Español

**Inglés (`en`):**
- BBC News
- Reuters
- AP News

Para agregar o cambiar fuentes, edita el diccionario `NEWS_SOURCES` en `scripts/news_agent.py`.
