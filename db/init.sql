-- CodeSherpa database initialization script
-- Creates the application user and base schema in Oracle 23ai Free

-- Connect as SYSDBA to create user
ALTER SESSION SET CONTAINER = FREEPDB1;

-- Create the application user (if not exists)
DECLARE
    user_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO user_count FROM all_users WHERE username = 'CODESHERPA';
    IF user_count = 0 THEN
        EXECUTE IMMEDIATE 'CREATE USER codesherpa IDENTIFIED BY codesherpa';
        EXECUTE IMMEDIATE 'GRANT CONNECT, RESOURCE TO codesherpa';
        EXECUTE IMMEDIATE 'GRANT CREATE SESSION TO codesherpa';
        EXECUTE IMMEDIATE 'GRANT UNLIMITED TABLESPACE TO codesherpa';
        EXECUTE IMMEDIATE 'GRANT DB_DEVELOPER_ROLE TO codesherpa';
    END IF;
END;
/
