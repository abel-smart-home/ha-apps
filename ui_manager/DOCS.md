# Documentación de Smart Home UI Manager

## Uso previsto

Smart Home UI Manager es una herramienta privada de mantenimiento. Está diseñada para ser operada por el administrador de las instalaciones, no por el cliente final.

La aplicación debe mantenerse con:

- **Iniciar al arrancar:** desactivado.
- **Watchdog:** desactivado.
- **Actualización automática:** desactivada.

Actualiza la aplicación mientras esté detenida y luego presiona **Iniciar** una sola vez.

## Distribución precompilada

Desde la versión 0.7.0, la aplicación utiliza la imagen multi-arquitectura:

```text
ghcr.io/abel-smart-home/smart-home-ui-manager
```

Antes de publicar una versión nueva:

1. Actualiza los archivos de la aplicación y su número de versión.
2. Ejecuta manualmente el workflow **Build Smart Home UI Manager** con `publish=false`.
3. Confirma que las compilaciones `amd64` y `aarch64` terminen correctamente.
4. Ejecuta nuevamente el workflow con `publish=true`.
5. Confirma que el paquete multi-arquitectura quede publicado.
6. Busca actualizaciones en una sola instalación de laboratorio.
7. Actualiza y ejecuta el diagnóstico y mantenimiento normal.
8. Solo después distribuye la versión durante mantenimientos de clientes.

## Modos exclusivos

Solo uno de estos modos puede estar activado durante una ejecución:

### Solo diagnóstico

```yaml
diagnostic_only_enabled: true
```

Comprueba el entorno sin instalar, actualizar, reparar ni restaurar componentes. El reporte queda en:

```text
/config/ui-manager/diagnostics/latest.txt
```

### Inventario local SHA-256

```yaml
local_inventory_enabled: true
```

Calcula la huella de un archivo o carpeta ya instalado, sin descargar ni reemplazar nada.

### Restauración manual

```yaml
restore_backup_enabled: true
restore_component: sonofflan
restore_backup: latest_good
```

Restaura el respaldo bueno más reciente de una integración y crea un respaldo de seguridad antes de reemplazarla.

## Mantenimiento normal

Todos los modos exclusivos deben estar desactivados. Activa únicamente los componentes utilizados por esa instalación y presiona **Iniciar**.

La aplicación ejecutará primero el diagnóstico previo. Si encuentra un fallo crítico, se detendrá antes de modificar componentes.

El reporte de mantenimiento queda en:

```text
/config/ui-manager/reports/latest.txt
```

## Diagnóstico previo

La aplicación comprueba:

- Validez de `components.json`.
- Disponibilidad de Python y curl.
- Módulos Python necesarios.
- Montaje y escritura de `/config`.
- Escritura en las carpetas de tarjetas, integraciones y reportes.
- Espacio libre mínimo configurado.
- Presencia del token interno de Supervisor.
- Consulta de la versión de Home Assistant Core.
- Resolución DNS de GitHub.

El espacio mínimo se controla con:

```yaml
minimum_free_space_mb: 200
```

El rango permitido es de 50 a 5000 MB.

## Resultados del diagnóstico

- `PASS`: comprobación correcta.
- `WARN`: existe una observación, pero no bloquea el mantenimiento.
- `FAIL`: fallo crítico; la aplicación no modifica componentes.

## Actualizar un componente aprobado

1. Prueba la versión nueva con HACS en el laboratorio.
2. Obtén su SHA-256 mediante el inventario local.
3. Confirma la misma huella en otra instalación de prueba.
4. Actualiza versión, URL, SHA-256 y compatibilidad en `components.json`.
5. Incrementa la versión de la aplicación.
6. Documenta el cambio en `CHANGELOG.md`.
7. Prueba y publica la imagen desde GitHub Actions.
8. Actualiza manualmente la aplicación en una instalación de laboratorio.
9. Ejecuta el diagnóstico y el mantenimiento.
10. Distribuye gradualmente durante los mantenimientos de clientes.

## Reportes y retención

Se conservan los últimos 20 reportes de cada tipo. Los archivos `latest.txt` no cuentan dentro de ese límite.

## Componentes de terceros

Las tarjetas e integraciones administradas pertenecen a sus respectivos autores y conservan sus propias licencias. Smart Home UI Manager descarga las publicaciones oficiales configuradas en el catálogo y verifica su contenido mediante SHA-256.
