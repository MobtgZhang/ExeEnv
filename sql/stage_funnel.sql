SELECT stage, COUNT(*) AS attempted, SUM(status='ok') AS returned
FROM depends_on WHERE method='cure_l' GROUP BY stage ORDER BY stage;
