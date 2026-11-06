# État du projet

Dernière mise à jour : 2026-11-06. Tranche T1 préparée sur `feature/t1-versioned-migrations`, tests réussis; non fusionnée et aucun changement sur `main`.

## Livré dans cette tranche

- Serveur HTTP Python standard library, service local et interface web statique.
- SQLite : registres, missions, événements, budget journalier initial de 5,00 USD et sessions.
- Authentification propriétaire côté serveur basée sur `CLAW3D_ADMIN_PASSWORD` (minimum 12 caractères), cookie HttpOnly/SameSite, en-tête anti-CSRF pour les écritures. Les routes health et ready restent publiques sans mutation.
- Sept rôles internes chargés dans le registre, six Skills versionnés et trois fournisseurs configurables.
- Création et transitions limitées des missions, création de préparations de réunion en attente et audit de ces actions.
- Les missions peuvent être enregistrées, planifiées, suspendues et reprises vers la planification. La transition vers `RUNNING` est refusée tant que le moteur d’exécution n’existe pas.
- Aucun appel fournisseur; aucune simulation d’activité. Une variable présente indique seulement `CONFIGURED`, sans test réseau.

## Limites explicites

Il n’y a pas de véritable routeur de modèles, d’exécution d’agent, d’approbation humaine formalisée, de comptabilisation de coût ni de budget ajustable dans l’interface. Le coupe-circuit est exposé comme indicateur de seuil; aucun exécuteur externe n’existe à bloquer pour l’instant. La configuration de clé n’est pas nécessaire pour exécuter le noyau local.

## Vérification de cette livraison

Le runner versionné est livré dans cette tranche de travail : table `schema_version`, scripts SQL numérotés, sauvegarde SQLite avant chaque migration, checksum des migrations et arrêt du démarrage si une migration échoue. Le premier script est additif et compatible avec les bases produites par le schéma inline précédent.

La suite de tests de cette tranche vérifie sur des fichiers temporaires la migration à froid, la préservation d’une ligne d’une base héritée, le contenu de la sauvegarde antérieure à migration, le rollback/échec startup et l’immutabilité des migrations déjà appliquées. Ne pas utiliser la base locale `data/claw3d.sqlite3` dans les tests.
