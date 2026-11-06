# État du projet

Dernière mise à jour : 2026-11-06. Branche initiale : `main`, dépôt initialement limité à un README et un commit.

## Livré dans cette tranche

- Serveur HTTP Python standard library, service local et interface web statique.
- SQLite : registres, missions, événements, budget journalier initial de 5,00 USD et sessions.
- Authentification propriétaire côté serveur basée sur `CLAW3D_ADMIN_PASSWORD` (minimum 12 caractères), cookie HttpOnly/SameSite, en-tête anti-CSRF pour les écritures. Les routes health et ready restent publiques sans mutation.
- Sept rôles internes chargés dans le registre, six Skills versionnés et trois fournisseurs configurables.
- Création et transitions limitées des missions, création de préparations de réunion en attente et audit de ces actions.
- Aucun appel fournisseur; aucune simulation d’activité. Une variable présente indique seulement `CONFIGURED`, sans test réseau.

## Limites explicites

Il n’y a pas de véritable routeur de modèles, d’exécution d’agent, d’approbation humaine formalisée, de comptabilisation de coût ni de budget ajustable dans l’interface. Le coupe-circuit est exposé comme indicateur de seuil; aucun exécuteur externe n’existe à bloquer pour l’instant. La configuration de clé n’est pas nécessaire pour exécuter le noyau local.

## Vérification de cette livraison

Les résultats effectifs des tests, du smoke test HTTP, du scan de secrets et du build sont consignés dans le rapport de livraison de session et dans la CI à venir; ne pas considérer une vérification comme réussie avant son exécution.
