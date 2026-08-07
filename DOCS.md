# Documentación de Smart Home UI Manager

## Estado de la aplicación

La versión `1.1.0` mantiene la línea estable iniciada en `1.0.0` y agrega dos componentes opcionales, desactivados por defecto: **Smart Entity Timer 0.3.0** y **Smart Entity Timer Card 0.2.2**. La lógica estable de instalación, actualización, reparación, respaldo y restauración se conserva. El tipo de inventario continúa como lista seleccionable con dos valores válidos:

```text
frontend
integration
```

La aplicación fue diseñada como herramienta privada de mantenimiento administrada por el instalador, no para operación diaria del cliente final.

## Ajustes recomendados de la aplicación

Mantén normalmente:

- **Iniciar al arrancar:** desactivado.
- **Watchdog:** desactivado.
- **Actualización automática:** desactivada.

Actualiza Smart Home UI Manager mientras esté detenida. Después guarda la configuración y presiona **Iniciar** una sola vez. La aplicación ejecuta la tarea seleccionada y se detiene al terminar.

## Regla principal de rutas

Dentro del contenedor de Smart Home UI Manager, la carpeta de configuración de Home Assistant siempre se encuentra en:

```text
/config
```

Aunque File Editor, Studio Code Server u otra herramienta muestre la misma carpeta como `/homeassistant`, en las opciones de esta aplicación debes escribir `/config`.

| Ruta vista en otras herramientas | Ruta que debes usar en Smart Home UI Manager |
|---|---|
| `/homeassistant/www/...` | `/config/www/...` |
| `/homeassistant/custom_components/...` | `/config/custom_components/...` |
| `/homeassistant/configuration.yaml` | `/config/configuration.yaml` |

Ejemplo correcto para Mushroom instalada mediante HACS:

```text
/config/www/community/lovelace-mushroom/mushroom.js
```

Ejemplo incorrecto dentro de esta aplicación:

```text
/homeassistant/www/community/lovelace-mushroom/mushroom.js
```

## Prioridad de los modos de operación

Los modos especiales son exclusivos. Activa solo el modo que necesitas.

| Opción activa | Operación ejecutada |
|---|---|
| `local_inventory_enabled: true` | Solo calcula la huella SHA-256 local |
| `restore_backup_enabled: true` | Solo restaura un respaldo |
| `diagnostic_only_enabled: true` | Solo realiza el diagnóstico |
| Todas las anteriores en `false` | Ejecuta mantenimiento normal |

Después de usar un modo especial, vuelve a desactivarlo antes de la siguiente ejecución.

# Referencia de todas las opciones

## `diagnostic_only_enabled`

### Función

Ejecuta únicamente el diagnóstico previo. No instala, actualiza, repara ni restaura componentes.

### Configuración

```yaml
diagnostic_only_enabled: true
local_inventory_enabled: false
restore_backup_enabled: false
```

### Procedimiento

1. Activa **Solo diagnóstico**.
2. Guarda la configuración.
3. Inicia la aplicación una vez.
4. Revisa el registro.
5. Abre el reporte:

```text
/config/ui-manager/diagnostics/latest.txt
```

6. Confirma:

```text
Fallos críticos: 0
El mantenimiento puede continuar.
```

7. Vuelve a configurar:

```yaml
diagnostic_only_enabled: false
```

### Cuándo usarlo

- Después de instalar la aplicación.
- Después de actualizar Smart Home UI Manager.
- Antes de un mantenimiento importante.
- Cuando cambió la versión de Home Assistant OS o Core.
- Para comprobar permisos, espacio y acceso interno sin modificar componentes.

---

## `minimum_free_space_mb`

### Función

Define el espacio libre mínimo requerido en `/config` antes del mantenimiento.

### Configuración recomendada

```yaml
minimum_free_space_mb: 200
```

### Rango permitido

```text
50 a 5000 MB
```

Si no hay espacio suficiente, el diagnóstico genera un fallo y el mantenimiento se detiene antes de modificar componentes.

---

## `local_inventory_enabled`

