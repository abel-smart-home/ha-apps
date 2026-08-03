# Documentación de Smart Home UI Manager

## Estado estable

La versión `1.0.0` es la primera versión marcada como `stable`. Fue validada mediante actualización desde 0.7.0, instalación limpia, ejecución en `amd64` y `aarch64`, diagnóstico previo, mantenimiento normal y verificación pública de las imágenes en GHCR.

Las futuras correcciones compatibles se publicarán como `1.0.1`, `1.0.2`, etc. Las funciones nuevas compatibles incrementarán la versión menor, por ejemplo `1.1.0`. Una versión ya publicada no debe sobrescribirse; cualquier corrección posterior requiere una etiqueta nueva.

## Uso previsto

Smart Home UI Manager es una herramienta privada de mantenimiento. Está diseñada para ser operada por el administrador de las instalaciones, no por el cliente final.

Mantén siempre:

- **Iniciar al arrancar:** desactivado.
- **Watchdog:** desactivado.
- **Actualización automática:** desactivada.

Actualiza la aplicación mientras esté detenida y después presiona **Iniciar** una sola vez.

## Distribución precompilada

La aplicación utiliza la imagen multi-arquitectura:

```text
ghcr.io/abel-smart-home/smart-home-ui-manager
```

Home Assistant usa el valor `version` de `config.yaml` como etiqueta de la imagen y selecciona automáticamente `amd64` o `aarch64`.

## Publicar una versión

El workflow se encuentra en:

```text
.github/workflows/build-ui-manager.yaml
```

La verificación pública se encuentra en:

```text
.github/scripts/verify-public-images.py
```

Procedimiento:

1. Actualiza los archivos de la aplicación.
2. Incrementa `version` en `ui_manager/config.yaml`.
3. Agrega la misma versión a `ui_manager/CHANGELOG.md`.
4. Guarda los cambios en la rama `main`.
5. Ejecuta **Build Smart Home UI Manager** con `publish=false` y `allow_overwrite=false`.
6. Confirma que `Validate and initialize`, `Build amd64` y `Build aarch64` terminen correctamente.
7. Ejecuta nuevamente con `publish=true` y `allow_overwrite=false`.
8. Confirma que también terminen `Publish multi-architecture manifest` y `Verify public publication`.
9. Revisa el resumen de la ejecución para confirmar imágenes públicas, arquitecturas, digests y commit.
10. Prueba la actualización en una sola instalación de laboratorio antes de distribuirla.

`allow_overwrite=true` se reserva para recuperar una publicación incompleta. No debe utilizarse para reemplazar normalmente una versión ya distribuida.

## Trazabilidad de compilación

El registro, diagnóstico y reporte de mantenimiento muestran:

- Versión de la aplicación.
- Arquitectura de la imagen.
- Commit que produjo la imagen.
- Fecha UTC de compilación.
- Repositorio de origen.
- Imagen y etiqueta ejecutadas.
- Confirmación de imagen precompilada.

El diagnóstico marca esta comprobación como `PASS` cuando todos los metadatos están presentes.

## Instalar en una instalación nueva de HAOS

1. Abre **Ajustes → Aplicaciones → Tienda de aplicaciones**.
2. Abre el menú de tres puntos y entra en **Repositorios**.
3. Agrega:

```text
https://github.com/abel-smart-home/ha-apps
```

4. Cierra el cuadro de repositorios y actualiza la tienda si fuera necesario.
5. Busca **Smart Home UI Manager**.
6. Abre la aplicación y presiona **Instalar**.
7. Confirma que Watchdog, inicio al arrancar y actualización automática estén desactivados.
8. En la configuración activa únicamente `diagnostic_only_enabled`.
9. Inicia la aplicación una vez y revisa `/config/ui-manager/diagnostics/latest.txt`.
10. Si el resultado permite continuar, desactiva `diagnostic_only_enabled` y ejecuta el mantenimiento normal.
11. Si se instalaron SonoffLAN o Spook, reinicia Home Assistant Core.
12. Agrega y configura las integraciones desde **Ajustes → Dispositivos y servicios** cuando corresponda.

Las tarjetas se registran como recursos automáticamente. Puede ser necesario recargar el navegador después de la primera instalación.

## Modos exclusivos

Solo uno de estos modos puede estar activado durante una ejecución.

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

- Trazabilidad de la imagen ejecutada.
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
7. Compila con `publish=false`.
8. Publica con `publish=true`.
9. Confirma la verificación pública.
10. Actualiza manualmente una instalación de laboratorio.
11. Ejecuta diagnóstico y mantenimiento.
12. Distribuye gradualmente durante los mantenimientos de clientes.

## Reportes y retención

Se conservan los últimos 20 reportes de cada tipo. Los archivos `latest.txt` no cuentan dentro de ese límite.

## Componentes de terceros

Las tarjetas e integraciones administradas pertenecen a sus respectivos autores y conservan sus propias licencias. Smart Home UI Manager descarga las publicaciones oficiales configuradas en el catálogo y verifica su contenido mediante SHA-256.
