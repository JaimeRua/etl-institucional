CREATE SCHEMA IF NOT EXISTS stg;

CREATE TABLE IF NOT EXISTS stg.matricula_sies (
    ano smallint,
    llave_vacante text,
    codigo_carrera text,
    acreditacion_carrera text,
    facultad text,
    nombre_carrera text,
    total_matricula integer,
    total_matricula_mujeres integer,
    total_matricula_hombres integer,
    total_matricula_no_binarios_o_indefinidos integer,
    total_matricula_primer_ano integer,
    total_matricula_mujeres_primer_ano integer,
    total_matricula_hombres_primer_ano integer,
    total_matricula_no_binarios_o_indefinidos_primer_ano integer,
    clasificacion_institucion_nivel_1 text,
    clasificacion_institucion_nivel_2 text,
    clasificacion_institucion_nivel_3 text,
    codigo_de_institucion text,
    nombre_institucion text,
    acreditacion_institucional text,
    region text,
    provincia text,
    comuna text,
    nombre_sede text,
    area_del_conocimiento text,
    cine_f_1997_area text,
    cine_f_1997_subarea text,
    area_carrera_generica text,
    cine_f_2013_area text,
    cine_f_2013_subarea text,
    nivel_global text,
    carrera_clasificacion_nivel_1 text,
    carrera_clasificacion_nivel_2 text,
    modalidad text,
    jornada text,
    tipo_de_plan_de_la_carrera text,
    duracion_estudio_carrera smallint,
    duracion_total_de_carrera smallint,
    total_rango_de_edad integer,
    rango_de_edad_15_a_19_anos integer,
    rango_de_edad_20_a_24_anos integer,
    rango_de_edad_25_a_29_anos integer,
    rango_de_edad_30_a_34_anos integer,
    rango_de_edad_35_a_39_anos integer,
    rango_de_edad_40_y_mas_anos integer,
    rango_de_edad_sin_informacion integer,
    promedio_edad_carrera numeric(6,2),
    promedio_edad_mujer numeric(6,2),
    promedio_edad_hombre numeric(6,2),
    promedio_edad_no_binario numeric(6,2),
    tes_servicio_local_educacion text,
    tes_particular_subvencionado text,
    tes_particular_pagado text,
    tes_corp_de_administracion_delegada text,
    total_tes integer,
    cobertura_tes numeric(9,4),
    tipo_establecimiento_hc text,
    tipo_establecimiento_tp text,
    clas_est_adulto text,
    clas_est_joven text,
    _raw_ingestion_id bigint NOT NULL,
    _raw_batch_id text,
    _raw_loaded_at timestamptz NOT NULL,
    _raw_row_hash text,
    _stg_run_id text NOT NULL,
    _stg_loaded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT matricula_sies_raw_ingestion_uk UNIQUE (_raw_ingestion_id)
);

CREATE INDEX IF NOT EXISTS matricula_sies_ano_idx
    ON stg.matricula_sies (ano);
CREATE INDEX IF NOT EXISTS matricula_sies_codigo_carrera_idx
    ON stg.matricula_sies (codigo_carrera);
CREATE INDEX IF NOT EXISTS matricula_sies_codigo_institucion_idx
    ON stg.matricula_sies (codigo_de_institucion);

CREATE TABLE IF NOT EXISTS stg.matricula_sies_rechazos (
    _stg_run_id text NOT NULL,
    _raw_ingestion_id bigint NOT NULL,
    _raw_batch_id text,
    _raw_loaded_at timestamptz NOT NULL,
    rechazado_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    errores text[] NOT NULL,
    registro_raw jsonb NOT NULL,
    PRIMARY KEY (_stg_run_id, _raw_ingestion_id)
);

CREATE INDEX IF NOT EXISTS matricula_sies_rechazos_ingestion_idx
    ON stg.matricula_sies_rechazos (_raw_ingestion_id);

COMMENT ON TABLE stg.matricula_sies IS
    'Normalización técnica de raw.bi_mat_sies_reporte; sin reglas de integración institucional.';
COMMENT ON TABLE stg.matricula_sies_rechazos IS
    'Registros raw rechazados por conversiones o dominios técnicos, conservados por ejecución.';
