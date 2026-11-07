# État du projet

Dernière mise à jour : 2026-11-07. T1 reste sur `feature/t1-versioned-migrations`, non fusionnée; `main` n’est pas modifiée.

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

Le runner versionné utilise la table `schema_version`, les scripts SQL numérotés, les checksums et bloque le démarrage si une migration échoue. Il prend `BEGIN IMMEDIATE` avant la sauvegarde, qui est faite via une connexion de lecture indépendante afin d’empêcher les écritures concurrentes entre le snapshot et la migration. Les fichiers de sauvegarde sont créés avec le mode propriétaire `0600`. Le premier script est additif et compatible avec les bases produites par le schéma inline précédent.

Le mode SQLite `:memory:` est explicitement refusé lorsqu’une migration est nécessaire, car le runner exige une sauvegarde fichier durable. La suite teste sur fichiers temporaires la migration à froid, les données héritées, la restauration effective d’une sauvegarde, le mode `0600`, le blocage d’une écriture concurrente, l’échec avec rollback, le refus mémoire et le checksum. Lors de la validation locale du 2026-11-07, `python3 -m unittest discover -s tests -v` a réussi avec 19 tests. Ce résultat local ne constitue pas un check GitHub; la PR n’a pas de CI attachée actuellement. Ne pas utiliser `data/claw3d.sqlite3` dans les tests.
