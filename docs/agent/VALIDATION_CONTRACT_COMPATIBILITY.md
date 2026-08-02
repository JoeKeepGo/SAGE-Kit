# Contract Compatibility

Current work uses the contract explicitly selected by project authority.
Historical records remain immutable and are interpreted according to their
original release or project documentation when an audit requires it.

The model-native release line does not ship legacy executable validators and
does not rewrite accepted history. Old release tags remain the authoritative
artifact for legacy runtime behavior. New projects use current static schemas
as guidance or pass them to a validator already chosen by the project.

Contract failure never falls back to an older version. Ambiguous or mixed
authority fails closed. Compatibility evidence cannot grant acceptance.
