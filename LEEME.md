# Rabbi David — Antigravity conectado

## Abrir la página

Abre **INICIAR.cmd**. Si el servidor ya está activo, abrirá la página; si está cerrado, lo iniciará en segundo plano y abrirá el navegador. No hace falta mantener una ventana de terminal abierta.

Dirección local: **http://127.0.0.1:8100/**

El lanzador usa el Python incluido en este ordenador con Codex. Si ese programa cambia de ubicación, actualiza `RD_PYTHON` en el lanzador. El proyecto necesita ReportLab, disponible en ese entorno. Esta versión solo se puede visitar desde este ordenador.

## Base utilizada

El frontend parte del backup indicado por el usuario:

`C:\Users\srgm2\Videos\material-edicion\BACKUP-rabbi-david-website-20260915\_140852\rabbi-david-website`

**Ese backup permanece intacto.** Se trabaja en esta copia independiente, conservando su diseño como base e integrando el backend. No es el frontend marfil de la versión rechazada.

## Recorrido para comprobar

1. Abre el test e introduce **nombre y correo**, ambos obligatorios. No se puede empezar sin ellos. La suscripción a mensajes comerciales es independiente y opcional.
2. Responde las preguntas; la sesión conserva tus avances. Revisa las respuestas y autoriza la preparación con IA.
3. Abre la lectura gratuita. Los niveles de **$19** y **$45** son demostraciones sin cobros. Desde el nivel de $19, la mejora personal muestra **$26 adicionales** y conserva las respuestas.
4. El nivel personal añade un plan de acción de 14 días y permite solicitar el audio. Una bienvenida hablada opcional también puede usar el nombre introducido.
5. Descarga el PDF y revisa el progreso del plan. Consulta el catálogo de libros existentes.
6. Las entregas, enlaces de recuperación y seguimientos de 24 horas y 5 días se preparan en el **buzón local** de prueba. No llegan a Gmail ni a ningún otro buzón externo.

La dirección de correo se comprueba por formato. Confirmar que pertenece realmente a la persona requerirá conectar un servicio de envío y verificarla mediante un enlace.

## IA y voz

La lectura, el plan y el seguimiento opcional tienen integración con OpenRouter. La voz autorizada está conectada con ai33.pro. Cada nueva generación de audio consume créditos; recargar la página o pulsar varias veces no debe crear grabaciones duplicadas. Las tareas inciertas quedan para revisión antes de repetirlas. El navegador puede requerir pulsar reproducir para escuchar.

## Datos privados

Configuración: `../../work/rabbi-david-private/config.json`.

Sesiones, buzón y audios: `../../work/rabbi-david-private/antigravity-data`.

Las rutas parten de esta carpeta. Las credenciales no están en los archivos públicos del website. No incluyas la carpeta privada al compartir o publicar la entrega.

## Pendiente para producción

- Dominio, alojamiento y adaptación del servidor para acceso público seguro.
- Servicio real de correo: actualmente no hay SMTP ni entrega externa.
- Checkout y pasarelas de pago, expresamente excluidos por ahora.
- Revisión editorial de lecturas, planes, prácticas y oferta final antes de vender.
- Confirmación final de precios de los libros que aún no tienen uno definido.

No se presentan testimonios inventados ni se atribuyen revisiones personales que no ocurren. La página es una previsualización funcional, no una tienda publicada.

## Pruebas

`python test_app.py` desde esta carpeta ejecuta once pruebas de backend: recorrido completo, aislamiento, validaciones, acceso, ramas adaptativas, PDF, recuperación, edición y protección frente a solicitudes duplicadas. No consumen créditos ni envían mensajes. El contrato técnico está en **BACKEND.md**.
