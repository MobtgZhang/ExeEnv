WITH pools AS (
SELECT c.task_id, MAX(c.correct) AS covered FROM candidate c
JOIN episode s ON s.method=c.method AND s.task_id=c.task_id
WHERE c.method='sc' AND s.status='scored' GROUP BY c.task_id HAVING COUNT(*)=3)
SELECT e.method, COUNT(*) AS pool_available, SUM(p.covered) AS pool_coverage,
SUM(e.status='scored') AS scored, SUM(e.correct) AS correct,
SUM(p.covered AND e.status='scored' AND NOT e.correct) AS selection_loss,
SUM(p.covered AND e.status!='scored') AS covered_without_selection
FROM pools p JOIN episode e ON e.task_id=p.task_id
WHERE e.method IN ('sc','usc','cisc') GROUP BY e.method ORDER BY e.method;
