# État de sécurité

## Mesures présentes

- Les mots de passe de fournisseur et d’admin ne sont pas livrés dans le dépôt; `.env` et bases de données sont ignorés par Git.
- Authentification vérifiée côté serveur, mot de passe exigé par variable d’environnement, sessions aléatoires dont seul le hash est stocké, expiration après huit heures.
- Cookies `HttpOnly` et `SameSite=Strict`; activer `CLAW3D_COOKIE_SECURE=1` derrière HTTPS. Le mode local HTTP de développement garde Secure désactivé.
- Écritures API protégées par session et en-tête anti-CSRF personnalisé; le logout exige aussi session et CSRF.
- Corps JSON limités à 64 KiB, Content-Length et Content-Type validés; JSON malformé renvoie 400 et payload trop grand 413.
- Limitation de connexion à cinq échecs par adresse IP sur une fenêtre de 60 secondes, avec réponse 429 et Retry-After.
- `/api/ready` vérifie une requête SQLite et retourne 503 sans exposer le chemin ou l’erreur si la base est indisponible.
- Health/ready sans mutation et événements de refus d’authentification consignés sans mot de passe ni cookie.

## À durcir avant toute exposition réseau

Le serveur reste destiné au loopback local, pas à Internet. Le limiteur de connexion est en mémoire par processus et se réinitialise au redémarrage; derrière plusieurs workers ou un proxy, il ne fournit pas une limite globale et n’utilise volontairement pas les en-têtes IP transférés. Il manque TLS intégré, révocation de toutes les sessions, validation stricte et cohérente de chaque champ, protections opérateur contre DoS, tests de pénétration et observabilité opérationnelle. Ne pas placer derrière proxy public sans durcissement complémentaire. Les clés d’environnement restent seulement signalées comme configurées, sans validation de fournisseur, et aucun appel externe n’est implémenté. Les migrations versionnées de T1 ne sont pas présentes dans cette branche T3 basée sur `main`.
