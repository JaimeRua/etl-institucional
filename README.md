# ETL Institucional

Repositorio de integración institucional con arquitectura de datos:

`SQL Server / APIs → raw → stg → int → mart → gold`

## Carga SQL Server → raw

El pipeline `sqlserver_to_raw` replica las tablas físicas de SQL Server en PostgreSQL sin aplicar reglas de negocio. Utiliza un manifiesto versionado con las 138 tablas y 6.289 columnas del inventario; `dbo.sysdiagrams` está documentada, pero deshabilitada.

Características:

- carga `FULL REFRESH` por tabla;
- lectura por lotes, sin cargar la tabla completa en memoria;
- inserción masiva con PostgreSQL `COPY`;
- `TRUNCATE` y carga dentro de la misma transacción: un error conserva la versión anterior;
- trazabilidad mediante `_etl_batch_id` y columnas de origen;
- auditoría general en `audit.etl_run` y por tabla en `audit.etl_table_run`;
- validación de columnas y comparación de conteos antes del `COMMIT`.

### Configuración

Los hosts, bases, usuarios y driver se definen en `config/dev.yml` o `config/prod.yml`. Los secretos se guardan únicamente en `.env`:

```dotenv
PG_PASSWORD=...
MSSQL_PASSWORD=...
```

El usuario SQL Server necesita `SELECT`; el usuario PostgreSQL necesita `TRUNCATE`, `INSERT`, `SELECT` y uso de las secuencias identity sobre `raw`, además de crear/actualizar las tablas de auditoría en `public`.

### Secuencia recomendada

1. Validar conexiones y estructura sin mover datos:

```bash
make run PIPELINE=sqlserver_to_raw ENV=dev ARGS="--table dbo.BI_MAT_SIES_REPORTE --dry-run"
```

2. Cargar una tabla piloto:

```bash
make run PIPELINE=sqlserver_to_raw ENV=dev ARGS="--table dbo.BI_MAT_SIES_REPORTE --chunk-size 10000"
```

3. Consultar auditoría y conteos:

```sql
SELECT * FROM audit.etl_run ORDER BY started_at DESC LIMIT 5;
SELECT * FROM audit.etl_table_run ORDER BY started_at DESC LIMIT 20;
```

4. Ejecutar las 137 tablas habilitadas:

```bash
make run PIPELINE=sqlserver_to_raw ENV=dev ARGS="--chunk-size 10000 --continue-on-error"
```

`--continue-on-error` intenta las tablas restantes y finalmente marca la ejecución como fallida si alguna no pudo cargarse. Sin esa opción, el proceso se detiene en el primer error. Puede repetirse `--table` para cargar una familia acotada.

La primera versión es intencionalmente `FULL REFRESH`. No se debe activar carga incremental hasta identificar para cada tabla una clave o marca de agua confiable (`updated_at`, identity monotónica o CDC).
