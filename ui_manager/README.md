# Smart Home UI Manager

Herramienta de mantenimiento manual para instalaciones de Home Assistant OS.

Permite instalar, actualizar, verificar y reparar tarjetas de interfaz e integraciones personalizadas previamente aprobadas, sin instalar HACS en los equipos de clientes.

## Funciones principales

- Catálogo central de versiones, URLs y huellas SHA-256.
- Validación de compatibilidad con Home Assistant Core.
- Diagnóstico previo de permisos, espacio, catálogo y servicios internos.
- Instalación y reparación de componentes seleccionados.
- Registro automático de recursos de dashboard.
- Respaldos y restauración segura de integraciones.
- Inventario local de huellas SHA-256.
- Reportes históricos de mantenimiento y diagnóstico.
- Imagen precompilada multi-arquitectura para `amd64` y `aarch64`.

La aplicación funciona bajo ejecución manual, realiza la tarea seleccionada y se detiene.

Desde la versión 0.7.0, GitHub Actions construye y publica la imagen en GitHub Container Registry. Las instalaciones de Home Assistant descargan la imagen terminada y ya no compilan la aplicación localmente.

Consulta `DOCS.md` para conocer la configuración y los procedimientos de mantenimiento.