### Función

Activa el modo de inventario local SHA-256. Calcula la huella de un componente ya instalado sin descargar, reemplazar ni eliminar archivos.

### Configuración base

```yaml
local_inventory_enabled: true
```

Mientras esté activado, el mantenimiento normal no se ejecuta.

### Resultado

El reporte se guarda en:

```text
/config/ui-manager/checksum-candidates/latest.txt
```

Al terminar, vuelve a configurar:

```yaml
local_inventory_enabled: false
```

---

## `local_inventory_type`

### Función

Indica qué clase de componente se va a inventariar. En la interfaz aparece como una lista seleccionable.

### Valores disponibles

```text
frontend
integration
```

### Selecciona `frontend` cuando

- El componente es una tarjeta de dashboard.
- La ruta apunta a un archivo JavaScript individual.
- Ejemplos: Mushroom, Mini Graph Card o Modern Circular Gauge.

```yaml
local_inventory_type: frontend
```

### Selecciona `integration` cuando

- El componente es una integración personalizada.
- La ruta apunta a una carpeta completa.
- La carpeta contiene un archivo `manifest.json` válido.

```yaml
local_inventory_type: integration
```

---

## `local_inventory_name`

### Función

Nombre descriptivo que aparecerá en el reporte de inventario.

Ejemplos:

```yaml
local_inventory_name: Mushroom
```

```yaml
local_inventory_name: SonoffLAN
```

Este nombre es informativo y no determina la ruta de instalación.

---

## `local_inventory_version`

### Función

Versión del componente que estás evaluando en laboratorio.

Ejemplo:

```yaml
local_inventory_version: 5.2.2
```

Para una integración, la versión indicada debe coincidir con la versión declarada en su `manifest.json`. Si no coincide, el reporte solicitará revisión.

---

## `local_inventory_path`

### Función

Ruta real del archivo o carpeta que se va a inventariar. Debe estar dentro de `/config`.

### Para una tarjeta

Debe apuntar al archivo JavaScript exacto:

```yaml
local_inventory_path: /config/www/community/lovelace-mushroom/mushroom.js
```

### Para una integración

Debe apuntar a la carpeta que contiene `manifest.json`:

```yaml
local_inventory_path: /config/custom_components/sonoff
```

### Error frecuente

```text
No such file or directory: '/homeassistant'
```

Solución: sustituye `/homeassistant` por `/config`.

---

# Procedimiento completo: inventario de una tarjeta

Ejemplo para Mushroom instalada por HACS:

```yaml
local_inventory_enabled: true
local_inventory_type: frontend
local_inventory_name: Mushroom
local_inventory_version: 5.2.2
local_inventory_path: /config/www/community/lovelace-mushroom/mushroom.js
```

1. Confirma mediante File Editor o Studio Code que el archivo `mushroom.js` existe.
2. Convierte la ruta visible a una ruta que empiece con `/config`.
3. Guarda la configuración.
4. Inicia la aplicación una sola vez.
5. Abre:

```text
/config/ui-manager/checksum-candidates/latest.txt
```

6. Copia la huella SHA-256.
7. Confirma la misma huella en otra instalación de laboratorio antes de aprobarla para el catálogo.
8. Desactiva `local_inventory_enabled`.

La huella corresponde al archivo JavaScript instalado, no al ZIP o a la página de GitHub.

# Procedimiento completo: inventario de una integración

Ejemplo para SonoffLAN:

```yaml
local_inventory_enabled: true
local_inventory_type: integration
local_inventory_name: SonoffLAN
local_inventory_version: 3.12.2
local_inventory_path: /config/custom_components/sonoff
```

1. Confirma que la carpeta existe.
2. Confirma que contiene `manifest.json`.
3. Confirma que la versión indicada coincide con el manifiesto.
4. Guarda e inicia la aplicación una sola vez.
5. Abre:

```text
/config/ui-manager/checksum-candidates/latest.txt
```

6. Copia la huella del árbol de archivos.
7. Valídala en una segunda instalación.
8. Desactiva `local_inventory_enabled`.

