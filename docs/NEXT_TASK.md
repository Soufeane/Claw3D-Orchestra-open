# Prochaine tâche prioritaire

Prochaine tranche candidate (T2) : ajouter une CI GitHub Actions minimale qui exécute `python3 -m unittest discover -s tests -v` sur chaque pull request et lance un scan de secrets. Cette tâche est notée, pas commencée dans T1.

Les tranches ultérieures, à ne démarrer qu’après accord, sont T3 (tests HTTP de sécurité), T4 (abstraction fournisseur factice), T5 (dépenses atomiques et coupe-circuit), T6 (approbations liées à l’action), puis T7 (validation réseau uniquement sur ordre explicite). Ne pas appeler un vrai fournisseur ni effectuer de validation réelle de clé.
