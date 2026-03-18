MATCH (p:participant)
OPTIONAL MATCH (p)-[:of_participant]->(:consent_group)
               -[:of_consent_group]->(st:study)
WITH
    st.study_id AS study_id,
    p.participant_id AS participant_id,
    CASE
        WHEN toLower(p.sex_at_birth) IN ['male', 'm'] THEN 'M'
        WHEN toLower(p.sex_at_birth) IN ['female', 'f'] THEN 'F'
        ELSE 'U'
    END AS sex_code
WHERE study_id IS NOT NULL
  AND participant_id IS NOT NULL
RETURN
    sex_code AS sex_at_birth,
    COUNT(DISTINCT toString(study_id) + '|' + toString(participant_id)) AS count
ORDER BY count DESC
