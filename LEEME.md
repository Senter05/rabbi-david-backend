# Rabbi David — revisión corregida

## Abrir y probar
INICIAR.cmd inicia el entorno local en http://127.0.0.1:8100. La voz está desactivada por defecto. Las claves permanecen en configuración privada o variables de entorno; nunca deben formar parte de una entrega.

Para un entorno sin proveedores: `python server.py --offline --data <carpeta-privada> --port 8100`.
Para pruebas: `python -m unittest discover -v`. Las pruebas usan datos ficticios y proveedores simulados; no consumen créditos. En esta revisión: 77 pruebas satisfactorias.

## Cambios
- Orígenes y hosts exactos, sin comodines de proveedores ni aceptación global por PRODUCTION/RENDER. Cookie HttpOnly + SameSite=Lax; Secure con PUBLIC_ORIGIN HTTPS.
- Cola de 12 trabajos como máximo, tres trabajadores, límites de solicitudes y presupuesto diario de llamadas persistente.
- Pregunta opcional reservada antes de generar; voz con espera progresiva y revisión tras 30 minutos.
- Recuperación independiente del correo mediante clave privada, exportación, cierre de sesión y borrado confirmado.
- Contacto y políticas con datos de Senter Company LLC. Footer común en 22 páginas.
- Recursos públicos con caché y ETag, archivos por bloques y rangos de descarga, portada optimizada y tipografía local.
- Errores iniciales recuperables y preservación de ajustes/audio durante actualizaciones.

## Se conserva por indicación del responsable
Reseñas, sus cifras y criterios de verificación; destinos de compra a Google; avance automático de reseñas. Se reparó únicamente la interacción Helpful y el reemplazo de una foto fallida, sin alterar los tres puntos anteriores.

## Correo y contacto
El formulario funciona y guarda un identificador de solicitud. Para entrega externa configurar SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, MAIL_FROM y SUPPORT_EMAIL. SMTP usa STARTTLS verificado. Sin configuración, la interfaz indica que la entrega externa está desconectada.

Los mensajes antiguos de previsualización permanecen locales cuando se conecta SMTP. Solo las nuevas solicitudes se encolan para entrega. Los envíos con resultado incierto quedan para revisión: no se repiten automáticamente.

## Publicación
Leer OPERACION.md. Se necesitan origen final, almacenamiento persistente, datos de soporte y credenciales vigentes. El checkout se integrará cuando el responsable aporte sus enlaces. No se ha realizado despliegue ni activado gastos en esta revisión.
