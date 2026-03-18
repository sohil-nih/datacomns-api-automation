// Align labels/properties with your Memgraph schema (CCDI curation / Bento).
// Returns distinct subject identifier triples for API cross-check.
MATCH (s)
WHERE ($sex IS NULL OR s.sex = $sex OR toString(s.sex) = toString($sex))
  AND (
    $race_contains IS NULL
    OR toLower(toString(coalesce(s.race, ''))) CONTAINS toLower(toString($race_contains))
  )
RETURN DISTINCT
  coalesce(s.organization, '') AS organization,
  coalesce(s.namespace, '') AS namespace,
  coalesce(s.name, s.subject_id, s.participant_id, toString(id(s))) AS subject_id
