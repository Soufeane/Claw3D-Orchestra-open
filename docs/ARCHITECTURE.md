# Architecture

## Principes

Un monolithe modulaire est retenu pour garder le cœur indépendant de l’interface et éviter les microservices. La première version utilise Python standard library et SQLite afin de s’exécuter localement sans dépendance externe. Le schéma est géré par des migrations SQL numérotées et additives (`CREATE TABLE IF NOT EXISTS`). Pour chaque migration, le runner obtient d’abord un verrou d’écriture (`BEGIN IMMEDIATE`), puis sauvegarde via une connexion SQLite de lecture indépendante; cela bloque les écritures concurrentes entre le snapshot et l’application. Les backups fichier sont en mode `0600`; une restauration reste une opération explicite de l’opérateur. Les bases `:memory:` sont refusées pour une migration en attente, car elles ne permettent pas de backup durable. Tout échec bloque le démarrage. Aucun reset de base n’est fourni.

## Modules

- `backend/claw3d/core.py` : persistance, registre initial, événements, budget, création et transitions des missions.
- `backend/claw3d/migrations.py` et `backend/claw3d/migrations/` : séquencement, vérification par checksum et sauvegardes avant migration.
- `backend/claw3d/providers.py` : contrat indépendant des fournisseurs, adaptateur fixture local et placeholder `WAITING_FOR_PROVIDER`; aucun SDK ni réseau.
- `backend/claw3d/costs.py` : réservations et dépenses transactionnelles, scopes organisation/mission/agent, idempotence et coupe-circuit.
- `backend/claw3d/approvals.py` : demandes liées au hash du payload canonique, expiration, décision humaine et consommation à usage unique.
- `backend/claw3d/server.py` : transport HTTP, sessions propriétaire, contrôle anti-CSRF, routes JSON, service statique.
- `frontend/static/` : console HTML/CSS/JS same-origin alimentée par API; pas de fausses données.
- `engine/{bots,skills,router,workflows,memory}/` : frontières prévues pour déplacer le domaine vers des modules spécialisés sans dépendance à l’UI.
- `tests/` : vérification du domaine et du serveur.

## Flux

Le navigateur appelle le backend same-origin. Toute route métier exige une session propriétaire. Les opérations d’écriture exigent `X-Claw3D-Request: 1`. Le serveur lit les clés fournisseur uniquement depuis son environnement et n’enregistre jamais leur valeur. La couche d’exécution et les appels externes ne sont pas présents dans cette livraison.

## Schéma actuel

`bots`, `skills`, `providers`, `models`, `missions`, `tasks`, `departments`, `events`, `settings`, `budgets`, `spend`, `decisions`, `meetings`, `approvals`, `users`, `sessions`, `cost_reservations` et `approval_requests`. La migration 0002 est additive, empilée explicitement sur T1. Les nouveaux modules ne sont pas câblés aux routes, à un Scheduler ou à un exécuteur; ce sont des primitives de domaine testées. L’authentification représente actuellement l’unique propriétaire local configuré via environnement; une gestion multi-utilisateur reste future.
