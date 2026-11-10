-- A neutralized database (odoo-bin neutralize, or a restore or duplication
-- with "Neutralize") is meant to be copied around. Like base does for mail
-- server passwords, drop the SFTP password, so the copy cannot upload to,
-- list or delete from the production SFTP server.
--
-- Odoo runs this file from the installed code right after a restore or a
-- duplication, before any module upgrade, so the database can come from any
-- earlier version. Only the tables and columns that exist are touched: add
-- new secrets to the list below, never as a bare UPDATE.
DO $$
DECLARE
    target record;
BEGIN
    FOR target IN
        SELECT secret.table_name,
               string_agg(format('%I = %L', secret.column_name, secret.cleared), ', ') AS assignments
          FROM (VALUES
                    ('backup_provider_sftp', 'password', NULL::text)
               ) AS secret(table_name, column_name, cleared)
          JOIN information_schema.columns AS existing
            ON existing.table_schema = current_schema()
           AND existing.table_name = secret.table_name
           AND existing.column_name = secret.column_name
         GROUP BY secret.table_name
    LOOP
        EXECUTE format('UPDATE %I SET %s', target.table_name, target.assignments);
    END LOOP;
END
$$;