La huella de una integración se calcula sobre su árbol completo de archivos instalado. Se ignoran cachés de Python y archivos temporales definidos por la aplicación.

---

## `restore_backup_enabled`

### Función

Activa el modo exclusivo de restauración manual de una integración.

### Configuración recomendada

```yaml
restore_backup_enabled: true
restore_component: sonofflan
restore_backup: latest_good
```

### Procedimiento

1. Activa **Restaurar respaldo**.
2. Indica el componente.
3. Usa normalmente `latest_good`.
4. Guarda e inicia la aplicación una vez.
5. Revisa:

```text
/config/ui-manager/restore-reports/latest.txt
```

6. Reinicia Home Assistant Core cuando el reporte lo solicite.
7. Comprueba la integración.
8. Desactiva:

```yaml
restore_backup_enabled: false
```

La restauración crea primero un respaldo de seguridad del estado instalado actualmente.

---

## `restore_component`

### Función

ID del componente del catálogo que se desea restaurar.

Valores actuales:

```text
sonofflan
spook
```

Ejemplo:

```yaml
restore_component: spook
```

Debe utilizarse el ID interno del catálogo, no necesariamente el nombre visible de la integración.

---

## `restore_backup`

### Función

Selecciona el respaldo que se restaurará.

### Valor recomendado

```yaml
restore_backup: latest_good
```

### Opciones

| Valor | Comportamiento |
|---|---|
| `latest_good` | Restaura el respaldo bueno más reciente y omite `SUSPECT`, `UNKNOWN` e `INVALID` |
| `latest` | Restaura el respaldo más reciente sin filtrar su clasificación |
| `AAAAmmdd-HHMMSS` | Restaura una carpeta de respaldo específica |

Usa `latest_good` salvo que conozcas exactamente el respaldo específico que necesitas.

El inventario de respaldos está en:

```text
/config/ui-manager/backups/inventory/latest.txt
```

---

## `max_integration_backups`

### Función

Cantidad máxima de respaldos que se conservan por integración.

### Valor recomendado

```yaml
max_integration_backups: 5
```

### Rango permitido

```text
1 a 20
```

Los respaldos se crean antes de:

- Actualizar una integración existente.
- Reparar una integración con huella incorrecta.
- Restaurar una integración.

La primera instalación no crea respaldo porque todavía no existe una versión anterior.

---

# Opciones de componentes administrados

## `mini_graph_card`

```yaml
mini_graph_card: true
```

Administra Mini Graph Card. La instala, verifica, actualiza o repara y registra su recurso de dashboard.

## `mushroom`

```yaml
mushroom: true
```

Administra Mushroom. La instala, verifica, actualiza o repara y registra su recurso de dashboard.

## `modern_circular_gauge`

```yaml
modern_circular_gauge: true
```

Administra Modern Circular Gauge. La instala, verifica, actualiza o repara y registra su recurso de dashboard.

## `sonofflan`

```yaml
sonofflan: true
```

Administra la integración SonoffLAN. Antes de actualizar o reparar crea un respaldo. Puede requerir reiniciar Home Assistant Core.

## `spook`

```yaml
spook: true
```

Administra la integración Spook. Antes de actualizar o reparar crea un respaldo. Puede requerir reiniciar Home Assistant Core.

## `smart_entity_timer`

```yaml
smart_entity_timer: false
```

Administra **Smart Entity Timer 0.3.0**. Es una integración personalizada y permanece desactivada por defecto porque todavía está en desarrollo activo. Requiere Home Assistant `2026.7.0` o posterior.

Cuando se habilita, Smart Home UI Manager puede instalarla, verificar su versión y SHA-256, actualizarla, repararla y crear respaldos de sus archivos antes de una actualización o reparación.

La instalación se realiza en:

```text
/config/custom_components/smart_entity_timer
```

Después de instalarla o actualizarla, reinicia Home Assistant Core.

