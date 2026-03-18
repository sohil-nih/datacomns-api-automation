// Distinct study ids reachable from participants (same linkage pattern as sex-count TC04).
// GET /namespace lists each catalog entry with id.name — typically phs* / study accession.
MATCH (p:participant)-[:of_participant]->(:consent_group)-[:of_consent_group]->(st:study)
WHERE st.study_id IS NOT NULL AND toString(st.study_id) <> ''
RETURN DISTINCT toString(st.study_id) AS namespace_name
ORDER BY namespace_name
