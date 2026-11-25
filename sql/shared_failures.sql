SELECT r.path, r.request_hash, COUNT(*) AS affected_episodes, COUNT(DISTINCT d.task_id) AS affected_tasks
FROM request r JOIN depends_on d ON d.request_path=r.path
WHERE r.status!='ok' GROUP BY r.path ORDER BY r.path;
