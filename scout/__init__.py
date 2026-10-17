"""Scout: watches public early-career job feeds, scores them, alerts, and preps applications.

Modules, in pipeline order:
  listings     fetch the source lists and normalize every row into one shape
  dedupe       one stable key per posting, so the same job from two sources counts once
  matching     company tier, role, location, early-career words, degree check
  scoring      the 0 to 100 score with a breakdown
  eligibility  reads a posting page for posting availability (network, cached)
  watch        the command line entry point that runs all of the above
"""
