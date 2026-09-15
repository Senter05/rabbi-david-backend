# Operación y pendientes externos

## Arranque y configuración
Usar `config.example.json` como referencia. Nunca incluir config.json, .env, bases de datos o claves en Git ni en los ZIP. Configurar en el alojamiento las claves de OpenRouter/ai33 y la voz autorizada. PUBLIC_ORIGIN debe ser el origen HTTPS visible al usuario. DATA_DIR debe apuntar a almacenamiento persistente privado; la plantilla no contrata ningún disco ni plan de pago. El disco efímero de una instancia no sirve para conservar lecturas.

El arranque de producción debe ejecutarse tras fijar PUBLIC_ORIGIN y DATA_DIR. El alojamiento termina TLS; la aplicación solo confía en configuración propia para cookie segura. El backend debe ser accesible a través del proxy del sitio. No ampliar ALLOWED_ORIGINS a todos los dominios de un proveedor.

## Límites y gasto
- MAX_TEXT_REQUESTS_PER_DAY: 100 llamadas por defecto, incluidos reintentos.
- MAX_VOICE_REQUESTS_PER_DAY: 10 envíos de grabación por defecto.
- max_jobs_per_day: 20 trabajos por identidad de correo/sesión.
- max_requests_per_minute: 120 operaciones POST por dirección de conexión.
- PAUSE_GENERATION=1 detiene nuevas llamadas facturables.
- Cola acotada: 12 trabajos, tres trabajadores.

Son límites de cantidad de solicitudes, no una garantía monetaria: el coste depende del modelo y del proveedor. Configurar también un presupuesto duro en la cuenta del proveedor. No se habilitaron créditos ni se cambió el presupuesto externo durante esta corrección. Si un proxy concentra todas las conexiones bajo una IP, el límite por conexión actúa como límite compartido; no confiar sin validación en un X-Forwarded-For aportado por usuarios.

## Recuperación y soporte
La clave privada descargable permite volver desde otro navegador sin correo. Los enlaces por correo necesitan SMTP y un origen configurado. SUPPORT_EMAIL y MAIL_FROM deben ser buzones propios confirmados; no utilizar el correo del agente registrado.

Administración desde terminal del propietario: `python manage.py --data <directorio> status`. No hay panel público de administración. `voice-resume --id <sesión> --field voice` reanuda la consulta de una tarea existente después de revisarla en el proveedor; no crea una grabación. Una tarea sin ID se revisa manualmente antes de autorizar otra. `mail-retry --id <mensaje> --confirmed-unsent` solo se usa tras comprobar que el mensaje no fue entregado.

## Datos, copia y restauración
Retención automática: 90 días sin actualización guardada. La interfaz permite exportación y borrado de la sesión actual. Para una copia administrativa, detener el proceso primero y copiar el directorio DATA_DIR completo a un volumen privado cifrado. Para restaurar, detener el proceso, conservar el directorio actual y arrancar una instancia aislada con una copia del respaldo mediante --data. Comprobar estado, PDF y adjuntos antes de sustituir la instancia. Nunca restaurar sobre una aplicación activa.

No se creó ninguna copia de datos reales en esta tarea. Antes de introducir copias de producción, definir plazo de retención, cifrado, responsables y un registro de borrados para reaplicarlos después de restaurar. La política pública evita afirmar que existe un sistema de copias que todavía no se ha configurado.

## Credenciales que estaban versionadas
config.json estaba seguido por Git y contenía claves configuradas. Se retiró del índice y se añadió a .gitignore, manteniendo el archivo local. Esto NO borra copias en commits anteriores. El titular debe renovar las claves en sus proveedores si ese historial se ha compartido, actualizar el entorno privado y retirar credenciales del historial mediante un procedimiento coordinado. No se reescribió historia compartida ni se invalidaron claves operativas durante esta corrección.

## Cierre externo pendiente
Confirmar correo de soporte, remitente, proveedor SMTP y dominio final; preparar almacenamiento persistente; probar una generación real autorizada y la entrega externa; incorporar checkout cuando se facilite. Las políticas explican el modo actual sin inventar suscripciones, plazos de respuesta o garantías de resultado.

## Referencias de redacción
La estructura de las políticas toma como referencia https://iqscore.me/terms, https://iqscore.me/privacy y https://iqscore.me/cookies; el texto se redactó para el funcionamiento real de este sitio. No se copiaron sus datos societarios, suscripciones, SLA, analítica o arbitraje. Se consultó la guía de la FTC: https://www.ftc.gov/business-guidance/resources/protecting-personal-information-guide-business para el enfoque de minimización y conservación.
