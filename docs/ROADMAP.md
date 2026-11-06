# Feuille de route

## Fondation — tranche initiale
- [x] Dépôt inspecté avant modifications; base locale avec serveur, SQLite, registres, missions et console.
- [x] Authentification serveur, health/ready, journalisation d’événements et statuts fournisseurs en attente.
- [ ] Validation complète des routes, auth, cookies/CSRF et erreurs de connexion via tests d’intégration.
- [ ] Pipeline CI reproductible et migrations versionnées formelles.

## Exécution contrôlée
- [ ] Abstraction de fournisseur et validation explicite des configurations, sans exposer les clés.
- [ ] Décomposition de mission et attribution aux rôles/Skills, avec exécution réelle uniquement si fournisseur configuré.
- [ ] Budgets transactionnels, coûts réels, limites par mission et coupe-circuit appliqué à l’exécuteur.
- [ ] Approbations propriétaire avant action externe, financière ou commerciale.

## Organisation
- [ ] Mémoires mission/département/organisation avec politiques de rétention.
- [ ] Réunions alimentées par données réellement produites, objections et décisions traçables.
- [ ] Mesures de qualité, fiabilité, coût et délai à partir de résultats réels.
- [ ] Départements additionnels et permissions granulaires.

## Interface
- [ ] Paramètres de routage et de budget protégés, avec affichage de la disponibilité réellement vérifiée.
- [ ] Vues dédiées aux décisions, approbations et détails d’audit.
- [ ] Préparation architecturale 3D facultative, sans bloquer le moteur.
