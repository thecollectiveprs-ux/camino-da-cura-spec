# Camino da Cura business requirements

Objective: research UK-based retreat organisers who may hire Camino da Cura exclusively for their own residential groups in Portugal. First pilot target: discover 100 relevant businesses, then report the actual qualification count. No individual consumers or automated outbound messages.

Venue: near Vinhó/Coja in Portugal's Coimbra region; five-bedroom farmhouse with private/shared arrangements; ideal 10–15 guests. Yoga/group spaces, pool, sauna, ice tub, meditation spaces, treatment room and outdoor nature. Steam room is owner-reported and awaiting website confirmation. Venue facts and score weights live in config/venue.json.

Discovery order: established yoga organisers, residential-retreat yoga teachers, small wellness groups, meditation/mindfulness; then Pilates, breathwork, holistic/creative retreats and small leadership/corporate groups; then plausible yoga/wellness studios without confirmed residential history. Organiser base geography must be evidenced separately from retreat destinations.

Qualification: six weighted documented criteria, 25/25/15/15/10/10. A 80+, B 60–79, C below 60. Unknowns earn zero and require research. No budget, intent or group-size assumptions. Past advertisements cannot establish occurrence. Exclude venue-only businesses and consumers. Flag large groups and permanent venue owners without documented external hiring. Preserve Portugal/Spain/European history and all evidence URLs/retrieval dates.

Contact research: publicly listed professional details and official pages only, no generated emails. Preserve source, type, verification and legal-form/compliance status. Public availability never establishes marketing permission; sole traders, unknown forms and personal contacts require human review. Suppression must persist and apply to exports.

Delivered locally: reusable search pipeline, SQLite, Excel CSV, configurable deterministic scorer, reviewed-evidence import, summary and mock tests. Existing code/tests retained. Scores are per venue campaign; deterministic scoring does not require paid LLM usage.

Next development: (1) robots-aware permitted website research, official-site and business identity verification, professional contact extraction; (2) interchangeable interpretation provider with fact/inference validation; (3) coverage/pagination and reviewed relevance to pursue 100 actual relevant candidates within an approved budget; (4) optional licensed verification/Companies House and a human compliance workflow. Live discovery remains paused pending approved provider usage. No email sender.

## Automated research milestone, 13 October 2026

Implemented bounded robots-aware HTML research, source-attributed publisher statements/advertisements, professional contacts and phones, campaign scoring and a capped ten-candidate pilot. UK always means organiser base. Manual assessments are preserved, with raw automated research history stored separately. Automated identity requires human confirmation. See live-pilot.md for activation, limitations and commands. No live requests or outbound sender.
