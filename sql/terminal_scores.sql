SELECT method, COUNT(*) AS attempts, SUM(correct) AS matches,
SUM(status='scored' AND correct=0 AND TRIM(COALESCE(prediction,''))!='') AS nonempty_mismatch,
SUM(status='scored' AND TRIM(COALESCE(prediction,''))='') AS returned_empty,
SUM(status!='scored') AS unavailable FROM episode GROUP BY method ORDER BY method;
