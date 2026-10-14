"""
Drafting module (LLD: plans/read-alllegal-drafting-module-track-spec-keen-ladybug.md).

A "track" (cheque bounce, commercial suit, bail, ...) is a configuration of the
same shared flow: capture facts once -> compute deadlines -> generate
fixed-format ("F") documents -> (Phase 2) research group -> research-linked
("R") documents. This package holds the engine; `app/drafting/tracks/<key>/`
holds each track's config, fact model and templates. Nothing in here should
know the word "cheque" except the cheque_bounce track package itself.
"""
