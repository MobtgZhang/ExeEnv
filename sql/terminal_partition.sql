SELECT e.method, SUM((NOT d.correct) AND e.correct) AS repairs,
SUM(d.correct AND e.status='scored' AND TRIM(COALESCE(e.prediction,''))!='' AND NOT e.correct) AS nonempty_loss,
SUM(d.correct AND e.status='scored' AND TRIM(COALESCE(e.prediction,''))='') AS empty_loss,
SUM(d.correct AND e.status!='scored') AS delivery_loss
FROM episode e JOIN episode d ON e.task_id=d.task_id AND d.method='draft'
WHERE e.method!='direct' GROUP BY e.method ORDER BY e.method;
