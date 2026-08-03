# Smart Home UI Manager

Herramienta de mantenimiento manual para instalaciones de Home Assistant OS.

**Estado de la versión:** `1.0.0 stable`. Esta es la primera línea base estable, validada en instalaciones limpias y actualizaciones sobre `amd64` y `aarch64`.

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
- Trazabilidad de versión, arquitectura, commit, fecha e imagen ejecutada.
- Verificación pública posterior a cada publicación en GHCR.

La aplicación funciona bajo ejecución manual, realiza la tarea seleccionada y se detiene.

## Distribución

La imagen multi-arquitectura se publica en:

```text
ghcr.io/abel-smart-home/smart-home-ui-manager
```

GitHub Actions construye las imágenes `amd64` y `aarch64`, publica el manifiesto genérico y comprueba que las tres referencias sean públicas y contengan los metadatos esperados.

Consulta `DOCS.md` para conocer la configuración, publicación, instalación limpia y procedimientos de mantenimiento.
