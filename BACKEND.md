# Backend — contrato actualizado

El sitio y las peticiones `/api/` deben verse bajo el mismo origen del navegador. Puede utilizarse el proxy existente en `public/_redirects`; PUBLIC_ORIGIN debe ser exactamente el origen visible al usuario, no un comodín. RENDER_EXTERNAL_HOSTNAME permite al proxy alcanzar exclusivamente ese host de backend. ALLOWED_ORIGINS acepta una lista separada por comas de orígenes exactos adicionales, si son necesarios.

El modo local escucha en 127.0.0.1. Producción requiere `--host 0.0.0.0`, PUBLIC_ORIGIN HTTPS y un DATA_DIR privado persistente. Voz requiere ENABLE_VOICE=1 o --enable-voice. Pagos siguen desactivados.

Las operaciones POST requieren JSON y X-Requested-With: RabbiDavid. Se conservan las rutas de enrolamiento, guardado, generación, seguimiento opcional, demo-tier, plan, voz, preferencias y progreso. Las operaciones nuevas son:

| Ruta | Función |
|---|---|
| POST /api/recovery-key | Genera una clave privada válida 90 días; invalida la anterior de esa sesión. Solo se guarda su hash. |
| POST /api/recover-key | `{key}` abre la sesión asociada. Requiere conservar privadamente la clave. |
| GET /api/export | Descarga el estado público de la sesión actual, sin IDs del proveedor o rutas internas. |
| POST /api/logout | Elimina la cookie del navegador sin borrar el registro. |
| POST /api/delete | `{confirmation:"DELETE"}` elimina sesión, tokens, mensajes locales y audio; rechaza durante trabajos activos. |
| POST /api/support | `{name,email,category,message}`; devuelve referencia y estado de entrega. |
| GET /api/config | Informa del modo de correo y soporte, sin credenciales. |

Correo SMTP: cola persistente con estados local, pending, sending, sent y needs_review. No se vuelven a enviar mensajes sent ni se convierte automáticamente el histórico local. Los enlaces por email son de un uso y 15 minutos; la clave descargable es reutilizable hasta expirar o ser reemplazada.

Recursos estáticos: HTML revalidado, recursos públicos max-age=3600 con ETag, datos privados no-store. Los archivos admiten rangos simples y se transmiten por bloques de 64 KB. Las rutas estáticas no crean una sesión.

Las sesiones sin actualizaciones guardadas durante 90 días se eliminan en mantenimiento periódico; trabajos activos se omiten hasta finalizar. Las cuotas contienen identificadores hash y contadores, no respuestas del test.
