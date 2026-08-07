# Smart Home UI Manager

Herramienta estable de mantenimiento manual para instalaciones de Home Assistant OS.

**Estado de la versión:** `1.1.0 stable`.

Permite instalar, actualizar, verificar y reparar tarjetas de interfaz e integraciones personalizadas previamente aprobadas, sin instalar HACS en los equipos de clientes.

## Funciones principales

- Catálogo central de versiones, URLs y huellas SHA-256.
- Validación de compatibilidad con Home Assistant Core.
- Diagnóstico previo de permisos, espacio, catálogo y servicios internos.
- Instalación y reparación de componentes seleccionados.
- Registro automático de recursos de dashboard.
- Respaldos y restauración segura de integraciones.
- Inventario local de huellas SHA-256.
- Selector cerrado para elegir inventario `frontend` o `integration`.
- Manual integrado con procedimiento para cada opción y equivalencias de rutas.
- Reportes históricos de mantenimiento y diagnóstico.
- Imagen precompilada multi-arquitectura para `amd64` y `aarch64`.
- Trazabilidad de versión, arquitectura, commit, fecha e imagen ejecutada.
- Verificación pública posterior a cada publicación en GHCR.

La aplicación funciona bajo ejecución manual, realiza la tarea seleccionada y se detiene.

## Ruta de configuración dentro de la aplicación

Smart Home UI Manager accede a la configuración mediante:

```text
/config
```

Aunque otras herramientas muestren `/homeassistant`, las rutas introducidas en esta aplicación deben comenzar con `/config`.

## Componentes opcionales en desarrollo

La versión `1.1.0` agrega dos componentes propios desactivados por defecto:

- **Smart Entity Timer 0.3.0** — integración personalizada.
- **Smart Entity Timer Card 0.2.2** — tarjeta de dashboard que requiere Smart Entity Timer.

Smart Home UI Manager continúa siendo estable. Estos dos componentes permanecen como opciones de adopción controlada: solo se administran cuando se habilitan explícitamente en la configuración. Ambos requieren Home Assistant `2026.7.0` o posterior.

Para evitar que dos gestores modifiquen el mismo componente, no mantengas HACS actualizando estos componentes en una instalación que ya sea administrada por Smart Home UI Manager. HACS puede seguir utilizándose en el laboratorio para validar futuras versiones.

## Distribución

La imagen multi-arquitectura se publica en:

```text
ghcr.io/abel-smart-home/smart-home-ui-manager
```

GitHub Actions construye las imágenes `amd64` y `aarch64`, publica el manifiesto genérico y comprueba que las tres referencias sean públicas y contengan los metadatos esperados.

Consulta `DOCS.md` para conocer cada opción, los modos de diagnóstico, inventario, restauración y mantenimiento, las rutas de reportes y la solución de errores frecuentes.
