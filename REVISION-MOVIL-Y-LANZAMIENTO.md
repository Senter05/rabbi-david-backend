# Revisión móvil y estado de lanzamiento

Fecha: 15 de septiembre de 2026. Prioridad: público de 50–70 años y 80% de tráfico móvil, según el responsable del proyecto.

## Conclusión

Se han corregido problemas de presentación y navegación móvil. La versión sigue siendo una **previsualización local**, no una versión lista para un lanzamiento comercial público.

## Cambios realizados

- Hoja independiente `public/css/mobile-accessibility.css`, enlazada en las veinte páginas. Conserva el diseño oscuro y dorado de Antigravity.
- Texto principal móvil de 18 px, interlineado más amplio y colores secundarios más claros. Metadatos de catálogo de 15–16 px; titulares adaptables al ancho.
- Botones principales con una altura mínima de 52 px y campos de entrada legibles. Las casillas tienen un control visual de 24 px dentro de etiquetas pulsables más amplias.
- Corregido el desbordamiento de la portada a 320 px. Grupos de contenido en una columna, márgenes consistentes y botones que permiten varias líneas.
- Cabecera sin fijarse sobre el contenido en móvil. Eliminados de la vista móvil dos bloques introductorios repetidos para dar prioridad al contenido y al formulario.
- Catálogo y doce fichas: controles mayores, portadas compactas, menos espacio vacío, títulos y precios que se ajustan al ancho.
- Resultado: índice en una columna, fuentes legibles, tarjetas del plan menos apretadas, números de capítulo sin partirse y ventanas de confirmación con desplazamiento vertical.
- Al avanzar o retroceder en el test, el progreso y la nueva pregunta vuelven a la parte superior visible.
- Portadas de libros situadas más abajo en la portada y el catálogo cargan de forma diferida. No se han alterado las imágenes originales.
- Se respeta la preferencia de movimiento reducido y se conserva la posibilidad de ampliar la página.

## Comprobaciones realizadas

| Superficie | Comprobación | Resultado |
|---|---|---|
| 18 páginas públicas: portada, catálogo, doce fichas, FAQ, ayuda, privacidad y términos | Anchos de ventana de 320 y 430 px | Sin desbordamiento del contenido principal ni controles principales de menos de 44 px |
| Portada, catálogo, ficha de libro, FAQ y ayuda | 768 px | Sin desbordamiento del contenido principal |
| Portada | 1440 px y revisión visual | Composición de escritorio conservada |
| Ayuda | 844 × 390 px, horizontal | Formulario ajustado al ancho y accesible mediante desplazamiento |
| Cuestionario | Inicio a 320 px; recorrido de 11 preguntas a 390 px; revisión a 430 px | Sin recortes; opciones, campos y textos legibles |
| Cuestionario | Avanzar, retroceder, texto inválido y corrección | Respuestas conservadas; error visible; navegación comprobada |
| Resultado y plan | Sesión aislada con contenido de prueba, a 320 px | Sin desbordamiento; enlaces, tarjetas y confirmación de nuevo test accesibles |
| HTML y CSS | Veinte enlaces a la hoja móvil, etiquetas viewport y sintaxis | Comprobaciones aprobadas |

El navegador usado reserva 15 px para su barra de desplazamiento: la prueba de ventana de 320 px examinó un área de contenido de 305 px. Las medidas se obtuvieron del documento renderizado, además de inspeccionar capturas.

La comprobación de contenido principal excluye los carruseles de reseñas: contienen testimonios presentados como verificados sin evidencia de verificación. No se ha mejorado ni validado esa presentación como parte de esta entrega. Siguen siendo un pendiente editorial; sus controles pequeños tampoco quedan cubiertos por la aprobación de controles principales.

### Contraste comprobado por muestras

Sobre los fondos oscuros definidos en la hoja de estilo:

- Texto descriptivo de producto: 11,38:1.
- Texto secundario sobre tarjeta: 9,90:1.
- Texto negro en el extremo más oscuro del botón de compra: 6,92:1.
- Botón principal, extremo más oscuro del degradado: 5,26:1.

Se utilizaron como referencia las guías de W3C sobre [reorganización del contenido](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html), [contraste](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) y [tamaño de los objetivos pulsables](https://www.w3.org/WAI/WCAG22/Understanding/target-size-enhanced.html). Estas comprobaciones por muestras **no constituyen una certificación WCAG completa**.

## Qué impide dar el lanzamiento por listo

1. **Informe nuevo y plan extenso:** todavía no hay una prueba real completa satisfactoria de lectura v3 y plan v2. Los éxitos anteriores documentados corresponden a versiones más breves; el proveedor gratuito limitó las peticiones durante la nueva prueba.
2. **Entrega real:** falta dominio, alojamiento público y servicio de correo. El PDF y el adjunto local funcionan; no se entregan mensajes a Gmail.
3. **Operación pública:** el servidor es local y el modo gratuito sigue activado, con generación de audio que consume créditos. Hace falta preparar límites de consumo, despliegue y recuperación antes de recibir tráfico público.
4. **Contenido comercial:** las 66 reseñas etiquetadas como verificadas carecen de evidencia proporcionada. También siguen enlaces de compra provisionales. Las pasarelas permanecen excluidas por decisión del responsable; no se han implementado en esta revisión.
5. **Validación final de uso:** faltan pruebas con personas del público objetivo, Safari en iPhone y Chrome en Android reales, teclado móvil, zoom y conexión móvil real. La revisión actual utiliza tamaños de pantalla simulados en un navegador de escritorio.

## Coordinación

El responsable confirmó que había otro editor trabajando en la misma carpeta. Se separaron los cambios generales en una hoja nueva para reducir conflictos. Si otro editor modifica estos archivos, hay que repetir la comprobación de la versión resultante antes de publicar.
