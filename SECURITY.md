# Security and data boundary

Only public, synthetic, or anonymized team-level information belongs in this repository.

Do not submit names, medical information, private schedules, disciplinary records, military orders, deployment details, credentials, tokens, or real operational records. Report suspected exposure privately to the repository owner and remove the affected history before public release.

The prototype is advisory and read-only. It must not be connected to live dispatch, scheduling, messaging, or mutual-aid controls without a separate security review and explicit authorization.

The visual interface listens only on `127.0.0.1`, `localhost`, or `::1`. It is not designed for internet exposure and has no user authentication. Do not reverse-proxy or bind it to a network interface without adding authentication, transport security, authorization, rate limiting, logging review, and a formal threat assessment.

The local server limits JSON requests to 64 KiB, requires same-origin browser writes, rejects non-loopback host headers, and returns restrictive Content Security Policy, frame, MIME-sniffing, referrer, and permissions headers. These controls reduce local browser risk but do not make the prototype suitable for production.
