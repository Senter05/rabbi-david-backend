# Backend Antigravity — contrato y comprobación

El servidor sirve exclusivamente `public/` del sitio Antigravity. Configuración, claves, sesiones y audio permanecen fuera de esa carpeta. El diseño anterior no forma parte de este frontend.

## Ejecución local

`server.py --config <configuración privada existente> --data <directorio antigravity-data> --port 8100 --enable-voice`

La voz solo se genera tras una petición explícita del frontend. Cada trabajo conserva su identificador; errores inciertos quedan para revisión y no se cobran automáticamente nuevas generaciones. `--offline` prepara reflexiones de prueba sin llamadas de IA; omitir `--enable-voice` impide generar audio.

## Sesión y contrato

Cookie HttpOnly y SameSite Strict. Todas las peticiones POST usan JSON y el encabezado `X-Requested-With: RabbiDavid`. Las respuestas de estado contienen `questions`, `answers`, `step`, `started`, `status`, `reading`, `tier`, `plan`, `plan_status`, `voice`, `intro`, `email`, `marketing` y `recommendation` cuando corresponde. Las claves, identificadores privados de voz y rutas del servidor no se exponen.

| Ruta | Entrada / salida |
|---|---|
| GET `/api/state` | Estado de la sesión. Lectura gratuita limitada a una sección; plan solo en nivel personal. |
| POST `/api/enroll` | `{name,email,marketing?}`. Nombre y correo válidos obligatorios antes de guardar respuestas, generar o acceder a niveles. Marketing independiente, desactivado por defecto. |
| POST `/api/save` | `{answers,step}`. Incluir `answers.name`; validar respuestas según preguntas del estado. |
| POST `/api/followup` | `{consent:true}`. Seguimiento opcional adaptado a respuestas. |
| POST `/api/generate` | `{consent:true,guided?:true}`. Inicia lectura asíncrona; consultar estado. |
| POST `/api/demo-tier` | `{tier:"reading"}` o `{tier:"personal"}`. Simulación de $19 / $45; mejora desde lectura $26 en interfaz. No cobra. |
| POST `/api/voice` | `{}`. Requiere plan personal listo y voz habilitada. |
| POST `/api/intro` | `{}`. Bienvenida individual opcional en nivel personal. |
| GET `/api/audio`, `/api/welcome`, `/api/transcript` | Archivos de audio propios o texto propio; nunca de otra sesión. |
| GET `/api/pdf` | PDF correspondiente al nivel actual. |
| POST `/api/days` | `{days:[1,2]}`. Progreso de días 1 a 14. |
| POST `/api/contact` | `{email,marketing}`. Correo válido obligatorio, permite retirar seguimientos. |
| GET `/api/inbox` | Buzón local de esta sesión, con fechas de seguimiento a 24 horas y 5 días. |
| POST `/api/recover` | `{email}`. Enlace de un uso, 15 minutos, guardado en buzón local. |
| GET `/access?token=…` | Recupera sesión y redirige a `/result.html`. |
| GET `/api/catalog`, `/api/practices` | Arrays de catálogo y prácticas. |
| POST `/api/owned` | `{owned:["morning"]}`. Evita recomendar libros marcados como propios. |
| POST `/api/support` | `{message}`. Guarda consulta local; no envía a terceros. |
| POST `/api/new` | `{}`. Nueva sesión; vuelve a exigir nombre y correo. |
| GET `/api/config` | `{mode:"preview",payments:false,email:"local",ai:boolean,voice:boolean}`. |

## Validación realizada

11 pruebas aprobadas: recorrido completo, separación entre sesiones, niveles y PDF, ramas de preguntas, seguimiento, recuperación de un uso, archivos privados inaccesibles, reconstrucción del plan tras editar, correo/nombre obligatorios incluso evitando la interfaz, y clics simultáneos sin duplicar lectura, plan o audio. Voz simulada en estas pruebas: no consume créditos.

## Límites vigentes

Servidor restringido a localhost; no apto aún para publicación directa. Pagos desactivados por petición del usuario. Correo y soporte permanecen en buzón local hasta disponer de dominio y proveedor de envío. Plan de acción y prácticas necesitan revisión editorial final. La dirección escrita se valida por formato; demostrar propiedad real del buzón requiere conectar el servicio de correo y un enlace de verificación. CSP permite estilos inline necesarios para animaciones originales; scripts solo del propio sitio, sin evaluación dinámica.

## Prueba gratuita temporal (15 septiembre 2026)
La configuración privada tiene `free_testing: true`. El resultado válido de IA da acceso al informe completo, al plan de 14 días y a la narración sin checkout. La preparación de audio es automática; recargar no vuelve a enviar la misma tarea al proveedor. ai33 utiliza los créditos del proyecto. Los correos siguen en el buzón local; no llegan a Gmail.
Para volver al embudo de precios, cambiar únicamente `free_testing` a `false` en la configuración privada y reiniciar el servidor. Los casos ya desbloqueados conservan su acceso.
Validación: 38 pruebas automatizadas aprobadas, incluidas seis de acceso gratuito e idempotencia. Una respuesta inválida debe corregirse antes de generar el contenido.
