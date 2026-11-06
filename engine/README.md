# Frontières moteur

Les sous-répertoires `bots/`, `skills/`, `router/`, `workflows/` et `memory/` réservent des frontières modulaires indépendantes de l’interface. Le registre et le domaine de la première tranche résident dans `backend/claw3d/core.py`; ne pas créer de processus bots permanents ni de fausses exécutions.
