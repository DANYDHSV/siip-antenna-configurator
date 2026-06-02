# Control de Cambios

Todos los cambios notables en este proyecto serán documentados en este archivo.

## [1.4.0] - 2026-06-02
### 🌟 Nuevas Funcionalidades
- **Reintento de Actualización Automático**: Al finalizar el proceso completo, si se detecta que alguna de las antenas falló en su actualización de firmware, la aplicación mostrará una ventana emergente de confirmación preguntando al usuario si desea realizar un último intento de actualización con esas IPs finales fallidas.
- **Mapeo Inteligente de Indicadores en Reintento**: Durante la segunda vuelta de actualización (reintento), los puntos indicadores visuales de las antenas ya exitosas se mantienen verdes, mientras que los correspondientes a las antenas fallidas pasan a amarillo/naranja intermitente mientras se procesan, y finalmente se actualizan a verde o rojo según su resultado final.
- **Fusión Inteligente No Destructiva de CSV**: El motor de resultados en el backend fusiona los nuevos estados de éxito y las direcciones MAC obtenidas en el reintento directamente sobre las filas correspondientes del archivo `resultados_antenas.csv` (emparejando por IP inicial o final) en lugar de duplicar filas, manteniendo el historial completo intacto.

## [1.3.0] - 2026-06-02
### 🌟 Nuevas Funcionalidades
- **Cancelación Cooperativa**: Se implementó una arquitectura de detención cooperativa entre la interfaz gráfica (`gui_configurador.py`) y el backend (`configuracion_completa_antenas2.py`) usando una bandera de estado compartida (`cancel_requested`) y una excepción dedicada (`ProcesoCancelado`) basada en `KeyboardInterrupt`. Ahora el botón "Cancelar proceso" interrumpe de inmediato cualquier hilo de ejecución activo de manera limpia y responsiva.
- **Chequeos de Conectividad Verbosos**: Se habilitó el reporte de estado detallado (`verbose=True`) para todos los procesos de espera en red (`esperar_ping`, `esperar_web`, `esperar_ssh`). El usuario puede visualizar en la consola el avance de intentos en tiempo real en lugar de una pantalla estática.

### 🛠 Mejoras y Correcciones (Bug Fixes)
- **Corrección de Bloqueos en IPs Ajenas**: Se optimizó la validación inicial de conectividad de los dispositivos escaneados reduciendo dramáticamente el número de reintentos máximos (de 120/60 a 15/10 intentos). Esto permite que el backend descarte en menos de 20 segundos cualquier dirección IP del rango que responda a ping pero no pertenezca a una antena Ubiquiti activa (ej. otros dispositivos en la red local), evitando que la consola se congele en silencio durante minutos.
- **Protección contra Pérdida de Excepciones**: Se modificaron bloques genéricos `except:` para propagar correctamente las interrupciones de usuario (`KeyboardInterrupt`), garantizando que la señal de cancelación llegue sin trabas al final del ciclo de vida del hilo.

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
