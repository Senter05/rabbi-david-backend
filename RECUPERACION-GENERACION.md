# Recuperación del informe y carga — 15/09/2026

## Cambios activos
- Primera lectura: máximo dos intentos. Si la validación rechaza el primero, el segundo recibe el motivo concreto y debe corregirlo. No se relajan las comprobaciones ni se muestra una plantilla como resultado de IA.
- Errores 401/403 no se repiten. No se ha añadido ningún reenvío automático a los pedidos de audio.
- Fallos definitivos guardan diagnóstico privado, excluido del estado público.
- Cuestionario y resultados muestran porcentaje estimado; 100% solamente cuando el servidor comunica que la lectura está lista. La conexión se vuelve a comprobar tras una interrupción.
- Plan y pregunta adicional usan generación sin razonamiento extendido; el plan conserva el contenido editorial del proyecto.

## Evidencia
- 43 pruebas Python aprobadas.
- Pruebas de presentación, respuesta inválida, reintento, porcentaje, conservación de respuestas y días del plan aprobadas.
- Informe del caso que fallaba: validado en 17,84 segundos, dos intentos. Guardado solo tras comprobar que sus respuestas y revisión no habían cambiado.
- El servidor se reinició sin trabajos activos. PID: 39160.

No se garantiza disponibilidad absoluta de los proveedores ni un máximo universal de 20 segundos. El envío a correo externo sigue pendiente de configurar. La prueba mantiene el checkout desactivado.

Comprobación final real: informe listo, plan generado por IA listo, bienvenida y audio principal listos. PDF y ambos audios servidos por HTTP 200 con contenido no vacío.
