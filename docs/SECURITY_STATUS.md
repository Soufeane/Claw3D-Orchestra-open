# État de sécurité

## Mesures présentes

- Les mots de passe de fournisseur et d’admin ne sont pas livrés dans le dépôt; `.env` et bases de données sont ignorés par Git.
- Authentification vérifiée côté serveur, mot de passe exigé par variable d’environnement, sessions aléatoires dont seul le hash est stocké, expiration après huit heures.
- Cookies `HttpOnly` et `SameSite=Strict`; activer `CLAW3D_COOKIE_SECURE=1` derrière HTTPS. Le mode local HTTP de développement garde Secure désactivé.
- Écritures API protégées par session et en-tête anti-CSRF personnalisé; validation de quelques champs et plafond de corps JSON.
- Health/ready sans mutation et audit des actions sensibles.

## À durcir avant toute exposition réseau

Le serveur est destiné au loopback local, pas à Internet. Il manque TLS intégré, limitation de débit anti-bruteforce, rotation/révocation avancée des sessions, tests de pénétration, politiques multi-rôles, validation stricte de tous champs, migration formelle et observabilité opérationnelle. Ne pas placer derrière proxy public sans durcissement. Les clés d’environnement présentes sont encore signalées comme configurées sans validation de fournisseur, et aucun appel externe n’est implémenté.
