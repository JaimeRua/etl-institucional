# DDL de la capa raw

`001_create_raw_tables.sql` versiona la estructura inicial de las 138 tablas
del inventario físico de `analisis_pro`.

Fuentes utilizadas para generarlo:

- `INVENTARIO_FISICO_.xlsx`, hoja `2.DATOS_COLUMNAS_TABLAS`;
- `../tables.json`, que define los nombres normalizados en PostgreSQL.

SHA-256 del inventario utilizado:

```text
1d78f77fdf48c17c939eeba306872111158be1fdb22e964302f88003c2a48917
```

## Criterios

- conserva el tipo físico del origen, con equivalencias PostgreSQL;
- conserva `NOT NULL`, pero no replica PK, índices ni `IDENTITY` del origen;
- los identificadores de negocio no se corrigen en `raw`;
- agrega metadatos técnicos `_etl_*` a todas las tablas;
- incluye `sysdiagrams`, aunque el manifiesto mantiene su carga deshabilitada;
- utiliza `CREATE TABLE IF NOT EXISTS` y no modifica tablas existentes.

Equivalencias principales:

| SQL Server | PostgreSQL raw |
|---|---|
| `nvarchar(n)` | `varchar(n)` |
| `nvarchar(max)` | `text` |
| `varchar(n)` | `varchar(n)` |
| `float` | `double precision` |
| `real` | `real` |
| `tinyint` | `smallint` |
| `smallint` | `smallint` |
| `int` | `integer` |
| `bigint` | `bigint` |
| `decimal(p,s)` | `numeric(p,s)` |
| `datetime` | `timestamp(3) without time zone` |
| `date` | `date` |
| `bit` | `boolean` |
| `varbinary` | `bytea` |

## Uso

Primero revisar el cambio y luego ejecutar con un usuario autorizado:

```bash
psql "$PG_DSN" -v ON_ERROR_STOP=1 \
  -f pipelines/sqlserver_to_raw/sql/001_create_raw_tables.sql
```

El script establece solamente la línea base. Una modificación futura de una
tabla existente debe incorporarse en una migración nueva y no mediante la
edición retroactiva de `001_create_raw_tables.sql`.