**Importante para migraciones:** el respaldo de Smart Home UI Manager conserva los archivos de la integración, pero no sustituye un respaldo completo de Home Assistant. La migración oficial de Smart Entity Timer `0.2.x` a `0.3.0` requiere que no haya temporizadores activos y recomienda crear un respaldo completo de Home Assistant antes de actualizar.

## `smart_entity_timer_card`

```yaml
smart_entity_timer_card: false
```

Administra **Smart Entity Timer Card 0.2.2**. Permanece desactivada por defecto y requiere Smart Entity Timer. Requiere Home Assistant `2026.7.0` o posterior.

La tarjeta se instala en:

```text
/config/www/ui-components/smart-entity-timer-card/smart-entity-timer-card.js
```

y registra automáticamente el recurso:

```text
/local/ui-components/smart-entity-timer-card/smart-entity-timer-card.js?v=0.2.2
```

Para usar el conjunto completo, habilita ambas opciones:

```yaml
smart_entity_timer: true
smart_entity_timer_card: true
```

La integración aparece primero en el catálogo y se procesa antes que la tarjeta. Si habilitas solo la tarjeta, el archivo y el recurso pueden instalarse, pero la tarjeta no tendrá el backend Smart Entity Timer necesario para funcionar.

### Regla para todos los componentes

- `true`: Smart Home UI Manager administra el componente.
- `false`: el componente se omite completamente.
- Cambiarlo a `false` no desinstala ni elimina el componente.
- La aplicación no elimina configuraciones, cuentas ni dispositivos de Home Assistant.

---

# Adopción desde HACS de Smart Entity Timer

En el laboratorio puedes continuar usando HACS para validar versiones nuevas y obtener sus huellas. En una instalación administrada por Smart Home UI Manager evita que HACS y UI Manager actualicen simultáneamente el mismo componente.

## Integración

Si Smart Entity Timer `0.3.0` ya está instalado mediante HACS y su árbol de archivos coincide con la huella aprobada, UI Manager lo reconocerá como `VERIFICADO`. A partir de ese momento, evita actualizar esa misma integración desde HACS en ese equipo.

## Tarjeta

HACS suele instalar la tarjeta en:

```text
/config/www/community/smart-entity-timer-card/smart-entity-timer-card.js
```

UI Manager utiliza su propia ubicación:

```text
/config/www/ui-components/smart-entity-timer-card/smart-entity-timer-card.js
```

No mantengas cargados simultáneamente dos recursos de la misma tarjeta. En una instalación de cliente deja como recurso activo únicamente el administrado por UI Manager.

## Huellas aprobadas para 1.1.0

```text
Smart Entity Timer 0.3.0
e43b10283883132485391d0a9a75eb835733809471d71a9605ef700662ea3504

Smart Entity Timer Card 0.2.2
aba1d46bce7cc8dbe15faab5936000af2b99b7b3b7df72ecaf5918396256a168
```

# Mantenimiento normal

Para ejecutar el mantenimiento normal, utiliza:

```yaml
diagnostic_only_enabled: false
local_inventory_enabled: false
restore_backup_enabled: false
```

Deja en `true` únicamente los componentes que deseas administrar.

La aplicación:

1. Ejecuta el diagnóstico previo.
2. Valida `components.json`.
3. Comprueba la versión de Home Assistant Core.
4. Omite componentes incompatibles antes de descargarlos.
5. Instala componentes ausentes.
6. Actualiza versiones anteriores.
7. Repara componentes cuya huella no coincide.
8. Registra los recursos de dashboard.
9. Genera respaldos de integraciones cuando corresponde.
10. Genera el reporte de mantenimiento.
11. Actualiza el inventario de respaldos.
12. Se detiene al finalizar.

Reporte:

```text
/config/ui-manager/reports/latest.txt
```

Si se instala, actualiza, repara o restaura una integración, revisa si el reporte solicita reiniciar Home Assistant Core.

# Diagnóstico previo automático

Antes del mantenimiento normal se comprueba:

