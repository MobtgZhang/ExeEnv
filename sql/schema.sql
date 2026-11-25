CREATE TABLE candidate(method TEXT,task_id TEXT,ordinal INTEGER,
        answer TEXT NOT NULL,correct INTEGER NOT NULL,
        FOREIGN KEY(method,task_id) REFERENCES episode,
        PRIMARY KEY(method,task_id,ordinal));
CREATE TABLE condition(task_id TEXT REFERENCES task,ordinal INTEGER,
        final_available INTEGER NOT NULL,basis TEXT,region TEXT NOT NULL,
        condition_text TEXT,quote TEXT,consequence TEXT,
        PRIMARY KEY(task_id,ordinal));
CREATE TABLE consumes(method TEXT, task_id TEXT, ordinal INTEGER,
        stage TEXT NOT NULL, request_path TEXT REFERENCES request,
        FOREIGN KEY(method,task_id) REFERENCES episode,
        PRIMARY KEY(method,task_id,ordinal));
CREATE TABLE depends_on(method TEXT,task_id TEXT,ordinal INTEGER,
        stage TEXT NOT NULL,request_path TEXT NOT NULL REFERENCES request,
        status TEXT NOT NULL,
        FOREIGN KEY(method,task_id) REFERENCES episode,
        PRIMARY KEY(method,task_id,ordinal));
CREATE TABLE episode(method TEXT, task_id TEXT REFERENCES task,
        status TEXT NOT NULL, prediction TEXT, correct INTEGER NOT NULL,
        result_type TEXT NOT NULL, tokens INTEGER NOT NULL,
        PRIMARY KEY(method,task_id));
CREATE TABLE request(path TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
        status TEXT NOT NULL, tokens INTEGER, failed_attempts INTEGER,
        started_utc TEXT);
CREATE TABLE task(task_id TEXT PRIMARY KEY, family TEXT NOT NULL);
CREATE VIEW failure_propagation AS
        SELECT r.path,r.failed_attempts,COUNT(*) affected_episodes,
          COUNT(DISTINCT d.task_id) affected_tasks
        FROM request r JOIN depends_on d ON d.request_path=r.path
        WHERE r.status='unavailable' GROUP BY r.path,r.failed_attempts;
CREATE VIEW logical_usage AS SELECT e.method,SUM(r.tokens) tokens
        FROM episode e JOIN consumes c USING(method,task_id)
        JOIN request r ON r.path=c.request_path GROUP BY e.method;
CREATE VIEW outcome_counts AS SELECT method,result_type,COUNT(*) n
        FROM episode GROUP BY method,result_type;
CREATE VIEW shared_draft_partition AS
        SELECT e.method,e.task_id,t.family,
          CASE WHEN d.correct=0 AND e.correct=1 THEN 1 ELSE 0 END repair,
          CASE WHEN d.correct=1 AND e.result_type='incorrect' THEN 1 ELSE 0 END wrong_regression,
          CASE WHEN d.correct=1 AND e.result_type='returned_empty' THEN 1 ELSE 0 END empty_loss,
          CASE WHEN d.correct=1 AND e.result_type='unavailable' THEN 1 ELSE 0 END delivery_loss,
          e.correct-d.correct net
        FROM episode e JOIN episode d ON d.task_id=e.task_id AND d.method='draft'
          JOIN task t ON t.task_id=e.task_id WHERE e.method!='direct';
