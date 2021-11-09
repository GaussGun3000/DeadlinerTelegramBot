--
-- File generated with SQLiteStudio v3.3.3 on Вс окт 10 16:45:03 2021
--
-- Text encoding used: System
--
PRAGMA foreign_keys = off;
BEGIN TRANSACTION;

-- Table: deadlines
DROP TABLE IF EXISTS deadlines;
CREATE TABLE deadlines (subject TEXT NOT NULL, task TEXT NOT NULL, date REAL NOT NULL, reminder_days INTEGER NOT NULL, notified INTEGER);
INSERT INTO deadlines (subject, task, date, reminder_days, notified) VALUES ('ЭВМ', 'Лаба 1', 1633467540.0, 0, 3);
INSERT INTO deadlines (subject, task, date, reminder_days, notified) VALUES ('ТОЭ', 'ДЗ 117, 114', 1633640340.0, 0, 7);
INSERT INTO deadlines (subject, task, date, reminder_days, notified) VALUES ('Экономика', 'Эссе', 1634331540.0, 0, 0);
INSERT INTO deadlines (subject, task, date, reminder_days, notified) VALUES ('Право', 'Лекция Конституция ч.3', 1633888800.0, 0, 7);
INSERT INTO deadlines (subject, task, date, reminder_days, notified) VALUES ('КиТГ', 'Видос для деда', 1634255940.0, 0, 0);

COMMIT TRANSACTION;
PRAGMA foreign_keys = on;
