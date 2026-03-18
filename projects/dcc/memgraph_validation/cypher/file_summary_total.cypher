MATCH (sf:sequencing_file)-[:of_sequencing_file]->(sa:sample)
WHERE sf.id IS NOT NULL AND toString(sf.id) <> ""
OPTIONAL MATCH (sa)-[:of_sample]->(:cell_line)-[:of_cell_line]->(st1:study)
OPTIONAL MATCH (sa)-[:of_sample]->(:participant)-[:of_participant]->(:consent_group)-[:of_consent_group]->(st2:study)
WITH sf.id AS file_id,
     sa.sample_id AS sample_id,
     coalesce(st1, st2).study_id AS study_id
WHERE study_id IS NOT NULL
RETURN COUNT(DISTINCT toString(file_id) + ':' + toString(sample_id) + ':' + toString(study_id)) AS total_files
