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

El usuario SQL Server necesita `SELECT`; el usuario PostgreSQL necesita `TRUNCATE`, `INSERT`, `SELECT` y uso de las secuencias identity sobre `raw`, además de crear/actualizar las tablas de auditoría en `audit` y los objetos de transformación en `stg`.

El DDL reproducible de las 138 tablas se encuentra en
`pipelines/sqlserver_to_raw/sql/001_create_raw_tables.sql`. En una base nueva se
aplica una sola vez antes de la primera carga:

```bash
psql "$PG_DSN" -v ON_ERROR_STOP=1 \
  -f pipelines/sqlserver_to_raw/sql/001_create_raw_tables.sql
```

El archivo crea únicamente objetos faltantes. Los cambios posteriores de
estructura deben agregarse como migraciones nuevas.

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

Los logs se emiten en JSON e incluyen `run_id`, pipeline, tabla, conteos y
evento. El nivel y formato pueden cambiarse con `APP_LOG_LEVEL` y
`APP_LOG_FORMAT` (`json` o `text`).

## Normalización raw → stg de matrícula SIES

El pipeline `raw_to_stg_matricula` transforma `raw.bi_mat_sies_reporte` en
`stg.matricula_sies`. La definición física está en
`pipelines/raw_to_stg_matricula/sql/001_create_stg_matricula_sies.sql` y las 60
reglas columna a columna están versionadas en
`pipelines/raw_to_stg_matricula/transformation_matrix.json`.

La ejecución limpia espacios y cadenas vacías, convierte tipos únicamente tras
validar su formato y conserva `_raw_ingestion_id`, el batch y la fecha de carga
de `raw`. Los registros con conversiones inválidas no entran silenciosamente en
`stg`: se guardan en `stg.matricula_sies_rechazos` con el registro original en
JSON y la lista de reglas incumplidas.

Validar el resultado proyectado sin reemplazar los datos de `stg`:

```bash
make run PIPELINE=raw_to_stg_matricula ENV=dev ARGS="--dry-run"
```

Ejecutar el `FULL REFRESH` de la tabla normalizada:

```bash
make run PIPELINE=raw_to_stg_matricula ENV=dev
```

Revisar calidad y reconciliación después de la carga:

```sql
SELECT count(*) AS filas_stg FROM stg.matricula_sies;

SELECT error, count(*) AS filas
FROM stg.matricula_sies_rechazos r
CROSS JOIN LATERAL unnest(r.errores) AS error
WHERE r._stg_run_id = '<run_id mostrado por el pipeline>'
GROUP BY error
ORDER BY filas DESC, error;

SELECT ano, sum(total_matricula) AS total_matricula
FROM stg.matricula_sies
GROUP BY ano
ORDER BY ano;
```

Un run con rechazos queda como `SUCCESS_WITH_WARNINGS` en
`audit.etl_table_run`. La carga se considera técnicamente reconciliada cuando
`rows_in = rows_out + filas_rechazadas`; los rechazos deben revisarse antes de
promover la información a `int`.

## Calidad y pruebas

```bash
make ci
```

La integración continua ejecuta Ruff, Pyright y pytest sobre Python 3.10 y
3.11. GitHub Actions levanta una base PostgreSQL 16 aislada para comprobar el
ciclo de auditoría, ejecutar el DDL completo de `raw` y validar el flujo
`raw_to_stg_matricula` con registros válidos y rechazados.

La configuración productiva no contiene direcciones ni usuarios ficticios.
Estos valores se entregan mediante `PG_*` y `MSSQL_*` en el entorno de
despliegue; las contraseñas continúan en `PG_PASSWORD` y `MSSQL_PASSWORD`.
