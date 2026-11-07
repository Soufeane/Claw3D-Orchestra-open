# Claw3D Orchestra

Claw3D Orchestra est une fondation locale pour une organisation numérique pilotée par son propriétaire. Les bots sont des rôles internes ; les fournisseurs IA sont des ressources techniques séparées. Cette première tranche persiste les données dans SQLite et n’invente aucune exécution ou réponse de bot.

## Démarrer localement

Prérequis : Python 3.10+ (aucune dépendance externe). Depuis la racine :

```sh
export CLAW3D_ADMIN_PASSWORD='choisir-un-secret-local-de-16-caracteres-ou-plus'
python3 -m backend.claw3d.server
```

Ouvrir `http://127.0.0.1:8000`. Au démarrage, l’application applique les migrations SQLite numérotées et crée une copie de sauvegarde avant chacune. `CLAW3D_DB_PATH` permet de choisir un autre chemin SQLite. Les migrations échouées bloquent le démarrage; les données existantes ne sont pas réinitialisées. Pour un accès HTTPS derrière un proxy TLS de confiance, définissez `CLAW3D_COOKIE_SECURE=1` et n’exposez pas directement le serveur HTTP à Internet.

Vérifications sans authentification : `GET /api/health` et `GET /api/ready`. Les autres routes API exigent une session propriétaire. Configurez les clés fournisseur uniquement dans l’environnement du processus ; elles ne sont ni affichées ni journalisées.

## Portée de la première tranche

Opérationnels : serveur local, schéma SQLite créé de façon additive, session propriétaire, registre de sept rôles bots, six Skills versionnés, missions avec transitions contrôlées et événements d’audit, préparations de réunion, statut explicite des fournisseurs, interface responsive et endpoints de santé/préparation. Les missions peuvent être préparées ou suspendues, mais aucune action ne prétend lancer un bot : la transition vers `RUNNING` est bloquée tant que le moteur réel n’est pas livré.

Non implémentés et désactivés : exécution réelle des modèles, planification/délégation automatique, mises à jour de fournisseur depuis l’interface, comptabilisation des coûts réels, modification du plafond via UI, approbations détaillées, mémoire longue durée et évaluation des performances. Le tableau de bord ne prétend pas que ces fonctions existent. Le statut `CONFIGURED` confirme seulement la présence d’une variable ; il ne valide pas la clé chez le fournisseur. Aucun appel réseau externe n’est implémenté.

DeepSeek (`DEEPSEEK_API_KEY`), Grok (`GROK_API_KEY`) et Groq (`GROQ_API_KEY`) restent `WAITING_FOR_API_KEY` si la variable correspondante est absente.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

Voir [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) et [`docs/NEXT_TASK.md`](docs/NEXT_TASK.md) pour l’état précis.
