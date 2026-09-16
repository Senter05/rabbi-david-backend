# ✡️ RABBI DAVID (`rabbidavid.org`) — MEMORIA OPERATIVA Y RUNBOOK DE RESOLUCIÓN

Documento maestro para continuidad en cualquier sesión de trabajo, soporte y resolución inmediata de bugs.

## 1. Identidad y Enlaces de Producción
- **Dominio Público**: `https://rabbidavid.org` (Frontend Netlify, Site ID `bc5b9341-f486-4b5f-9b07-500d6c7362e9`).
- **Backend Render**: `https://rabbi-david-backend.onrender.com` (Repo: `https://github.com/Senter05/rabbi-david-backend.git`, rama `main`).
- **Directorio de Trabajo Local**: `C:\Users\srgm2\Documents\Codex\2026-09-15\estamos-en-un-proyecto-ambicioso-en\outputs\rabbi-david-antigravity`
- **Tono y Marca**: Sabiduría judía ancestral guiada por Rabbi David. CERO menciones de Inteligencia Artificial ("ayuda de Rabbi David"). "Operated by Senter Company LLC" reservado únicamente para términos y condiciones.

---

## 2. Precios y Estructura Comercial Oficial

### Test de Abundancia y Lectura Personalizada:
- **01. Apertura Gratuita (Free Preview)**: $0 USD (cubre ~40% de la lectura tras contestar el test).
- **02. The Complete Reading**: **$7 USD** (700 centavos). Nivel `'reading'`. Desbloquea las 4 perspectivas completas y descarga del PDF.
- **03. Your Own 14-Day Plan & Audio**: **$27 USD** (2700 centavos). Nivel `'personal'`. Incluye lectura completa, PDF del plan de 14 días y narración de audio personalizada con voz autorizada de Rabbi David.
- **Upgrade de Lectura a Plan Personal**: **$20 USD** (2000 centavos, $27 en total).

### Política de Reembolso:
- **Test / Lectura / Plan / Audio**: Estrictamente **NO REEMBOLSABLES** (servicio personalizado digital, pago único sin suscripción).
- **E-books**: Reembolsables bajo condiciones de soporte.

### E-Books Individuales y Bundle (Stripe):
- *The Rabbi's Morning Wealth Blessing*: **$27 USD** (`https://buy.stripe.com/6oU00lacucqC3KOdWrawo0l`)
- *The 7 Jewish Money Rituals*: **$32 USD** (`https://buy.stripe.com/cNieVf3O6bmyftwdWrawo0h`)
- *Generational Wealth: The Torah Method*: **$77 USD** (`https://buy.stripe.com/eVq5kF3O6gGS5SW9Gbawo0i`)
- *The Complete Rabbi's Wealth System (4-Ebook Bundle)*: **$150 USD** (`https://buy.stripe.com/28E7sNfwOduGbdg9Gbawo0j`)

---

## 3. Arquitectura del Backend y Servicios

- **Motor Backend (`server.py`)**: `ThreadingHTTPServer` Python nativo con SQLite (`data/state.sqlite`).
- **Modelo IA (Generación de Texto)**: OpenRouter `~deepseek/deepseek-flash-latest` (con fallback local/ling-3.0).
- **Motor de Voz (Audio)**: FishAudio / AI33 (`fishaudio_7d805071401d4b738334f332a8c320c2`). Dispara automáticamente con la compra de `personal` plan (`start_voice`).
- **Audio de Bienvenida (17s)**: Eliminado permanentemente (`intro_job` es no-op) para no desperdiciar cuotas de FishAudio.
- **Base de Datos Persistente**: Supabase (`https://gkihlvkdkciqpkrhbunv.supabase.co`). Sincroniza tablas `users`, `sessions`, `orders` y bucket `user-assets` para archivos de audio y PDF.
- **Email**: Resend SMTP (`smtp.resend.com:587`, usuario `resend`, clave `re_jfs6ZfzS...`) desde `Rabbi David <delivery@rabbidavid.org>`.
- **Stripe**:
  - Clave restringida Live: Integrada vía base64 en `server.py` (`config.setdefault('stripe_secret_key', ...)`).
  - Webhook URL: `https://rabbidavid.org/api/stripe-webhook` (`checkout.session.completed`).
  - Modo: `free_testing: false` por defecto en Render.

---

## 4. Flujo de Pago y Resolución de Cuentas Cruzadas

1. **Creación de Checkout (`/api/create-checkout-session`)**:
   Recibe `{ tier }`, inyecta en metadatos `session_id`, `user_id`, `registered_email`, `tier` y crea la sesión Stripe Checkout.
2. **Redirección y Desbloqueo Inmediato**:
   Al completar el pago, Stripe devuelve a `result.html?checkout_session_id=cs_...&paid=true`. El frontend llama de inmediato a `/api/checkout-verify`, que consulta la API de Stripe en tiempo real y ejecuta `apply_tier_purchase`.
3. **Mapeo de Correos Distintos (`apply_tier_purchase`)**:
   Si el usuario se registra con un correo y paga con otro en Stripe/PayPal, el backend vincula la sesión y usuario por `metadata[session_id]` o `metadata[user_id]` o `registered_email`. El usuario nunca pierde acceso.

---

## 5. Frontend (`public/`)

- **Result Page (`result.html` + `result-app.js`)**:
  - Barra de progreso dual (estimación 2-3 min para audio, ~35s para plan).
  - **Transición instantánea**: Cuando el backend confirma `status: 'ready'`, cancela inmediatamente el timer y renderiza el `<audio controls>` o el botón de descarga del plan, sin esperar a que la barra llegue al 100%.
  - Carrusel de biblioteca de libros (`book-carousel.js`) accesible y automático.
  - Paywall dinámico priorizando el plan personal de $27 como recomendado sobre la lectura de $7.
- **Portal de Cuenta (`account.html` + `account.js`)**:
  - Visualización y escucha de lecturas previas, descarga de planes y audio sin fricción.
  - Botón "Start a New Test" genera nueva sesión sin bucles.

---

## 6. Despliegue Rápido y Verificación

### Desplegar Backend (Render):
```bash
git add server.py ...
git commit -m "mensaje"
git push origin main
```
Render compila y despliega en ~1-2 min.

### Desplegar Frontend (Netlify):
```bash
python C:\Users\srgm2\.gemini\antigravity\brain\22ab224a-c5eb-42de-8868-351bdc0bf32c\scratch\package_and_deploy.py
```

### Ejecutar Tests:
```bash
# Node
node --test test_password_visibility.cjs test_quiz_navigation.cjs test_result_ui.cjs test_book_carousel.cjs
# Python
python -m unittest test_free_testing.py test_personalization.py test_app.py test_auth.py
```

---

## 7. Matriz de Resolución de Bugs (Troubleshooting)

- **Stripe da 400 "Stripe is not configured"**: Verificar línea 1445 de `server.py` con la clave base64 decodificada.
- **Audio colgado**: La generación en FishAudio tarda de 2 a 3 min. Si falla, el backend marca `status: 'needs_review'` y muestra el enlace de soporte.
- **Netlify no actualiza**: Subir con `package_and_deploy.py` que empaqueta con forward slashes POSIX.
- **GitHub Push rechazado**: Nunca pegar `rk_live_...` o `sk_live_...` en texto plano en archivos commiteados; siempre usar base64 o env vars.
