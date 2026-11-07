# État du projet

Dernière mise à jour : 2026-11-07. Cette branche `feature/t4-t6-control-foundations` est explicitement basée sur `feature/t1-versioned-migrations` (PR #1), qui reste non fusionnée; `main` n’est pas modifiée. T3 est une branche/PR séparée et n’est pas requise ici.

## Livré dans cette tranche

- Serveur HTTP Python standard library, service local et interface web statique.
- SQLite : registres, missions, événements, budget journalier initial de 5,00 USD et sessions.
- Authentification propriétaire côté serveur basée sur `CLAW3D_ADMIN_PASSWORD` (minimum 12 caractères), cookie HttpOnly/SameSite, en-tête anti-CSRF pour les écritures. Les routes health et ready restent publiques sans mutation.
- Sept rôles internes chargés dans le registre, six Skills versionnés et trois fournisseurs configurables.
- Création et transitions limitées des missions, création de préparations de réunion en attente et audit de ces actions.
- Les missions peuvent être enregistrées, planifiées, suspendues et reprises vers la planification. La transition vers `RUNNING` est refusée tant que le moteur d’exécution n’existe pas.
- Aucun appel fournisseur ni simulation de bot. La seule réponse synthétique est produite par la fixture T4, marquée `LOCAL_FIXTURE` et destinée aux tests. Une variable présente indique seulement `CONFIGURED`, sans test réseau.
- T4 : contrats fournisseur, `WaitingProvider` et fixture locale déterministe `FixtureProvider`; fixture non opérationnelle, non enregistrée automatiquement et sans réseau.
- T5 : primitive `CostManager` avec budgets journaliers organisation/mission/agent, réservation idempotente, consommation simulée/opérateur, libération, audit et coupe-circuit atomiques.
- T6 : primitive `ApprovalEngine` liée à mission, requester, action, hash SHA-256 du payload canonique et coût, avec expiration, décision, consommation unique et journalisation sans payload brut.
- Migration 0002 additive pour `cost_reservations` et `approval_requests`; aucun effacement ou remplacement de données.

## Limites explicites

T4-T6 ne sont pas intégrés à une route HTTP, à l’interface, au pipeline des missions ou à un exécuteur. L’estimation de coût T5 vient de l’appelant; seule la fixture donne le coût simulé nul. `OPERATOR_RECORDED` ne constitue pas une mesure indépendante d’un fournisseur. Les modules ne garantissent donc pas encore qu’une future action passera par l’approbation et le budget. Il n’y a toujours ni routeur de modèles ni exécution d’agent; la transition mission vers `RUNNING` demeure bloquée. La configuration d’une clé n’est pas nécessaire au noyau local.

## Vérification de cette livraison

Le runner versionné utilise la table `schema_version`, les scripts SQL numérotés, les checksums et bloque le démarrage si une migration échoue. Il prend `BEGIN IMMEDIATE` avant la sauvegarde, qui est faite via une connexion de lecture indépendante afin d’empêcher les écritures concurrentes entre le snapshot et la migration. Les fichiers de sauvegarde sont créés avec le mode propriétaire `0600`. Le premier script est additif et compatible avec les bases produites par le schéma inline précédent.

Le mode SQLite `:memory:` est explicitement refusé lorsqu’une migration est nécessaire, car le runner exige une sauvegarde fichier durable. La suite teste sur fichiers temporaires les migrations v1→v2, la préservation de données, la restauration, le mode `0600`, le blocage d’écriture concurrente, l’échec avec rollback et le checksum. Les tests T4-T6 couvrent aussi les opérations budget/approbation concurrentes et les replays. Le dernier résultat de tests doit être relevé dans le rapport de livraison; il ne constitue pas un check GitHub. La PR de cette branche sera empilée sur T1 et n’aura pas de CI opérationnelle avant publication de T2. Ne pas utiliser `data/claw3d.sqlite3` dans les tests.
