# Control de Cambios

Todos los cambios notables en este proyecto serán documentados en este archivo.

## [1.1.0] - 2025-12-12
### 🌟 Nuevas Funcionalidades
- **Test de Conexión**: Nuevo botón en la barra de estado que permite realizar una prueba de conectividad (ping scan) rápida e independiente sin iniciar el proceso de configuración completo. Muestra IPs detectadas y estado en la consola.
- **Modo "Sólo Actualizar"**: Nueva lógica operativa para reintentar únicamente la actualización de firmware en antenas que ya tienen configuración final, optimizando tiempos de reparación.
- **Gestión de Rangos Independientes**: Ahora es posible configurar rangos de IP distintos para cada operación (Configuración Standard, Test de Conexión y Sólo Actualizar) desde el menú de Ajustes.
- **Filtrado Inteligente de MACs**: El botón "Copiar MACs" ahora utiliza expresiones regulares para limpiar la salida, ignorando textos de error ("No disponible") y copiando únicamente direcciones MAC válidas.

### 🛠 Mejoras y Correcciones
- **Estabilidad Visual**: Solucionado el parpadeo errático de la barra de progreso al forzar modo 'determinate'.
- **Indicador de Estado Activo**: Implementado (finalmente) el indicador naranja para señalar visualmente qué antena se está procesando en tiempo real.
- **Layout y UX**: 
    - Aumentado tamaño de ventana inicial a 900x800 para asegurar visibilidad total de controles inferiores.
    - Estilo visual explícito para botones deshabilitados (gris).
    - Estilo permanente (Gris/Blanco) para el botón "Copiar MACs" según preferencia de usuario.
- **Correcciones Logicas**: Ajustes en el backend para soportar un modo de operación (update_only) que no desplaza la IP objetivo.

## [1.0.0] - 2025-12-10
### 🎉 Versión Inicial Estable

Esta es la primera versión estable y completa del Configurador de Antenas, lista para producción.

### 🚀 Nuevas Características
- **Barra de Progreso Granular**: Implementación de un sistema de seguimiento por fases (Detección, Config Web, SSH, Reinicio, Actualización) que proporciona un porcentaje de avance preciso y realista, eliminando las estimaciones genéricas.
- **Iconos Dinámicos**: La interfaz ahora detecta automáticamente la cantidad real de antenas activas/escaneadas y ajusta el número de indicadores visuales en pantalla, en lugar de mostrar siempre un número fijo.
- **Botón "Copiar Log"**: Agregado un botón dedicado en la consola para facilitar la extracción de registros de depuración y soporte.
- **Soporte de Tema Oscuro**: Mejoras en la visualización de tablas y controles para garantizar compatibilidad con modos oscuros del sistema operativo.
- **Navegación por Pestañas**: Separación clara entre la vista de "Proceso" (ejecución activa) y "Resultados" (tablas finales).

### 🐛 Correcciones y Optimizaciones (Bug Fixes)
- **Corrección de conteo de iconos**: Solucionado el problema donde se mostraban más indicadores de estado que antenas reales.
- **Lectura de CSV**: Mejorada la robustez al leer archivos de resultados, soportando correctamente valores booleanos ('True'/'False') para los estados de éxito/error.
- **Reducción de Ruido en Logs**: Se filtraron los mensajes repetitivos de "Esperando..." y cuentas regresivas internas de la consola visible, manteniendo la interfaz limpia mientras la barra de progreso se actualiza en el fondo.
- **Sincronización GUI-Backend**: Implementación de etiquetas de comunicación (`[GUI] PHASE_PROGRESS`, `[GUI] START/END_ANTENNA`) para una sincronización perfecta entre el proceso de fondo y la interfaz.
- **Manejo de Errores SSH**: Se añadieron bloques `try/except` faltantes en las rutinas de verificación post-actualización para evitar cierres inesperados.

### 💅 Mejoras Estéticas
- **Logo**: Se redondearon las esquinas del logotipo para una integración más suave con la interfaz moderna.
- **Limpieza de Directorio**: Reestructuración del proyecto para separar scripts de utilidad y archivos temporales de la base de código principal.

---
*Formato basado en [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).*
