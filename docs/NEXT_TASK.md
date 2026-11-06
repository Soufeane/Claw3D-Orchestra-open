# Prochaine tâche prioritaire

Construire et tester la couche d’exécution contrôlée (après durcissement auth/API) : abstraction de fournisseur, validation réseau/clé sans afficher les secrets, réponse `WAITING_FOR_PROVIDER` tant qu’aucun fournisseur n’est configuré, suivi des dépenses atomique et coupe-circuit appliqué avant chaque appel réel. Toute action externe doit rester sans effet tant qu’elle n’a pas l’approbation humaine requise.

Avant d’ajouter les fournisseurs, compléter les tests HTTP d’authentification et d’accès, tester cookie/anti-CSRF, les transitions complètes, ready avec base inaccessible, et sécurité anti-fuite de secrets. Ajouter une CI et choisir une stratégie de migrations versionnées sans jamais écraser la base existante.
