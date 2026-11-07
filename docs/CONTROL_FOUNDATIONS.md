# Fondations de contrôle T4–T6

## Statut de la livraison

Ces composants sont des primitives backend et non un moteur d’exécution. La branche `feature/t4-t6-control-foundations` est empilée explicitement sur `feature/t1-versioned-migrations`; la PR correspondante doit cibler cette branche tant que T1 n’est pas intégrée. Elle n’est pas autonome par rapport à T1 : elle requiert le runner versionné et ajoute `0002_control_foundations.sql`.

Aucun département métier, Scheduler, Workflow Engine, Agent Runtime, appel fournisseur, clé ou SDK n’est ajouté. Aucune route HTTP ni interface n’expose ces composants. Ils n’authentifient pas eux-mêmes un utilisateur ni n’exécutent d’action externe. Le futur orchestrateur devra appeler l’approbation et la réservation du budget avant toute action.

## T4 — contrat fournisseur

`backend/claw3d/providers.py` définit `ProviderAdapter`, `ProviderAvailability`, `ProviderRequest`, `CostEstimate`, `ProviderResponse` et les erreurs typées. `WaitingProvider` reste `WAITING_FOR_PROVIDER` et refuse toute préparation ou exécution. `FixtureProvider` fonctionne localement, renvoie une réponse fixe marquée `LOCAL_FIXTURE`, n’utilise aucun réseau et présente un coût de fixture nul `FIXTURE_ZERO_COST`. Son statut `FIXTURE_ONLY` n’est pas un statut de fournisseur opérationnel.

Le contrat de `execute` permet de tester les appels futurs, mais la seule implémentation fournie est la fixture locale. Annulation retourne `False`, car la fixture synchrone n’a aucune tâche réelle à arrêter.

## T5 — coûts et budgets

`CostManager` sérialise les opérations critiques avec `BEGIN IMMEDIATE`. Les réservations ont une clé d’idempotence unique. Les limites journalières peuvent être configurées par organisation, mission et agent. Le coût réservé est pris en compte avant acceptation; la consommation écrit la dépense dans `spend` et finalise la réservation dans la même transaction. Une consommation supérieure à la réservation, un montant négatif, un rejeu, un double release et le coupe-circuit global sont refusés. La libération ne crée aucune dépense.

L’estimation à réserver est fournie par l’appelant; aucun tarif/token de fournisseur n’est calculé dans cette tranche. Les sources de coût autorisées sont `FIXTURE_SIMULATED` et `OPERATOR_RECORDED`; il n’existe aucun coût fournisseur réel déclaré. Le budget organisation par défaut reste 500 cents par jour; son réglage est synchronisé avec le setting historique lu par le noyau. Les limites mission/agent sont facultatives tant qu’elles ne sont pas définies. Le coupe-circuit empêche de nouvelles réservations; une dépense déjà engagée doit encore pouvoir être enregistrée. Les changements de budget et toutes les opérations de réservation/finalisation sont auditables sans journaliser de prompt ou payload.

## T6 — approbations humaines

`ApprovalEngine` lie une approbation à l’identifiant de mission, au composant demandeur, à l’action, au hash SHA-256 du JSON canonique du payload et au coût estimé. Le payload brut n’est pas stocké. La demande expire au plus tard après 24 heures. Une approbation non expirée passe de `PENDING` à `APPROVED`/`REJECTED`; la consommation exige le même contexte exact et passe atomiquement à `CONSUMED`. `BEGIN IMMEDIATE` et l’état terminal empêchent deux consommateurs concurrents. Les événements ne contiennent pas le payload.

L’approbation est une preuve côté domaine, pas une signature externe ni une identité multi-utilisateur complète. Dans cette tranche, `actor` est fourni par l’appelant interne et il n’existe pas encore de route authentifiée ou de vérification RBAC. Le futur moteur devra obtenir cet acteur depuis la session serveur, exiger `consume` avant l’action, et coordonner cette preuve avec la réservation du coût.

## Migration et compatibilité

`0002_control_foundations.sql` n’ajoute que deux tables et des index, plus une valeur de setting via `INSERT OR IGNORE`. Il ne supprime ni ne réécrit aucune donnée existante. Le runner T1 produit une sauvegarde avant de l’appliquer et bloque l’application si le script échoue. La compatibilité v1→v2 est testée sur une base temporaire avec conservation d’une mission et présence d’une sauvegarde pré-migration.

## Validation locale

Les tests couvrent les contrats fixture/attente, limites et coûts, idempotence, libération, coupe-circuit, réservations concurrentes, expiration, refus, changement du payload, rejeu, consommation concurrente, absence du payload dans les événements et upgrade SQLite v1→v2. Tous les tests utilisent des fichiers temporaires. Ces tests ne constituent pas une validation GitHub Actions, et la CI/Gitleaks ne sont pas opérationnels tant que T2 reste non publiée.
