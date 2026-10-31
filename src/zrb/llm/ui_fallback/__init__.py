"""The UI pieces L0 may construct.

`StdUI` is the fallback for a run with no UI, so it cannot live in the
presentation layer the run loop must not import. `resolution` combines several
UIs through a combiner the presentation layer registers; `state_defaults`
holds the inert `AnyUI` members.
"""
