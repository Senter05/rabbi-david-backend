# Integración de Cuentas y Checkout (Guía para el Desarrollador de Checkout)

Esta guía describe cómo asociar compras realizadas en el checkout con la cuenta de usuario de Rabbi David (`https://rabbidavid.org`) para que los accesos adquiridos queden guardados permanentemente.

---

## 1. Activación de Tiers de Lectura / Test

Cuando un usuario paga un nivel del test en el checkout (ej. \$7 para Lectura Completa o \$32 para Plan Personal + Audio):

### Endpoint Backend: `POST /api/internal/grant-tier`
Este endpoint actualiza el tier del usuario de forma inmediata y desacoplada.

- **URL**: `https://rabbi-david-backend.onrender.com/api/internal/grant-tier`
- **Método**: `POST`
- **Headers**:
  - `Content-Type: application/json`
  - `X-Requested-With: RabbiDavid`
- **Payload**:
```json
{
  "email": "usuario@ejemplo.com",
  "tier": "reading",
  "session_id": "cs_live_opcional_si_viene_de_stripe",
  "order_id": "ord_12345",
  "provider_id": "pi_stripe_12345"
}
```

### Valores de `tier`:
- `"reading"`: Desbloquea la lectura completa de 7 secciones (\$7).
- `"personal"`: Desbloquea la lectura completa + el plan de 14 días personalizado + el audio (\$32 total).

### Comportamiento Automático:
1. Localiza la lectura activa del usuario (por `email` o `session_id`).
2. Actualiza el nivel a `reading` o `personal`.
3. Si el tier es `personal`, encola automáticamente la preparación del plan de 14 días y audio.
4. Vincula la orden en la tabla de pedidos y en la cuenta del usuario.
5. El usuario ve de inmediato su lectura desbloqueada en `result.html` y en `account.html` (Mi Cuenta) sin tener que regenerar ni volver a pagar.

---

## 2. Metadatos Recomendados en Sesiones de Checkout (Stripe)

Al crear la sesión de Checkout (`stripe.checkout.sessions.create`), incluir en `metadata`:
```json
{
  "email": customer_email,
  "tier": "reading", // o "personal"
  "user_id": user_id_si_esta_disponible
}
```
El webhook de Stripe (`POST /api/stripe-webhook`) o el redirect de retorno (`/download/...` o `result.html`) procesará estos metadatos automáticamente.

---

## 3. Compras de E-Books

Las compras de los 5 libros digitales (`rituals`, `legacy`, `complete`, `ceo`, `morning`) ya están integradas:
- Se guardan en la tabla `orders` con `email` y `book_id`.
- Se asocian automáticamente a la cuenta del usuario (`account.html`) en la pestaña de lecturas/libros adquiridos cuando el usuario inicia sesión con el mismo email.
