# Prochaine tâche prioritaire

T4-T6 sont implémentées comme primitives sur `feature/t4-t6-control-foundations`, explicitement empilée sur T1. Avant tout runtime, faire relire T1 puis T4-T6 dans cet ordre; aucune fusion n’est automatique. T3 est une PR distincte. T2 est préparée localement mais non publiée faute de permission GitHub `Workflows: Read and write`; ne pas présenter la CI ou Gitleaks comme actifs.

Après revue humaine des PR, la prochaine tranche technique devrait brancher une API propriétaire contrôlée sur les primitives de budget et d’approbation, avec une politique d’acteur vérifiable et tests end-to-end. Elle ne doit toujours pas déclencher d’exécution externe. Ne commencer Scheduler, Workflow Engine ou Agent Runtime qu’après ce contrôle d’intégration, et ne jamais appeler un vrai fournisseur ni valider une clé sans ordre explicite.
