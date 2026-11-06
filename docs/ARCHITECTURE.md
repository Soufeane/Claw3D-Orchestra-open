# Architecture

## Principes

Un monolithe modulaire est retenu pour garder le cœur indépendant de l’interface et éviter les microservices. La première version utilise Python standard library et SQLite afin de s’exécuter localement sans dépendance externe. Le schéma est géré par des migrations SQL numérotées et additives (`CREATE TABLE IF NOT EXISTS`). Avant chaque migration, le runner crée une sauvegarde SQLite cohérente; tout échec bloque le démarrage. Aucun reset de base n’est fourni.

## Modules

- `backend/claw3d/core.py` : persistance, registre initial, événements, budget, création et transitions des missions.
- `backend/claw3d/migrations.py` et `backend/claw3d/migrations/` : séquencement, vérification par checksum et sauvegardes avant migration.
- `backend/claw3d/server.py` : transport HTTP, sessions propriétaire, contrôle anti-CSRF, routes JSON, service statique.
- `frontend/static/` : console HTML/CSS/JS same-origin alimentée par API; pas de fausses données.
- `engine/{bots,skills,router,workflows,memory}/` : frontières prévues pour déplacer le domaine vers des modules spécialisés sans dépendance à l’UI.
- `tests/` : vérification du domaine et du serveur.

## Flux

Le navigateur appelle le backend same-origin. Toute route métier exige une session propriétaire. Les opérations d’écriture exigent `X-Claw3D-Request: 1`. Le serveur lit les clés fournisseur uniquement depuis son environnement et n’enregistre jamais leur valeur. La couche d’exécution et les appels externes ne sont pas présents dans cette livraison.

## Schéma actuel

`bots`, `skills`, `providers`, `models`, `missions`, `tasks`, `departments`, `events`, `settings`, `budgets`, `spend`, `decisions`, `meetings`, `approvals`, `users` et `sessions`. Plusieurs tables fournissent seulement un schéma extensible et n’ont pas encore d’API métier complète. L’authentification représente actuellement l’unique propriétaire local configuré via environnement; une gestion multi-utilisateur reste future.
