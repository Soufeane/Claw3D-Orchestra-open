# Décisions

## 2026-11-06 — monolithe local sans dépendances

Le dépôt était initialement constitué d’un README et d’un commit. Le cœur est donc un serveur Python standard library et SQLite, avec interface web statique. Ce choix favorise démarrage local, faible friction et indépendance moteur/UI avant d’introduire une infrastructure.

## 2026-11-06 — pas d’appels externes dans la tranche initiale

Les noms des fournisseurs et variables de configuration sont préparés, mais aucun adaptateur réseau n’est livré. La présence d’une clé n’autorise donc aucun appel; l’interface affiche cette limite.

## 2026-11-06 — authentification locale via variable d’environnement

Un mot de passe propriétaire fort est injecté au démarrage et n’est pas stocké. Session aléatoire stockée sous forme de hash; cookie HttpOnly/SameSite, Secure activable en HTTPS. La version actuelle assume un seul propriétaire local, pas une plateforme exposée à Internet.

## 2026-11-06 — données non fictives

Les rôles bots et Skills sont des entrées de registre, non des processus actifs. Les missions créées par l’utilisateur sont persistées et aucune sortie de modèle n’est fabriquée.

## 2026-11-07 — primitives de contrôle isolées avant l’exécution

Le contrat fournisseur possède seulement une fixture locale déterministe et un placeholder `WAITING_FOR_PROVIDER`; aucun SDK ni réseau n’est autorisé dans cette étape. Les budgets et approbations sont des primitives SQLite transactionnelles, pas encore des intercepteurs obligatoires d’une action. Les montants fixtures et opérateur restent étiquetés et ne sont jamais présentés comme des coûts de fournisseur mesurés. La migration 0002 est additive et la livraison est empilée explicitement sur la PR T1, car elle exige son runner versionné.
