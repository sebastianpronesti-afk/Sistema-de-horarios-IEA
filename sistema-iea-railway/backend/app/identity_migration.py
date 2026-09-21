"""Additive PostgreSQL guards; existing identities and relations are never rewritten.

Reservations serialize concurrent attempts at the same document/code. Historical
duplicates keep their rows and are reported for review, but cannot grow silently.
"""
from sqlalchemy import text


def install_identity_guards(db):
    db.execute(text('LOCK TABLE catedras, docentes IN SHARE ROW EXCLUSIVE MODE'))
    statements = [
        """CREATE TABLE IF NOT EXISTS identity_keys (
            kind VARCHAR(30) NOT NULL, value TEXT NOT NULL, owner_id INTEGER,
            PRIMARY KEY(kind,value))""",
        """CREATE OR REPLACE FUNCTION identity_document(raw TEXT) RETURNS TEXT
        LANGUAGE plpgsql IMMUTABLE AS $$
        DECLARE result TEXT;
        BEGIN
          result := regexp_replace(coalesce(raw,''), '[[:space:]]', '', 'g');
          IF result ~ '^[0-9]+[.]0+$' THEN result := split_part(result,'.',1);
          ELSE result := replace(replace(result,'.',''),'-',''); END IF;
          IF result !~ '^[0-9]{6,12}$' THEN RETURN NULL; END IF;
          RETURN coalesce(nullif(ltrim(result,'0'),''),'0');
        END $$""",
        "DELETE FROM identity_keys WHERE kind IN ('docentes','catedras')",
        """INSERT INTO identity_keys(kind,value,owner_id)
          SELECT 'docentes',identity_document(dni),min(id) FROM docentes
          WHERE identity_document(dni) IS NOT NULL GROUP BY identity_document(dni)""",
        """INSERT INTO identity_keys(kind,value,owner_id)
          SELECT 'catedras',lower(btrim(codigo)),min(id) FROM catedras
          GROUP BY lower(btrim(codigo))""",
        """CREATE OR REPLACE FUNCTION protect_entity_identity() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        DECLARE new_key TEXT; old_key TEXT; held_by INTEGER;
        BEGIN
          IF TG_OP='UPDATE' AND NEW.id IS DISTINCT FROM OLD.id THEN
            RAISE EXCEPTION 'El ID es permanente' USING ERRCODE='23505';
          END IF;
          IF TG_TABLE_NAME='docentes' THEN
            new_key := identity_document(NEW.dni);
            IF TG_OP='UPDATE' THEN old_key := identity_document(OLD.dni); END IF;
            IF new_key IS NULL AND btrim(coalesce(NEW.dni,''))<>''
               AND (TG_OP='INSERT' OR NEW.dni IS DISTINCT FROM OLD.dni) THEN
              RAISE EXCEPTION 'Documento inválido' USING ERRCODE='23505';
            END IF;
          ELSE
            IF TG_OP='UPDATE' AND NEW.codigo IS DISTINCT FROM OLD.codigo THEN
              RAISE EXCEPTION 'El código de cátedra se conserva' USING ERRCODE='23505';
            END IF;
            new_key := lower(btrim(NEW.codigo));
            IF TG_OP='UPDATE' THEN old_key := lower(btrim(OLD.codigo)); END IF;
            IF new_key='' THEN RAISE EXCEPTION 'Falta el código de cátedra' USING ERRCODE='23505'; END IF;
          END IF;
          IF TG_OP='UPDATE' AND new_key IS NOT DISTINCT FROM old_key THEN RETURN NEW; END IF;
          IF new_key IS NULL THEN RETURN NEW; END IF;
          INSERT INTO identity_keys AS keys(kind,value,owner_id) VALUES(TG_TABLE_NAME,new_key,NEW.id)
            ON CONFLICT(kind,value) DO UPDATE SET owner_id=coalesce(keys.owner_id,EXCLUDED.owner_id)
            RETURNING owner_id INTO held_by;
          IF held_by<>NEW.id THEN
            RAISE EXCEPTION 'Identidad duplicada; revisá la ficha existente' USING ERRCODE='23505';
          END IF;
          RETURN NEW;
        END $$""",
        """CREATE OR REPLACE FUNCTION release_entity_identity() RETURNS TRIGGER
        LANGUAGE plpgsql AS $$
        DECLARE old_key TEXT; next_owner INTEGER;
        BEGIN
          IF TG_TABLE_NAME='docentes' THEN
            old_key := identity_document(OLD.dni);
            IF TG_OP='UPDATE' AND old_key IS NOT DISTINCT FROM identity_document(NEW.dni) THEN RETURN NULL; END IF;
          ELSE
            old_key := lower(btrim(OLD.codigo));
            IF TG_OP='UPDATE' THEN RETURN NULL; END IF;
          END IF;
          IF old_key IS NULL THEN RETURN NULL; END IF;
          PERFORM 1 FROM identity_keys WHERE kind=TG_TABLE_NAME AND value=old_key FOR UPDATE;
          IF TG_TABLE_NAME='docentes' THEN
            SELECT min(id) INTO next_owner FROM docentes WHERE identity_document(dni)=old_key;
          ELSE
            SELECT min(id) INTO next_owner FROM catedras WHERE lower(btrim(codigo))=old_key;
          END IF;
          UPDATE identity_keys SET owner_id=next_owner WHERE kind=TG_TABLE_NAME AND value=old_key;
          RETURN NULL;
        END $$""",
    ]
    for table in ('docentes', 'catedras'):
        statements += [
            f'DROP TRIGGER IF EXISTS identity_guard ON {table}',
            f'CREATE TRIGGER identity_guard BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION protect_entity_identity()',
            f'DROP TRIGGER IF EXISTS identity_release ON {table}',
            f'CREATE TRIGGER identity_release AFTER DELETE OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION release_entity_identity()',
        ]
    for statement in statements:
        db.execute(text(statement))
    db.commit()
