MATCH (sa:sample)
WHERE sa.sample_id IS NOT NULL
  AND toString(sa.sample_id) <> ''

OPTIONAL MATCH (d:diagnosis)-[:of_diagnosis]->(sa)

OPTIONAL MATCH (sa)-[:of_sample]->(:cell_line)-[:of_cell_line]->(st1:study)

OPTIONAL MATCH (sa)-[:of_sample]->(:participant)
               -[:of_participant]->(:consent_group)
               -[:of_consent_group]->(st2:study)

WITH sa,
     d,
     coalesce(st1, st2) AS st
WHERE st IS NOT NULL

WITH sa.sample_id AS sample_id,
     st.study_id AS study_id,
     d.tumor_grade AS tumor_grade

WITH DISTINCT sample_id, study_id, tumor_grade

RETURN tumor_grade AS value,
       COUNT(DISTINCT toString(sample_id) + ':' + toString(study_id)) AS count
ORDER BY count DESC, value ASC
