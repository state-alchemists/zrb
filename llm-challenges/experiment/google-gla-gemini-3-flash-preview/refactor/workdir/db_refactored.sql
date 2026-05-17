PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE errors (dt TEXT, message TEXT, count INTEGER);
INSERT INTO errors VALUES('2026-05-17 18:55:21.296548','Database timeout',2);
INSERT INTO errors VALUES('2026-05-17 18:55:41','Database timeout',2);
CREATE TABLE api_metrics (dt TEXT, endpoint TEXT, avg_ms REAL);
INSERT INTO api_metrics VALUES('2026-05-17 18:55:21.296748','/users/profile',250.0);
INSERT INTO api_metrics VALUES('2026-05-17 18:55:41','/users/profile',250.0);
COMMIT;
