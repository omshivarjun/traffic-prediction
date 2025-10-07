-- Initialize Hive Metastore Version
INSERT INTO "VERSION" ("VER_ID", "SCHEMA_VERSION", "VERSION_COMMENT") 
VALUES (1, '2.3.0', 'Hive release version 2.3.0')
ON CONFLICT DO NOTHING;
