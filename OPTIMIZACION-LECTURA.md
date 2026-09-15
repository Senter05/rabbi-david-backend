# Optimización de la primera lectura — 15/09/2026

Cambio activo en el servidor local: instrucciones compactas sin longitudes contradictorias, límite de salida 2600 tokens y razonamiento extendido desactivado para la primera lectura. Se mantienen las validaciones de cuatro secciones, referencias a las respuestas y primer paso. Modelo y credenciales sin cambios. Plan y narración siguen separados.

Pruebas reales con casos ficticios: 6,92 s, 7,34 s y 6,42 s; tres informes válidos. Esto mide la llamada y validación, no prueba carga simultánea ni garantiza un máximo de 20 s. Durante el ajuste hubo respuestas rechazadas; no deben contarse como pruebas exitosas. La versión anterior tardó 51,33 s y no pasó validación.

36 pruebas de aplicación/personalización/entradas/modo gratuito aprobadas. En la suite completa, una prueba de PDF falla porque el título se extrae con un salto de línea; corresponde a los cambios de maquetación actuales y no se modificó en esta tarea.

Servidor reiniciado solo tras comprobar que no había trabajos activos. PID al activar: 17708. Debe conservarse el proceso oculto; no depende de una sesión de terminal anterior.

Referencia técnica: https://openrouter.ai/docs/guides/best-practices/reasoning-tokens
