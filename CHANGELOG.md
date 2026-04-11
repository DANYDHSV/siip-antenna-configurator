# Control de Cambios

Todos los cambios notables en este proyecto serán documentados en este archivo.

## [1.2.0] - 2026-03-21
### 🌟 Nuevas Funcionalidades
- **Actualizador de Firmware Automático (OTA)**: La aplicación verifica transparentemente contra la API de Ubiquiti (`fw-update.ubnt.com`) si existe un parche más nuevo para la base estática `WA`. De existir, ofrece descargarla, mostrándote una ventana de progreso y actualizando las configuraciones centrales automáticamente.
- **Bypass de Políticas de Seguridad v19+**: Las antenas con firmware de fábrica en revisiones v19 y superior exigen obligatoriamente 12 caracteres. El configurador intercepta la validación e inyecta temporalmente `Siip.123456789` para abrir puertas SSH durante la Fase 1 sin sacrificar la restauración del backup, previniendo cuellos de botella de downgrade.
- **Botón Rápido de Ajustes**: Se incluye un icono de Engrane (`⚙️`) directamente en el header de la aplicación para saltar rápidamente a la manipulación de IPs y recursos locales, complementando al botón Dark/Light mode.

### 🛠 Mejoras y Correcciones (Bug Fixes)
- **Corrección de Tiempos en Pings para macOS**: El binario `ping` nativo en macOS utiliza milisegundos (`-W`) contrastando con Linux (segundos), lo que producía falsos positivos por timeout (1ms). Ahora inyecta `1000` en sistemas Darwin, resucitando la Detección de Dispositivos.
- **Sincronización Crítica en Memoria Flash (SSH)**: Se ajustó el motor paramiko para ser bloqueante (`stdout.channel.recv_exit_status()`). Antes, el comando `reboot` atropellaba a la escritura en búfer `cfgmtd` por la naturaleza asíncrona de ssh, provocando pérdida esporádica de la IP inyectada.
- **Retraso Post-Selenium**: Al aplicar una nueva credencial vía Web, la antena resetea el proceso interno `sshd` matando momentáneamente sus puertos. Se implementó una pausa extendida de 8s para asegurar que SSH esté levantado previniendo `Channel closed`.
- **Rendimiento Nativo de la Intefaz Gráfica (macOS Text Invisibility)**: Sustitución de `tk.Button` retrogradados por componentes `ttk.Button` para los utilitarios "Copiar Log" y "Copiar MACs". Ahora el Sistema Operativo dibuja nativamente los gradientes, bordes, y corrige drásticamente colores invisibles (blanco sobre blanco) originados a perder foco o alternar en modo Light.

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
