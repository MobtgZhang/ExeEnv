SELECT c.method, COUNT(*) AS successful_consumptions, SUM(r.tokens) AS reported_tokens
FROM consumes c JOIN request r ON r.path=c.request_path
GROUP BY c.method ORDER BY c.method;