- Trazabilidad de la imagen ejecutada.
- Validez del catálogo.
- Disponibilidad de Python y `curl`.
- Módulos Python requeridos.
- Montaje y escritura de `/config`.
- Acceso de escritura a tarjetas, integraciones y reportes.
- Espacio libre.
- Token interno de Supervisor.
- Consulta de Home Assistant Core.
- Resolución DNS de GitHub.

Resultados:

- `PASS`: correcto.
- `WARN`: observación que no bloquea.
- `FAIL`: fallo crítico; no se modifican componentes.

# Ubicación rápida de reportes

| Reporte | Ruta |
|---|---|
| Mantenimiento | `/config/ui-manager/reports/latest.txt` |
| Diagnóstico | `/config/ui-manager/diagnostics/latest.txt` |
| Inventario SHA-256 | `/config/ui-manager/checksum-candidates/latest.txt` |
| Restauración | `/config/ui-manager/restore-reports/latest.txt` |
| Inventario de respaldos | `/config/ui-manager/backups/inventory/latest.txt` |

Se conservan los últimos 20 reportes históricos de cada tipo. `latest.txt` no cuenta dentro del límite.

# Solución rápida de problemas

## La ruta `/homeassistant` no existe

Mensaje:

```text
No such file or directory: '/homeassistant'
```

Solución: usa la ruta equivalente dentro de `/config`.

## La tarjeta no se encuentra

1. Abre `/config/www/community`.
2. Confirma el nombre real de la carpeta creada por HACS.
3. Busca el archivo JavaScript exacto.
4. Copia la ruta completa comenzando con `/config`.

## La integración no contiene `manifest.json`

La ruta debe apuntar a la carpeta concreta de la integración, no a `/config/custom_components` completo.

Ejemplo correcto:

```text
/config/custom_components/sonoff
```

## La versión indicada no coincide

Abre `manifest.json` y utiliza exactamente la versión declarada por la integración instalada.

## No existe `latest_good`

Revisa:

```text
/config/ui-manager/backups/inventory/latest.txt
```

Puede que todavía no exista ningún respaldo clasificado como `GOOD`. Selecciona un respaldo específico únicamente después de revisar su estado y versión.

## Componente incompatible

El componente se omite antes de descargarse. Actualiza Home Assistant Core o mantén una versión aprobada compatible en el catálogo.

## SHA-256 diferente

No apruebes la huella hasta confirmar:

- Que la versión sea la correcta.
- Que el archivo provenga de la publicación oficial.
- Que no haya sido modificado localmente.
- Que la misma huella aparezca en una segunda instalación de prueba.

## Recurso de dashboard ya registrado

No es un error. La aplicación comprobó que el recurso correcto ya existe.

## Cuándo reiniciar Home Assistant Core

Normalmente después de instalar, actualizar, reparar o restaurar SonoffLAN, Spook o Smart Entity Timer. Las tarjetas de frontend suelen requerir únicamente recargar el navegador.

# Publicar una versión futura

1. Prueba el componente nuevo o actualizado mediante HACS en laboratorio.
2. Obtén y valida su SHA-256.
3. Modifica el catálogo y los archivos de configuración necesarios.
4. Incrementa `version` en `ui_manager/config.yaml`.
5. Agrega la versión a `CHANGELOG.md`.
6. Ejecuta el workflow con `publish=false` y `allow_overwrite=false`.
7. Confirma la compilación `amd64` y `aarch64`.
8. Ejecuta con `publish=true` y `allow_overwrite=false`.
9. Confirma el manifiesto y la verificación pública.
10. Actualiza primero una instalación de laboratorio.
11. Ejecuta diagnóstico y mantenimiento normal.
12. Distribuye la actualización gradualmente.

No sobrescribas una versión publicada. Una corrección posterior a `1.1.0` debe publicarse como `1.1.1`; una nueva función compatible puede publicarse como `1.2.0`.

# Componentes de terceros

Las tarjetas e integraciones administradas pertenecen a sus respectivos autores y conservan sus propias licencias. Smart Home UI Manager descarga las publicaciones oficiales configuradas en el catálogo y verifica su contenido mediante SHA-256.
